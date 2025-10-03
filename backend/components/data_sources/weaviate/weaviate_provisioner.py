import asyncio
from pathlib import Path
import subprocess
from typing import Dict, Any, Optional, List
from components.data_sources.interfaces import DataSourceProvisioner
import requests
import time
from loguru import logger
from components.data_sources.interfaces import DataSourceProvisioner
from components.data_sources.registry import DATA_SOURCE_REGISTRY


class WeaviateProvisioner(DataSourceProvisioner):
    """Provisioner for Weaviate - synchronous by default."""

    SOURCE_NAME = "weaviate"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.docker_compose_file: Optional[Path] = None
        self.is_running = False

    def start(self, config: Dict[str, Any]) -> None:
        """Start the provisioner (blocking)."""
        self.config = config
        self._setup_environment(config)

        self.docker_compose_file = Path(__file__).parent / "docker-compose.yml"

        # Simple subprocess call
        cmd = self._get_docker_compose_command() + [
            "-f",
            str(self.docker_compose_file),
            "up",
            "-d",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Started Weaviate: {result.stdout}")

        self._wait_for_healthy()
        self.is_running = True

    def stop(self) -> None:
        """Stop the provisioner (blocking)."""
        if not self.docker_compose_file:
            return

        cmd = self._get_docker_compose_command() + [
            "-f",
            str(self.docker_compose_file),
            "down",
        ]

        subprocess.run(cmd, capture_output=True, check=False)
        self.is_running = False

    def status(self) -> str:
        """Get status (blocking)."""
        if not self.docker_compose_file:
            return "not_configured"

        # Check if containers are running
        cmd = self._get_docker_compose_command() + [
            "-f",
            str(self.docker_compose_file),
            "ps",
            "--format",
            "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not result.stdout.strip():
            return "stopped"

        # Check health
        return "healthy" if self._check_health() else "starting"

    def _wait_for_healthy(self, timeout: int = 60) -> None:
        """Wait for services to be healthy."""

        http_port = self.config.get("httpPort", 8080)
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._check_health():
                logger.info("Weaviate is healthy")
                return
            time.sleep(2)

        raise TimeoutError(f"Weaviate not healthy within {timeout}s")

    def _check_health(self) -> bool:
        """Check if Weaviate is healthy."""
        try:
            http_port = self.config.get("httpPort", 8080)
            response = requests.get(
                f"http://localhost:{http_port}/v1/.well-known/ready", timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def _setup_environment(self, config: Dict[str, Any]) -> None:
        """Setup environment variables for docker-compose."""
        import os

        os.environ["WEAVIATE_PORT"] = str(config.get("httpPort", 8080))
        os.environ["WEAVIATE_GRPC_PORT"] = str(config.get("grpcPort", 50051))
        os.environ["QUERY_DEFAULTS_LIMIT"] = str(config.get("queryLimit", 10))

    def _get_docker_compose_command(self) -> List[str]:
        """Get docker compose command (handles v1 and v2)."""
        try:
            subprocess.run(
                ["docker", "compose", "version"], capture_output=True, check=True
            )
            return ["docker", "compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ["docker-compose"]


DATA_SOURCE_REGISTRY.register_provisioner(WeaviateProvisioner)
