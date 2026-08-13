"""Request handler — typed submit/approve/reject/withdraw + provisioning.

`submit` dispatches on the request's type. Approval runs the type's side
effect: create_space provisions a space (async), delete_space tears one
down. Reject (admin declines) and withdraw (owner cancels their own pending
ask) are generic and terminal.
"""

import asyncio
from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger

from syft_station.components.auth.session import ROLE_ADMIN, SessionUser
from syft_station.components.provision.interfaces import Provisioner, ProvisionError
from syft_station.components.requests.entities import (
    Request,
    RequestOrigin,
    RequestStatus,
    RequestType,
)
from syft_station.components.requests.interfaces import WalletAttachments
from syft_station.components.requests.repository import RequestRepository
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    PatchRequestBody,
    RequestResponse,
    SubmitRequestBody,
)
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.provisioning import SpaceConverger
from syft_station.components.spaces.repository import (
    SpaceRepository,
    generate_space_token,
)


def _to_response(request: Request) -> RequestResponse:
    return RequestResponse.model_validate(request.model_dump())


class RequestHandler:
    """Typed request lifecycle, driving the provisioner for space side effects."""

    def __init__(
        self,
        repository: RequestRepository,
        space_repository: SpaceRepository,
        setup_repository: SetupRepository,
        provisioner: Provisioner,
        credits: WalletAttachments,
        converger: SpaceConverger,
    ):
        self.repository = repository
        self.space_repository = space_repository
        self.setup_repository = setup_repository
        self.provisioner = provisioner
        # A station with no wallet is just an empty wallets table — the
        # service then resolves no wallet, grants nothing, revokes nothing.
        self.credits = credits
        self.converger = converger
        # Keep strong references so provisioning tasks aren't GC'd mid-run.
        self._tasks: set[asyncio.Task] = set()

    # --- Queries ---

    async def list_requests(self, user: SessionUser) -> list[RequestResponse]:
        if user.role == ROLE_ADMIN:
            requests = await self.repository.list_all()
        else:
            requests = await self.repository.list_by_owner(user.email)
        return [_to_response(r) for r in requests]

    async def _get_request(self, request_id: UUID) -> Request:
        request = await self.repository.get_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        return request

    async def get_request(self, request_id: UUID, user: SessionUser) -> RequestResponse:
        """One request, for status polling. Members see only their own."""
        request = await self._get_request(request_id)
        self._require_owner_or_admin(request, user)
        return _to_response(request)

    # --- Submit (dispatch on type) ---

    async def submit(
        self, body: SubmitRequestBody, user: SessionUser
    ) -> RequestResponse:
        origin = (
            RequestOrigin.ADMIN if user.role == ROLE_ADMIN else RequestOrigin.MEMBER
        )
        if body.payload.type == RequestType.CREATE_SPACE.value:
            return await self._submit_create(body, user, origin)
        if body.payload.type == RequestType.DELETE_SPACE.value:
            return await self._submit_delete(body, user, origin)
        raise HTTPException(status_code=422, detail="Unknown request type")

    async def _submit_create(
        self, body: SubmitRequestBody, user: SessionUser, origin: RequestOrigin
    ) -> RequestResponse:
        payload = body.payload  # CreateSpacePayload
        # Admin may create on a member's behalf; members own their own.
        owner_email = user.email
        if user.role == ROLE_ADMIN and body.owner_email:
            owner_email = body.owner_email

        if await self._subdomain_taken(payload.subdomain):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{payload.subdomain}' is already taken",
            )
        if await self._owner_has_space_or_pending(owner_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"One space per account: {owner_email} already has a space "
                "or an open request",
            )
        request = await self.repository.create(
            Request(
                type=RequestType.CREATE_SPACE.value,
                owner_email=owner_email,
                space_name=payload.space_name,
                subdomain=payload.subdomain,
                reason=body.reason,
                origin=origin.value,
            )
        )
        return _to_response(request)

    async def _submit_delete(
        self, body: SubmitRequestBody, user: SessionUser, origin: RequestOrigin
    ) -> RequestResponse:
        if not body.space_id:
            raise HTTPException(status_code=422, detail="space_id is required")
        space = await self.space_repository.get_by_id(body.space_id)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        if user.role != ROLE_ADMIN and space.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your space"
            )
        if await self.repository.open_delete_for_space(space.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A deletion request for this space is already pending",
            )
        request = await self.repository.create(
            Request(
                type=RequestType.DELETE_SPACE.value,
                owner_email=space.owner_email,
                space_id=space.id,
                space_name=space.name,
                subdomain=space.subdomain,
                reason=body.reason,
                origin=origin.value,
            )
        )
        return _to_response(request)

    # --- Approve (dispatch on type) ---

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
        if request.type == RequestType.CREATE_SPACE.value:
            return await self._approve_create(request, body)
        if request.type == RequestType.DELETE_SPACE.value:
            return await self._approve_delete(request)
        raise HTTPException(status_code=422, detail="Unknown request type")

    async def _approve_create(
        self, request: Request, body: ApproveRequestBody
    ) -> RequestResponse:
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
        # Resolve the wallet pick now so a bad id fails approve, not the task.
        wallet_id = None
        if body.attach_wallet:
            wallet_id = await self.credits.choose_wallet(body.wallet_id)
        return await self._start_provisioning(
            request, wallet_id=wallet_id, wallet_opt_out=not body.attach_wallet
        )

    async def _approve_delete(self, request: Request) -> RequestResponse:
        space = (
            await self.space_repository.get_by_id(request.space_id)
            if request.space_id
            else None
        )
        await self._teardown(space, request.subdomain)
        request = await self.repository.set_status(request, RequestStatus.APPROVED)
        return _to_response(request)

    # --- Reject / withdraw / retry ---

    async def reject(self, request_id: UUID, reason: str) -> RequestResponse:
        """Admin declines a pending request (create or delete)."""
        request = await self._get_request(request_id)
        if request.status != RequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending requests can be rejected",
            )
        request = await self.repository.set_status(
            request, RequestStatus.REJECTED, resolution_note=reason
        )
        return _to_response(request)

    async def withdraw(self, request_id: UUID, user: SessionUser) -> RequestResponse:
        """Owner (or admin) cancels a pending request of their own."""
        request = await self._get_request(request_id)
        self._require_owner_or_admin(request, user)
        if request.status != RequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending requests can be withdrawn",
            )
        request = await self.repository.set_status(request, RequestStatus.WITHDRAWN)
        return _to_response(request)

    async def retry(self, request_id: UUID) -> RequestResponse:
        request = await self._get_request(request_id)
        if request.type != RequestType.CREATE_SPACE.value:
            raise HTTPException(status_code=409, detail="Only create requests retry")
        if request.status != RequestStatus.FAILED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only failed requests can be retried",
            )
        return await self._start_provisioning(request, set_wallet=False)

    async def transition(
        self, request_id: UUID, body: PatchRequestBody, user: SessionUser
    ) -> RequestResponse:
        """Move a request to a target status (the PATCH entry point).

        Dispatches to the tested lifecycle methods and enforces who may make
        each transition: approve/reject are admin-only; withdraw is the
        owner's (or admin's). A failed create approved again is a retry.
        """
        request = await self._get_request(request_id)
        if body.status == RequestStatus.APPROVED.value:
            self._require_admin(user)
            if request.status == RequestStatus.FAILED.value:
                return await self.retry(request_id)
            return await self.approve(
                request_id,
                ApproveRequestBody(
                    space_name=body.space_name,
                    subdomain=body.subdomain,
                    attach_wallet=body.attach_wallet,
                    wallet_id=body.wallet_id,
                ),
            )
        if body.status == RequestStatus.REJECTED.value:
            self._require_admin(user)
            return await self.reject(request_id, body.reason)
        if body.status == RequestStatus.WITHDRAWN.value:
            return await self.withdraw(request_id, user)
        raise HTTPException(status_code=422, detail="Unsupported target status")

    # --- Helpers ---

    def _require_admin(self, user: SessionUser) -> None:
        if user.role != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin only"
            )

    def _require_owner_or_admin(self, request: Request, user: SessionUser) -> None:
        if user.role != ROLE_ADMIN and request.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your request"
            )

    async def _subdomain_taken(
        self, subdomain: str, exclude_id: UUID | None = None
    ) -> bool:
        """Taken if an open create request reserves it, or a live space owns it."""
        if await self.repository.subdomain_reserved(subdomain, exclude_id=exclude_id):
            return True
        return await self.space_repository.get_by_subdomain(subdomain) is not None

    async def _owner_has_space_or_pending(self, owner_email: str) -> bool:
        """One space per owner: a live space, or an unfinished create request."""
        if await self.space_repository.list_by_owner(owner_email):
            return True
        return await self.repository.open_create_for_owner(owner_email) is not None

    async def _teardown(self, space: Space | None, subdomain: str | None) -> None:
        """Deprovision (purge) and remove the space's registry row + credits."""
        target = space.subdomain if space else subdomain
        if not target:
            return
        try:
            await self.provisioner.deprovision(target, purge=True)
        except Exception as e:
            logger.exception(f"Teardown failed for '{target}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to tear down the space — please try again",
            ) from e
        if space:
            await self.credits.revoke_space(space.id)
            await self.space_repository.delete_space(space.id)

    async def _start_provisioning(
        self,
        request: Request,
        wallet_id: UUID | None = None,
        wallet_opt_out: bool = False,
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
                    wallet_opt_out=wallet_opt_out if set_wallet else False,
                )
            )
            await self.space_repository.create_token(space.id, generate_space_token())
        elif set_wallet and (
            space.wallet_id != wallet_id or space.wallet_opt_out != wallet_opt_out
        ):
            space.wallet_id = wallet_id
            space.wallet_opt_out = wallet_opt_out
            space = await self.space_repository.update(space)

        request.resolution_note = None  # clear a previous attempt's failure
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
        try:
            await self.converger.converge(space)
            await self.repository.set_status(request, RequestStatus.APPROVED)
        except ProvisionError as e:
            logger.warning(f"Provisioning failed for '{space.subdomain}': {e}")
            await self.repository.set_status(
                request, RequestStatus.FAILED, resolution_note=str(e)
            )

    async def wait_for_provisioning(self) -> None:
        """Await any in-flight provisioning tasks (used at shutdown / in tests)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
