"""Mock provisioner — no Kubernetes required.

A stub for fast API/UI development and the test suite: it fakes provisioning
without touching a cluster. The real work is done by K8sProvisioner.
"""

import asyncio

from loguru import logger

from syft_station.components.provision.interfaces import ProvisionError, SpaceSpec

_PROVISION_DELAY_SECONDS = 1.0


class MockProvisioner:
    """Pretends to provision. Subdomains containing "fail" fail, so the
    FAILED → retry path stays exercisable without a cluster (same trigger
    the frontend prototype uses)."""

    async def provision(self, spec: SpaceSpec) -> str:
        logger.info(f"[mock] provisioning space '{spec.subdomain}'")
        await asyncio.sleep(_PROVISION_DELAY_SECONDS)
        if "fail" in spec.subdomain:
            raise ProvisionError("mock provisioner: subdomain contains 'fail'")
        return f"https://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        logger.info(f"[mock] deprovisioning space '{subdomain}' (purge={purge})")
        await asyncio.sleep(0)
