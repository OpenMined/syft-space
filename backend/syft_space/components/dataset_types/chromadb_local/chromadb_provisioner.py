"""ChromaDB provisioner implementation."""

import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

from anyio import Path as AsyncPath
from loguru import logger

from syft_space.components.dataset_types.interfaces import BaseDatasetTypeProvisioner

DEFAULT_HTTP_PORT = 8100


def _chroma_command() -> list[str]:
    """Return the base command to invoke the ``chroma`` CLI.

    Inside a PyInstaller bundle the ``chroma`` entry-point script does not
    exist on PATH.  Instead we re-invoke the frozen executable itself with a
    ``--chroma-server`` flag that is intercepted at the top of ``main.py``
    and forwarded to ``chromadb.cli.cli:app``.

    In development (unfrozen) we call ``chroma`` directly since the
    virtualenv has it on PATH.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--chroma-server"]
    return ["chroma"]


class LocalChromaDBProvisioner(BaseDatasetTypeProvisioner):
    """Provisioner for ChromaDB - manages subprocess lifecycle.

    All methods are classmethods. State is tracked via PID file.
    Uses `chroma run` command to start the server (no Docker dependency).
    """

    NAME = "local_file"

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        return cls.NAME

    @classmethod
    async def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start ChromaDB server via subprocess.

        Args:
            config: Configuration dictionary with httpPort, etc.

        Returns:
            State dict with pid, pid_file, data_path, http_port for re-discovery
        """
        # Extract config (use camelCase key from schema or snake_case)
        http_port = config.get("httpPort") or config.get("http_port", DEFAULT_HTTP_PORT)

        # Data directory for persistence (async mkdir)
        home = await AsyncPath.home()
        data_path = home / ".syft-space" / "chromadb"
        await data_path.mkdir(parents=True, exist_ok=True)

        # PID file for process tracking
        pid_file = data_path / "chromadb.pid"

        # Check if already running
        if await pid_file.exists():
            try:
                pid_content = await pid_file.read_text()
                existing_pid = int(pid_content.strip())
                if await cls._is_process_running(existing_pid):
                    # Check if it's healthy
                    if await cls._check_health(http_port):
                        logger.info(f"ChromaDB already running with PID {existing_pid}")
                        return {
                            "pid": existing_pid,
                            "pid_file": str(pid_file),
                            "data_path": str(data_path),
                            "httpPort": http_port,
                        }
                    else:
                        # Process exists but not healthy - stop it first
                        logger.warning(
                            f"ChromaDB process {existing_pid} unhealthy, stopping..."
                        )
                        await cls.stop({"pid": existing_pid, "pid_file": str(pid_file)})
                else:
                    # PID file exists but process is dead - clean up stale file
                    logger.info(
                        f"Cleaning up stale PID file (process {existing_pid} not running)"
                    )
                    await pid_file.unlink()
            except (ValueError, Exception) as e:
                logger.warning(f"Error checking existing PID: {e}")

        # Start ChromaDB server
        # chroma run --path <path> --port <port> --host 0.0.0.0
        cmd = [
            *_chroma_command(),
            "run",
            "--path",
            str(data_path),
            "--port",
            str(http_port),
            "--host",
            "0.0.0.0",
        ]
        # Use subprocess.Popen instead of asyncio.create_subprocess_exec
        # because Windows SelectorEventLoop (used by uvicorn) does not
        # support asyncio subprocess creation.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Save PID for later management (async write)
        await pid_file.write_text(str(proc.pid))

        logger.info(f"Started ChromaDB server with PID {proc.pid}")

        # Log subprocess output in background threads (not async tasks,
        # since we're using sync Popen pipes)
        def _log_stream(stream, level: str) -> None:
            for line in stream:
                text = line.decode(errors="replace").rstrip()
                if text:
                    if level == "err":
                        logger.warning(f"[chromadb] {text}")
                    else:
                        logger.debug(f"[chromadb] {text}")

        if proc.stdout:
            threading.Thread(
                target=_log_stream, args=(proc.stdout, "out"), daemon=True
            ).start()
        if proc.stderr:
            threading.Thread(
                target=_log_stream, args=(proc.stderr, "err"), daemon=True
            ).start()

        # Wait for health
        await cls._wait_for_healthy(http_port)

        return {
            "pid": proc.pid,
            "pid_file": str(pid_file),
            "data_path": str(data_path),
            "httpPort": http_port,
        }

    @classmethod
    async def stop(cls, state: dict[str, Any]) -> None:
        """Stop ChromaDB server process (async-safe).

        Args:
            state: State dict from start()
        """
        pid = state.get("pid")
        pid_file_path = state.get("pid_file")

        if pid:
            try:
                # Graceful shutdown: SIGTERM on Unix, CTRL_BREAK on Windows
                if sys.platform == "win32":
                    os.kill(pid, signal.CTRL_BREAK_EVENT)
                else:
                    os.kill(pid, signal.SIGTERM)

                # Wait for graceful shutdown
                await asyncio.sleep(2.0)

                # Check if still running, force kill if needed
                if await cls._is_process_running(pid):
                    os.kill(pid, signal.SIGKILL if sys.platform != "win32" else signal.SIGTERM)
                    logger.info(f"Force killed ChromaDB process {pid}")
                else:
                    logger.info(f"ChromaDB process {pid} stopped gracefully")

            except (OSError, ProcessLookupError):
                logger.info(f"ChromaDB process {pid} already stopped")
            except Exception as e:
                logger.warning(f"Error stopping ChromaDB process {pid}: {e}")

        # Clean up PID file (async)
        if pid_file_path:
            pid_file = AsyncPath(pid_file_path)
            if await pid_file.exists():
                await pid_file.unlink()

    @classmethod
    async def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if ChromaDB process is running.

        Uses state to re-discover the resource (important after restart).

        Args:
            state: State dict from start()

        Returns:
            True if running, False otherwise
        """
        pid = state.get("pid")
        if not pid:
            return False

        return await cls._is_process_running(pid)

    @classmethod
    async def status(cls, state: dict[str, Any]) -> str:
        """Get detailed status of ChromaDB server.

        Args:
            state: State dict from start()

        Returns:
            Status string: "running", "stopped", "starting"
        """
        if not await cls.is_running(state):
            return "stopped"

        # Check health
        http_port = state.get("httpPort", DEFAULT_HTTP_PORT)
        is_healthy = await cls._check_health(http_port)

        if is_healthy:
            return "running"
        else:
            return "starting"

    @classmethod
    async def wait_until_ready(cls, state: dict[str, Any]) -> None:
        """Wait for ChromaDB HTTP server to be healthy.

        Args:
            state: State dict from start()

        Raises:
            TimeoutError: If not healthy within 60s or no port in state
        """
        http_port = state.get("httpPort") or state.get("http_port")
        if not http_port:
            raise TimeoutError("No HTTP port in provisioner state")
        await cls._wait_for_healthy(int(http_port))

    @classmethod
    async def _is_process_running(cls, pid: int) -> bool:
        """Check if a ChromaDB process is running.

        Uses psutil to verify the PID belongs to a ChromaDB process
        (not a reused PID for something else). Falls back to basic
        os.kill check only if psutil is not installed.

        Args:
            pid: Process ID to check

        Returns:
            True if process exists and is a ChromaDB process, False otherwise
        """
        try:
            import psutil
        except ImportError:
            # psutil not available — fall back to basic PID check
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

        try:
            proc = psutil.Process(pid)
            cmdline = " ".join(proc.cmdline()).lower()
            return "chroma" in cmdline
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    @classmethod
    async def _wait_for_healthy(cls, http_port: int, timeout: float = 60.0) -> None:
        """Wait for ChromaDB to be healthy.

        Args:
            http_port: HTTP port to check
            timeout: Timeout in seconds

        Raises:
            TimeoutError: If not healthy within timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await cls._check_health(http_port):
                logger.info("ChromaDB is healthy")
                return
            await asyncio.sleep(2.0)

        raise TimeoutError(f"ChromaDB not healthy within {timeout}s")

    @classmethod
    async def _check_health(cls, http_port: int) -> bool:
        """Check if ChromaDB is healthy.

        Args:
            http_port: HTTP port to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            import chromadb
        except ImportError as exc:
            logger.warning(f"ChromaDB is not importable; health check skipped: {exc}")
            return False

        host = cls._get_host()
        try:
            client = await chromadb.AsyncHttpClient(
                host=host,
                port=http_port,
                ssl=False,
            )
            heartbeat = await client.heartbeat()
            return heartbeat is not None
        except Exception as e:
            logger.debug(f"ChromaDB health check failed at {host}:{http_port}: {e}")
            return False

    @classmethod
    def _get_host(cls) -> str:
        """Get the host address for health checks.

        Always returns 'localhost' because ChromaDB runs as a local subprocess
        within the same container/process space.
        """
        return "localhost"
