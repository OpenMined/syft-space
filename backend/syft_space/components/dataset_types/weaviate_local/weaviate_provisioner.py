"""Weaviate provisioner implementation."""

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from syft_space.components.dataset_types.interfaces import BaseDatasetTypeProvisioner


class LocalFileBasedProvisioner(BaseDatasetTypeProvisioner):
    """Provisioner for Weaviate - manages Docker container lifecycle.

    All methods are classmethods. State is tracked via Docker container names.
    """

    NAME = "local_file"

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        return cls.NAME

    @classmethod
    async def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start Weaviate Docker container.

        Args:
            config: Configuration dictionary with httpPort, grpcPort, etc.

        Returns:
            State dict with container_name, http_port, grpc_port for re-discovery
        """
        # Extract config
        http_port = config.get("httpPort", 8083)
        grpc_port = config.get("grpcPort", 50051)
        query_limit = config.get("queryLimit", 10)

        # Use dtype-based container name for shared provisioner
        # All datasets of this type share the same container
        container_name = f"syft-space-{cls.NAME}".replace("_", "-")

        # Get environment variables for docker-compose (thread-safe)
        env = cls._get_environment(http_port, grpc_port, query_limit)

        docker_compose_file = Path(__file__).parent / "docker-compose.yml"

        # Start container with unique name
        cmd = await cls._get_docker_compose_command() + [
            "-f",
            str(docker_compose_file),
            "-p",
            container_name,  # Project name becomes container prefix
            "up",
            "-d",
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            logger.error(
                f"Failed to start Weaviate container: {stderr.decode('utf-8')}"
            )
            raise RuntimeError(
                f"Failed to start Weaviate container: {stderr.decode('utf-8')} -> {stdout.decode('utf-8')}"
            )

        logger.info(
            f"Started Weaviate container '{container_name}': {stdout.decode('utf-8')}"
        )

        # Wait for health
        await cls._wait_for_healthy(http_port)

        # Return state for persistence
        # Include connection fields with keys matching configuration_schema
        return {
            "container_name": container_name,
            "docker_compose_file": str(docker_compose_file),
            # Connection fields (keys match configuration_schema)
            "httpPort": http_port,
            "grpcPort": grpc_port,
            "useTLS": config.get("useTLS", False),
        }

    @classmethod
    async def stop(cls, state: dict[str, Any]) -> None:
        """Stop Weaviate container.

        Args:
            state: State dict from start()
        """
        container_name = state.get("container_name")
        if not container_name:
            logger.warning("No container_name in state, cannot stop")
            return

        docker_compose_file = state.get(
            "docker_compose_file", str(Path(__file__).parent / "docker-compose.yml")
        )

        cmd = await cls._get_docker_compose_command() + [
            "-f",
            docker_compose_file,
            "-p",
            container_name,
            "down",
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Add 30 second timeout to prevent indefinite hang during shutdown
            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=60.0,
            )
        except asyncio.TimeoutError as e:
            # Kill the process if it times out
            logger.error(
                f"Docker compose down timed out after 30s for '{container_name}': {e}"
            )
            result.kill()
            await result.wait()
            raise RuntimeError(
                f"Docker compose down timed out after 30s for '{container_name}'"
            ) from e

        if result.returncode != 0:
            logger.error(f"Failed to stop Weaviate container: {stderr.decode('utf-8')}")
            raise RuntimeError(
                f"Failed to stop Weaviate container: {stderr.decode('utf-8')}"
            )

        logger.info(
            f"Stopped Weaviate container '{container_name}': {stdout.decode('utf-8')}"
        )

    @classmethod
    async def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if Weaviate container is running.

        Args:
            state: State dict from start()

        Returns:
            True if running, False otherwise
        """
        container_name = state.get("container_name")
        if not container_name:
            return False

        proc = await asyncio.create_subprocess_exec(
            "docker",
            "ps",
            "--filter",
            f"name={container_name}",
            "--format",
            "{{.Names}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(
                f"Failed to check if container is running: {stderr.decode('utf-8')}"
            )
            return False
        return container_name in stdout.decode("utf-8").splitlines()

    @classmethod
    async def status(cls, state: dict[str, Any]) -> str:
        """Get status of Weaviate container.

        Args:
            state: State dict from start()

        Returns:
            Status: "running", "stopped", "starting", "healthy"
        """
        if not await cls.is_running(state):
            return "stopped"

        # Check health
        http_port = state.get("httpPort", 8083)
        if await cls._check_health(http_port):
            return "healthy"
        else:
            return "starting"

    @classmethod
    async def _wait_for_healthy(cls, http_port: int, timeout: float = 60.0) -> None:
        """Wait for Weaviate to be healthy.

        Args:
            http_port: HTTP port to check
            timeout: Timeout in seconds

        Raises:
            TimeoutError: If not healthy within timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await cls._check_health(http_port):
                logger.info("Weaviate is healthy")
                return
            await asyncio.sleep(2.0)

        raise TimeoutError(f"Weaviate not healthy within {timeout}s")

    @classmethod
    async def _check_health(cls, http_port: int) -> bool:
        """Check if Weaviate is healthy.

        Args:
            http_port: HTTP port to check

        Returns:
            True if healthy, False otherwise
        """
        host = cls._get_docker_host()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"http://{host}:{http_port}/v1/.well-known/ready", timeout=2
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to check Weaviate health at {host}:{http_port}: {e}")
            return False

    @classmethod
    def _get_environment(
        cls, http_port: int, grpc_port: int, query_limit: int
    ) -> dict[str, str]:
        """Get environment variables for docker-compose (thread-safe).

        Returns a copy of the current environment with Weaviate-specific variables set.
        This avoids race conditions when multiple provisioners start concurrently.

        Args:
            http_port: HTTP port
            grpc_port: gRPC port
            query_limit: Query limit

        Returns:
            Dictionary of environment variables to pass to subprocess
        """
        import os

        # Copy current environment to avoid modifying global state
        env = os.environ.copy()
        # Set Weaviate-specific variables
        env["WEAVIATE_PORT"] = str(http_port)
        env["WEAVIATE_GRPC_PORT"] = str(grpc_port)
        env["QUERY_DEFAULTS_LIMIT"] = str(query_limit)
        return env

    @classmethod
    def _get_docker_host(cls) -> str:
        """Get the Docker host address for health checks.

        Returns DOCKER_NETWORK_HOST env var if set, otherwise 'localhost'.
        This allows the code to work both locally and inside Docker containers.
        """
        import os

        return os.getenv("DOCKER_NETWORK_HOST", "localhost")

    @classmethod
    async def _get_docker_compose_command(cls) -> list[str]:
        """Get docker compose command (handles v1 and v2).

        Returns:
            List of command parts
        """
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "compose",
            "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # If failed, use docker-compose as fallback
        if proc.returncode != 0:
            logger.debug(
                f"docker compose v2 plugin not available, using docker-compose: {stderr.decode('utf-8')}"
            )
            return ["docker-compose"]

        # If successful, use docker compose
        return ["docker", "compose"]
