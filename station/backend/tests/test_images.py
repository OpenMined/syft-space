"""Image catalog: GHCR tag listing, date resolution, caching, latest flag."""

import httpx
import pytest
from fastapi import HTTPException

from syft_station.components.images.handlers import ImageHandler
from syft_station.components.images.registry import (
    REVISION_LABEL,
    ImageRegistryClient,
    ResolvedImage,
)

REGISTRY = "ghcr.test"
REPO = "openmined/syft-space"

# tag -> created timestamp; insertion order is deliberately NOT chronological,
# mirroring the real registry (tags/list carries no order guarantee).
TAGS = {
    "6d86bcb": "2026-01-20T09:43:54.224054949Z",
    "ebb4ba3": "2026-01-21T10:00:00Z",
    "2fa954d": "2026-07-14T06:44:58.912595775Z",
    "64bda81": "2026-01-20T11:51:33.950954402Z",
    "13db2b3": "2026-02-02T08:00:00Z",
    "d86118a": "2026-03-15T08:00:00Z",
    "cba1f4c": "2026-04-01T08:00:00Z",
}


class FakeRegistry:
    """MockTransport handler emulating the GHCR anonymous pull flow."""

    def __init__(self, tags: dict[str, str], latest_tag: str | None = "2fa954d"):
        self.tags = tags
        self.latest_tag = latest_tag
        self.down = False
        self.broken_blobs: set[str] = set()
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("registry down")
        path = request.url.path
        self.requests.append(path)

        if path == "/token":
            return httpx.Response(200, json={"token": "anon"})

        if path == f"/v2/{REPO}/tags/list":
            listed = []
            for tag in self.tags:
                listed += [tag, f"{tag}-amd64", f"{tag}-arm64"]
            if self.latest_tag:
                listed.append("latest")
            return httpx.Response(200, json={"name": REPO, "tags": listed})

        if path.startswith(f"/v2/{REPO}/manifests/"):
            ref = path.rsplit("/", 1)[1]
            if ref.startswith("sha256:plat-"):
                tag = ref.removeprefix("sha256:plat-")
                return httpx.Response(
                    200,
                    json={
                        "mediaType": "application/vnd.oci.image.manifest.v1+json",
                        "config": {"digest": f"sha256:cfg-{tag}"},
                    },
                )
            tag = self.latest_tag if ref == "latest" else ref
            return httpx.Response(
                200,
                headers={"Docker-Content-Digest": f"sha256:idx-{tag}"},
                json={
                    "mediaType": "application/vnd.oci.image.index.v1+json",
                    "manifests": [
                        {
                            "digest": "sha256:attestation",
                            "platform": {"os": "unknown", "architecture": "unknown"},
                        },
                        {
                            "digest": f"sha256:plat-{tag}",
                            "platform": {"os": "linux", "architecture": "amd64"},
                        },
                    ],
                },
            )

        if path.startswith(f"/v2/{REPO}/blobs/sha256:cfg-"):
            tag = path.rsplit("sha256:cfg-", 1)[1]
            if tag in self.broken_blobs:
                return httpx.Response(500)
            return httpx.Response(
                200,
                json={
                    "created": self.tags[tag],
                    "config": {"Labels": {REVISION_LABEL: f"{tag}fullsha"}},
                },
            )

        raise AssertionError(f"unexpected path {path}")


def make_handler(fake: FakeRegistry) -> ImageHandler:
    client = ImageRegistryClient(REGISTRY, REPO)
    client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        base_url=f"https://{REGISTRY}", transport=httpx.MockTransport(fake)
    )
    return ImageHandler(client)


async def test_lists_newest_first_with_limit():
    handler = make_handler(FakeRegistry(TAGS))
    images = await handler.list_images(limit=5)

    assert [i.tag for i in images] == [
        "2fa954d",
        "cba1f4c",
        "d86118a",
        "13db2b3",
        "ebb4ba3",
    ]
    assert images[0].revision == "2fa954dfullsha"
    # Arch-suffixed tags and 'latest' never appear as entries.
    assert all("-" not in i.tag and i.tag != "latest" for i in images)


async def test_latest_flag_marks_matching_tag():
    handler = make_handler(FakeRegistry(TAGS, latest_tag="2fa954d"))
    images = await handler.list_images(limit=5)
    assert [i.tag for i in images if i.is_latest] == ["2fa954d"]


async def test_no_latest_tag_means_no_flag():
    handler = make_handler(FakeRegistry(TAGS, latest_tag=None))
    images = await handler.list_images(limit=5)
    assert not any(i.is_latest for i in images)


async def test_second_call_is_served_from_cache():
    fake = FakeRegistry(TAGS)
    handler = make_handler(fake)
    await handler.list_images(limit=5)
    request_count = len(fake.requests)

    await handler.list_images(limit=3)
    assert len(fake.requests) == request_count


async def test_expired_refresh_only_resolves_new_tags():
    fake = FakeRegistry(TAGS)
    handler = make_handler(fake)
    await handler.list_images(limit=5)

    fake.tags["a1b2c3d"] = "2026-07-20T00:00:00Z"
    fake.requests.clear()
    handler._expires_at = 0.0  # force the TTL to lapse
    images = await handler.list_images(limit=5)

    assert images[0].tag == "a1b2c3d"
    manifest_fetches = [p for p in fake.requests if "/manifests/" in p]
    # New tag's index+platform, plus re-resolving where 'latest' points.
    assert sorted(manifest_fetches) == sorted(
        [
            f"/v2/{REPO}/manifests/a1b2c3d",
            f"/v2/{REPO}/manifests/sha256:plat-a1b2c3d",
            f"/v2/{REPO}/manifests/latest",
        ]
    )


async def test_registry_down_with_no_cache_is_502():
    fake = FakeRegistry(TAGS)
    fake.down = True
    handler = make_handler(fake)
    with pytest.raises(HTTPException) as exc:
        await handler.list_images(limit=5)
    assert exc.value.status_code == 502


async def test_registry_down_after_success_serves_stale():
    fake = FakeRegistry(TAGS)
    handler = make_handler(fake)
    first = await handler.list_images(limit=5)

    fake.down = True
    handler._expires_at = 0.0
    stale = await handler.list_images(limit=5)
    assert [i.tag for i in stale] == [i.tag for i in first]


async def test_unresolvable_tag_is_skipped():
    fake = FakeRegistry(TAGS)
    fake.broken_blobs.add("d86118a")
    handler = make_handler(fake)
    images = await handler.list_images(limit=10)

    tags = [i.tag for i in images]
    assert "d86118a" not in tags
    assert len(tags) == len(TAGS) - 1


async def test_memo_reuse_returns_identical_objects():
    fake = FakeRegistry(TAGS)
    handler = make_handler(fake)
    await handler.list_images(limit=5)
    memo_before = dict(handler._memo)

    handler._expires_at = 0.0
    await handler.list_images(limit=5)
    for tag, image in memo_before.items():
        assert isinstance(image, ResolvedImage)
        assert handler._memo[tag] is image
