"""Mock provisioner — no Kubernetes required.

A stub for fast API/UI development and the test suite: it fakes provisioning
without touching a cluster. The real work is done by K8sProvisioner.
"""

import asyncio

from loguru import logger

from syft_station.components.provision.interfaces import (
    ProvisionError,
    SpaceRuntimeStatus,
    SpaceSpec,
)

_PROVISION_DELAY_SECONDS = 1.0


class MockProvisioner:
    """Pretends to provision. Subdomains containing "fail" fail, so the
    FAILED → retry path stays exercisable without a cluster (same trigger
    the frontend prototype uses). Pause state is tracked in-memory so the
    runtime-status read behaves plausibly for UI development."""

    def __init__(self):
        self._paused: set[str] = set()

    async def provision(self, spec: SpaceSpec) -> str:
        logger.info(f"[mock] provisioning space '{spec.subdomain}'")
        await asyncio.sleep(_PROVISION_DELAY_SECONDS)
        if "fail" in spec.subdomain:
            raise ProvisionError("mock provisioner: subdomain contains 'fail'")
        return f"https://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        logger.info(f"[mock] deprovisioning space '{subdomain}' (purge={purge})")
        self._paused.discard(subdomain)

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        logger.info(f"[mock] updating secret of '{subdomain}': {sorted(data)}")

    async def restart(self, subdomain: str) -> None:
        logger.info(f"[mock] restarting space '{subdomain}'")

    async def pause(self, subdomain: str) -> None:
        logger.info(f"[mock] pausing space '{subdomain}'")
        self._paused.add(subdomain)

    async def resume(self, subdomain: str) -> None:
        logger.info(f"[mock] resuming space '{subdomain}'")
        self._paused.discard(subdomain)

    async def get_status(self, subdomain: str) -> SpaceRuntimeStatus:
        if subdomain in self._paused:
            return SpaceRuntimeStatus.PAUSED
        return SpaceRuntimeStatus.RUNNING

    async def logs(self, subdomain: str, tail_lines: int) -> str:
        """A few canned lines so the log viewer has something to show without
        a cluster; empty while paused, like a pod that isn't running."""
        if subdomain in self._paused:
            return ""
        sample = [
            "2026-08-11T10:00:00Z INFO   uvicorn      Application startup complete",
            f"2026-08-11T10:00:01Z INFO   syft         space '{subdomain}' ready",
            "2026-08-11T10:00:12Z INFO   uvicorn      GET /api/v1/health 200 2ms",
        ]
        return "\n".join(sample[-tail_lines:])
