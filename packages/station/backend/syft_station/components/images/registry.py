"""Anonymous container-registry client for listing syft-space image tags.

Talks the OCI Distribution API (GHCR flavor) without credentials — public
images grant an anonymous pull token. Build tags carry no inherent order
(they are commit ids), so each tag's created date comes from its image
config blob: tag → index manifest → platform manifest → config blob.

Tag metadata is immutable once pushed; callers pass previously resolved
tags back in so only new tags cost the three-request chain.
"""

import asyncio
from datetime import datetime

import httpx
from loguru import logger
from pydantic import BaseModel

_HTTP_TIMEOUT_SECONDS = 15.0
_MAX_CONCURRENT_RESOLVES = 10

# Per-architecture tags duplicate their bare multi-arch tag; hide them.
_ARCH_SUFFIXES = ("-amd64", "-arm64")

_MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)
_INDEX_MEDIA_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)

REVISION_LABEL = "org.opencontainers.image.revision"


class RegistryError(Exception):
    """The registry could not be reached or gave an unusable response."""


class ResolvedImage(BaseModel):
    """One build tag with the metadata needed to sort and display it."""

    tag: str
    created: datetime
    revision: str | None
    digest: str


class ImageRegistryClient:
    """Lists and resolves image tags for one repository, anonymously."""

    def __init__(self, registry: str, repository: str):
        self.base_url = f"https://{registry}"
        self.repository = repository

    def _build_http_client(self) -> httpx.AsyncClient:
        """Build the HTTP client (seam for tests to inject a MockTransport)."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,  # blob downloads redirect to backing storage
        )

    async def fetch_catalog(
        self, known: dict[str, ResolvedImage]
    ) -> tuple[list[ResolvedImage], str | None]:
        """Resolve every bare build tag, reusing ``known`` entries.

        Returns the resolved tags and the manifest digest that ``latest``
        currently points at (None if the repository has no ``latest`` tag).
        Tags that fail to resolve individually are logged and skipped;
        registry-level failures raise RegistryError.
        """
        try:
            async with self._build_http_client() as client:
                headers = {"Authorization": f"Bearer {await self._token(client)}"}
                tags = await self._list_tags(client, headers)

                bare = [
                    t for t in tags if t != "latest" and not t.endswith(_ARCH_SUFFIXES)
                ]
                semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RESOLVES)

                async def resolve(tag: str) -> ResolvedImage | None:
                    if tag in known:
                        return known[tag]
                    async with semaphore:
                        try:
                            return await self._resolve_tag(client, headers, tag)
                        except Exception as e:
                            logger.warning(f"Skipping unresolvable tag '{tag}': {e}")
                            return None

                resolved = await asyncio.gather(*(resolve(t) for t in bare))

                latest_digest = None
                if "latest" in tags:
                    try:
                        _, latest_digest = await self._get_manifest(
                            client, headers, "latest"
                        )
                    except Exception as e:
                        logger.warning(f"Could not resolve 'latest' digest: {e}")

                return [r for r in resolved if r is not None], latest_digest
        except RegistryError:
            raise
        except httpx.HTTPError as e:
            raise RegistryError(f"Registry is unreachable: {e}") from e

    async def _token(self, client: httpx.AsyncClient) -> str:
        """Fetch an anonymous pull token (public repositories only)."""
        response = await client.get(
            "/token", params={"scope": f"repository:{self.repository}:pull"}
        )
        if response.status_code != 200:
            raise RegistryError(
                f"Token request failed with status {response.status_code}"
            )
        token = response.json().get("token")
        if not token:
            raise RegistryError("Token response missing 'token'")
        return token

    async def _list_tags(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> list[str]:
        response = await client.get(
            f"/v2/{self.repository}/tags/list",
            params={"n": 1000},
            headers=headers,
        )
        if response.status_code != 200:
            raise RegistryError(
                f"Tag listing failed with status {response.status_code}"
            )
        return response.json().get("tags") or []

    async def _get_manifest(
        self, client: httpx.AsyncClient, headers: dict[str, str], reference: str
    ) -> tuple[dict, str]:
        """Fetch a manifest by tag or digest; returns (manifest, digest)."""
        response = await client.get(
            f"/v2/{self.repository}/manifests/{reference}",
            headers={**headers, "Accept": _MANIFEST_ACCEPT},
        )
        if response.status_code != 200:
            raise RegistryError(
                f"Manifest '{reference}' failed with status {response.status_code}"
            )
        return response.json(), response.headers.get("docker-content-digest", "")

    async def _resolve_tag(
        self, client: httpx.AsyncClient, headers: dict[str, str], tag: str
    ) -> ResolvedImage:
        """Walk tag → (index →) platform manifest → config blob."""
        manifest, digest = await self._get_manifest(client, headers, tag)

        if manifest.get("mediaType") in _INDEX_MEDIA_TYPES:
            platform_digest = self._pick_platform_digest(manifest, tag)
            manifest, _ = await self._get_manifest(client, headers, platform_digest)

        config_digest = manifest["config"]["digest"]
        response = await client.get(
            f"/v2/{self.repository}/blobs/{config_digest}", headers=headers
        )
        if response.status_code != 200:
            raise RegistryError(
                f"Config blob for '{tag}' failed with status {response.status_code}"
            )
        config = response.json()

        labels = (config.get("config") or {}).get("Labels") or {}
        return ResolvedImage(
            tag=tag,
            created=datetime.fromisoformat(config["created"]),
            revision=labels.get(REVISION_LABEL),
            digest=digest,
        )

    @staticmethod
    def _pick_platform_digest(index: dict, tag: str) -> str:
        """Pick a real platform entry from an index (skips attestations)."""
        for entry in index.get("manifests", []):
            platform = entry.get("platform") or {}
            if platform.get("os") not in (None, "unknown"):
                return entry["digest"]
        raise RegistryError(f"Index for '{tag}' has no platform manifests")
