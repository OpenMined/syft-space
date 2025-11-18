"""Weaviate provisioner implementation."""

import subprocess
import time
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from syftai_space.components.dataset_types.interfaces import BaseDatasetTypeProvisioner


class WeaviateProvisioner(BaseDatasetTypeProvisioner):
    """Provisioner for Weaviate - manages Docker container lifecycle.

    All methods are classmethods. State is tracked via Docker container names.
    """

    NAME = "weaviate_local"

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        return cls.NAME

    @classmethod
    def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start Weaviate Docker container.

        Args:
            config: Configuration dictionary with httpPort, grpcPort, etc.

        Returns:
            State dict with container_name, http_port, grpc_port for re-discovery
        """
        # Extract config
        http_port = config.get("httpPort", 8080)
        grpc_port = config.get("grpcPort", 50051)
        query_limit = config.get("queryLimit", 10)
        dataset_name = config.get("dataset_name", "default")

        # Use dataset name to create unique container name
        # Convert to lowercase to comply with Docker Compose naming requirements
        container_name = f"weaviate-{dataset_name}".lower()

        # Setup environment for docker-compose
        cls._setup_environment(http_port, grpc_port, query_limit)

        docker_compose_file = Path(__file__).parent / "docker-compose.yml"

        # Start container with unique name
        cmd = cls._get_docker_compose_command() + [
            "-f",
            str(docker_compose_file),
            "-p",
            container_name,  # Project name becomes container prefix
            "up",
            "-d",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Weaviate container: {e.stderr}")
            raise RuntimeError(f"Failed to start Weaviate container: {e.stderr}") from e

        logger.info(f"Started Weaviate container '{container_name}': {result.stdout}")

        # Wait for health
        cls._wait_for_healthy(http_port)

        # Return state for persistence
        return {
            "container_name": container_name,
            "http_port": http_port,
            "grpc_port": grpc_port,
            "docker_compose_file": str(docker_compose_file),
        }

    @classmethod
    def stop(cls, state: dict[str, Any]) -> None:
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

        cmd = cls._get_docker_compose_command() + [
            "-f",
            docker_compose_file,
            "-p",
            container_name,
            "down",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info(f"Stopped Weaviate container '{container_name}'")
        else:
            logger.error(f"Failed to stop container: {result.stderr}")

    @classmethod
    def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if Weaviate container is running.

        Args:
            state: State dict from start()

        Returns:
            True if running, False otherwise
        """
        container_name = state.get("container_name")
        if not container_name:
            return False

        # Check via docker ps
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return container_name in result.stdout
        except Exception as e:
            logger.error(f"Error checking if running: {e}")
            return False

    @classmethod
    def status(cls, state: dict[str, Any]) -> str:
        """Get status of Weaviate container.

        Args:
            state: State dict from start()

        Returns:
            Status: "running", "stopped", "starting", "healthy"
        """
        if not cls.is_running(state):
            return "stopped"

        # Check health
        http_port = state.get("http_port", 8080)
        if cls._check_health(http_port):
            return "healthy"
        else:
            return "starting"

    @classmethod
    def _wait_for_healthy(cls, http_port: int, timeout: int = 60) -> None:
        """Wait for Weaviate to be healthy.

        Args:
            http_port: HTTP port to check
            timeout: Timeout in seconds

        Raises:
            TimeoutError: If not healthy within timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if cls._check_health(http_port):
                logger.info("Weaviate is healthy")
                return
            time.sleep(2)

        raise TimeoutError(f"Weaviate not healthy within {timeout}s")

    @classmethod
    def _check_health(cls, http_port: int) -> bool:
        """Check if Weaviate is healthy.

        Args:
            http_port: HTTP port to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"http://localhost:{http_port}/v1/.well-known/ready", timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False

    @classmethod
    def _setup_environment(
        cls, http_port: int, grpc_port: int, query_limit: int
    ) -> None:
        """Setup environment variables for docker-compose.

        Args:
            http_port: HTTP port
            grpc_port: gRPC port
            query_limit: Query limit
        """
        import os

        os.environ["WEAVIATE_PORT"] = str(http_port)
        os.environ["WEAVIATE_GRPC_PORT"] = str(grpc_port)
        os.environ["QUERY_DEFAULTS_LIMIT"] = str(query_limit)

    @classmethod
    def _get_docker_compose_command(cls) -> list[str]:
        """Get docker compose command (handles v1 and v2).

        Returns:
            List of command parts
        """
        try:
            subprocess.run(
                ["docker", "compose", "version"], capture_output=True, check=True
            )
            return ["docker", "compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ["docker-compose"]
