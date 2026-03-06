"""ChromaDB provisioner implementation."""

import asyncio
import os
import signal
import sys
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

        # Recover from corrupted (0-byte) database before anything else
        await cls._verify_database_integrity(data_path)

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
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if proc.pid is None:
            raise RuntimeError("Failed to start ChromaDB server: no PID returned")

        # Save PID for later management (async write)
        await pid_file.write_text(str(proc.pid))

        logger.info(f"Started ChromaDB server with PID {proc.pid}")

        # Log subprocess output in background for debugging
        async def _log_stream(stream: asyncio.StreamReader, level: str) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if level == "err":
                    logger.warning(f"[chromadb] {text}")
                else:
                    logger.debug(f"[chromadb] {text}")

        if proc.stdout:
            asyncio.create_task(_log_stream(proc.stdout, "out"))
        if proc.stderr:
            asyncio.create_task(_log_stream(proc.stderr, "err"))

        # Wait for health — clean up on any startup failure
        try:
            await cls._wait_for_healthy(http_port, proc=proc)
        except (TimeoutError, RuntimeError):
            logger.error(f"ChromaDB process {proc.pid} failed to start, cleaning up")
            await cls.stop({"pid": proc.pid, "pid_file": str(pid_file)})
            raise

        # Final liveness check: ensure our child is still the one serving
        if proc.returncode is not None:
            await cls.stop({"pid": proc.pid, "pid_file": str(pid_file)})
            raise RuntimeError(
                f"ChromaDB process {proc.pid} exited (code {proc.returncode}) "
                "after passing health check — another process may hold the port"
            )

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

                # Poll for graceful exit (up to 10s) to avoid SIGKILL corruption
                for _ in range(20):  # 20 * 0.5s = 10s
                    await asyncio.sleep(0.5)
                    if not await cls._is_process_running(pid):
                        logger.info(f"ChromaDB process {pid} stopped gracefully")
                        break
                else:
                    # Still running after 10s — force kill as last resort
                    os.kill(
                        pid,
                        signal.SIGKILL if sys.platform != "win32" else signal.SIGTERM,
                    )
                    logger.warning(f"Force killed ChromaDB process {pid} after 10s")

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
    async def _verify_database_integrity(cls, data_path: AsyncPath) -> None:
        """Delete ChromaDB's internal database if it is 0 bytes (corrupted).

        A 0-byte ``chroma.sqlite3`` is produced when the process is killed
        mid-write (e.g. by process-wick SIGKILL).  ChromaDB cannot recover
        from this on its own and will fail with "no such table: tenants".
        Removing the file lets ChromaDB recreate it on the next start.
        """
        db_file = data_path / "chroma.sqlite3"
        if await db_file.exists():
            stat = await db_file.stat()
            if stat.st_size == 0:
                logger.warning(
                    "Detected 0-byte chroma.sqlite3 — deleting corrupted database"
                )
                await db_file.unlink()

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
    async def _wait_for_healthy(
        cls,
        http_port: int,
        timeout: float = 60.0,
        proc: asyncio.subprocess.Process | None = None,
    ) -> None:
        """Wait for ChromaDB to be healthy.

        Args:
            http_port: HTTP port to check
            timeout: Timeout in seconds
            proc: Optional subprocess to monitor for early exit

        Raises:
            TimeoutError: If not healthy within timeout
            RuntimeError: If the subprocess exits before becoming healthy
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Fail fast if the child process already exited
            if proc is not None and proc.returncode is not None:
                raise RuntimeError(
                    f"ChromaDB process exited with code {proc.returncode} "
                    "before becoming healthy"
                )
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
