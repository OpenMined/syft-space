"""Cluster control plane server (scaffold).

Will provide: SyftHub sign-in proxy, space request queue, admin approval,
and k8s provisioning of syft-space instances. See /station.md at the
repo root for the full plan.
"""

from fastapi import FastAPI

app = FastAPI(title="Syft Station")


@app.get("/healthcheck")
async def healthcheck() -> dict[str, str]:
    """Liveness/readiness probe endpoint."""
    return {"status": "ok"}
