"""Space request handler — lifecycle + provisioning orchestration."""

import asyncio
from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger

from syft_station.components.auth.session import ROLE_ADMIN, SessionUser
from syft_station.components.provision.interfaces import (
    Provisioner,
    ProvisionError,
    SpaceSpec,
)
from syft_station.components.requests.entities import (
    RequestOrigin,
    RequestStatus,
    SpaceRequest,
)
from syft_station.components.requests.interfaces import WalletAttachments
from syft_station.components.requests.repository import RequestRepository
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    RequestResponse,
    SubmitRequestBody,
)
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.repository import (
    SpaceRepository,
    generate_space_token,
)


def _to_response(request: SpaceRequest) -> RequestResponse:
    return RequestResponse.model_validate(request.model_dump())


# Only states that have provisioned k8s resources can be torn down.
_DELETABLE_STATUSES = {RequestStatus.ACTIVE.value, RequestStatus.FAILED.value}


class RequestHandler:
    """Submit / approve / reject / retry / withdraw, driving the provisioner."""

    def __init__(
        self,
        repository: RequestRepository,
        space_repository: SpaceRepository,
        setup_repository: SetupRepository,
        provisioner: Provisioner,
        credits: WalletAttachments,
    ):
        self.repository = repository
        self.space_repository = space_repository
        self.setup_repository = setup_repository
        self.provisioner = provisioner
        # A station with no wallet is just an empty wallets table — the
        # service then resolves no wallet, grants nothing, revokes nothing.
        self.credits = credits
        # Keep strong references so provisioning tasks aren't GC'd mid-run.
        self._tasks: set[asyncio.Task] = set()

    # --- Queries ---

    async def list_requests(self, user: SessionUser) -> list[RequestResponse]:
        if user.role == ROLE_ADMIN:
            requests = await self.repository.list_all()
        else:
            requests = await self.repository.list_by_owner(user.email)
        return [_to_response(r) for r in requests]

    async def _get_request(self, request_id: UUID) -> SpaceRequest:
        request = await self.repository.get_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        return request

    async def get_request(self, request_id: UUID, user: SessionUser) -> RequestResponse:
        """One request, for status polling. Members see only their own."""
        request = await self._get_request(request_id)
        if user.role != ROLE_ADMIN and request.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your request"
            )
        return _to_response(request)

    # --- Lifecycle ---

    async def submit(
        self, body: SubmitRequestBody, user: SessionUser
    ) -> RequestResponse:
        if await self._subdomain_taken(body.subdomain):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{body.subdomain}' is already taken",
            )
        origin = (
            RequestOrigin.ADMIN if user.role == ROLE_ADMIN else RequestOrigin.MEMBER
        )
        # The admin can create a space on a member's behalf; members always
        # own their own requests.
        owner_email = user.email
        if user.role == ROLE_ADMIN and body.owner_email:
            owner_email = body.owner_email
        request = await self.repository.create(
            SpaceRequest(
                space_name=body.space_name,
                subdomain=body.subdomain,
                owner_email=owner_email,
                reason=body.reason,
                origin=origin.value,
            )
        )
        return _to_response(request)

    async def approve(
        self, request_id: UUID, body: ApproveRequestBody
    ) -> RequestResponse:
        request = await self._get_request(request_id)
        if request.status != RequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only pending requests can be approved "
                f"(status: {request.status})",
            )

        # Review-and-confirm: the admin may adjust name/subdomain.
        if body.space_name:
            request.space_name = body.space_name
        if body.subdomain:
            request.subdomain = body.subdomain

        if await self._subdomain_taken(request.subdomain, exclude_id=request.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{request.subdomain}' is already taken",
            )

        # Resolve the wallet pick now so a bad id fails the approve, not the
        # background provisioning task.
        wallet_id = None
        if body.attach_wallet:
            wallet_id = await self.credits.choose_wallet(body.wallet_id)

        return await self._start_provisioning(request, wallet_id=wallet_id)

    async def reject(self, request_id: UUID, reason: str) -> RequestResponse:
        request = await self._get_request(request_id)
        if request.status != RequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending requests can be rejected",
            )
        request = await self.repository.set_status(
            request, RequestStatus.REJECTED, reject_reason=reason
        )
        return _to_response(request)

    async def retry(self, request_id: UUID) -> RequestResponse:
        request = await self._get_request(request_id)
        if request.status != RequestStatus.FAILED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only failed requests can be retried",
            )
        return await self._start_provisioning(request, set_wallet=False)

    async def delete_space(
        self, request_id: UUID, user: SessionUser
    ) -> RequestResponse:
        """Tear down a provisioned space and mark the request DELETED.

        The only path that calls the provisioner's deprovision — deletion is
        always an explicit user action (no implicit rollback on failure).
        Full teardown (purge=True): the data volume goes too, so a freed
        subdomain can't be re-provisioned onto another owner's leftover data.
        DELETED is kept as a state for admin visibility.
        """
        request = await self._get_request(request_id)
        if user.role != ROLE_ADMIN and request.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your request"
            )
        if request.status not in _DELETABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only active or failed spaces can be deleted "
                f"(status: {request.status})",
            )

        space = None
        if request.space_id:
            space = await self.space_repository.get_by_id(request.space_id)
        subdomain = space.subdomain if space else request.subdomain

        try:
            await self.provisioner.deprovision(subdomain, purge=True)
        except Exception as e:
            logger.exception(f"Teardown failed for '{subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to tear down the space — please try again",
            ) from e

        if space:
            await self.credits.revoke_space(space.id)
            await self.space_repository.delete_space(space.id)
        request = await self.repository.set_status(request, RequestStatus.DELETED)
        return _to_response(request)

    async def withdraw(self, request_id: UUID, user: SessionUser) -> RequestResponse:
        request = await self._get_request(request_id)
        if user.role != ROLE_ADMIN and request.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your request"
            )
        if request.status != RequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending requests can be withdrawn",
            )
        request = await self.repository.set_status(request, RequestStatus.WITHDRAWN)
        return _to_response(request)

    # --- Provisioning ---

    async def _subdomain_taken(
        self, subdomain: str, exclude_id: UUID | None = None
    ) -> bool:
        if await self.repository.subdomain_in_use(subdomain, exclude_id=exclude_id):
            return True
        return await self.space_repository.get_by_subdomain(subdomain) is not None

    async def _start_provisioning(
        self,
        request: SpaceRequest,
        wallet_id: UUID | None = None,
        set_wallet: bool = True,
    ) -> RequestResponse:
        """set_wallet=False (retry) keeps the space's existing wallet intent."""
        config = await self.setup_repository.get_config()
        if not config.domain:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Station is not set up yet — configure the domain first",
            )

        # Reuse the space + token from a failed attempt; create on first run.
        space = None
        if request.space_id:
            space = await self.space_repository.get_by_id(request.space_id)
        if space is None:
            space = await self.space_repository.create(
                Space(
                    request_id=request.id,
                    name=request.space_name,
                    subdomain=request.subdomain,
                    owner_email=request.owner_email,
                    version=config.supported_version,
                    wallet_id=wallet_id if set_wallet else None,
                )
            )
            await self.space_repository.create_token(space.id, generate_space_token())
        elif set_wallet and space.wallet_id != wallet_id:
            space.wallet_id = wallet_id
            space = await self.space_repository.update(space)

        request.reject_reason = None  # clear a previous attempt's failure
        request = await self.repository.set_status(
            request, RequestStatus.PROVISIONING, space_id=space.id
        )

        task = asyncio.create_task(self._provision(request.id, space.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return _to_response(request)

    async def _provision(self, request_id: UUID, space_id: UUID) -> None:
        request = await self.repository.get_by_id(request_id)
        space = await self.space_repository.get_by_id(space_id)
        if not request or not space:
            logger.error(f"Provisioning lost its request/space ({request_id})")
            return

        config = await self.setup_repository.get_config()
        token_row = await self.space_repository.get_token(space.id)

        # Every attempt mints a FRESH credits token (the previous plaintext
        # is unrecoverable by design); a failed attempt leaves no live grant
        # behind that this retry would still be using.
        grant = None
        if space.wallet_id:
            grant = await self.credits.grant_for_space(space.id, space.wallet_id)

        spec = SpaceSpec(
            subdomain=space.subdomain,
            space_name=space.name,
            owner_email=space.owner_email,
            version=config.supported_version,
            domain=config.domain,
            admin_token=token_row.token or "" if token_row else "",
            credits_url=grant.url if grant else "",
            credits_token=grant.token if grant else "",
            credits_currency=grant.currency if grant else "",
        )

        try:
            url = await self.provisioner.provision(spec)
        except ProvisionError as e:
            logger.warning(f"Provisioning failed for '{space.subdomain}': {e}")
            # Keep the error on the request so the admin sees why it failed
            await self.repository.set_status(
                request, RequestStatus.FAILED, reject_reason=str(e)
            )
            return
        except Exception as e:
            logger.exception(f"Provisioning crashed for '{space.subdomain}'")
            await self.repository.set_status(
                request, RequestStatus.FAILED, reject_reason=f"Unexpected error: {e}"
            )
            return

        space.url = url
        space.version = config.supported_version
        await self.space_repository.update(space)
        await self.repository.set_status(request, RequestStatus.ACTIVE)
        logger.info(f"Space '{space.subdomain}' active at {url}")

    async def wait_for_provisioning(self) -> None:
        """Wait for in-flight provisioning tasks (tests + shutdown)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
