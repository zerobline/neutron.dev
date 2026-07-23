"""Ephemeral Next.js preview runtimes for generated projects.

Starts `npm install` then `next dev` in the project directory and tracks
status/logs so the workspace can iframe the live URL.
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.config import settings

logger = logging.getLogger("uvicorn.error")

RuntimeStatus = Literal[
    "idle",
    "installing",
    "starting",
    "ready",
    "error",
    "stopped",
]

_LOG_LIMIT = 200
_INSTALL_TIMEOUT_S = 600
_READY_TIMEOUT_S = 120
_HEALTH_INTERVAL_S = 0.75
_HEARTBEAT_S = 5.0

# Common Node install locations (Docker image, Windows, nvm, fnm, etc.)
_NODE_CANDIDATE_DIRS = (
    "/usr/local/bin",
    "/usr/bin",
    r"C:\Program Files\nodejs",
    r"C:\Program Files (x86)\nodejs",
)


@dataclass
class RuntimeState:
    project_id: str
    status: RuntimeStatus = "idle"
    port: int | None = None
    url: str | None = None
    message: str = ""
    logs: list[str] = field(default_factory=list)
    process: subprocess.Popen | None = None
    thread: threading.Thread | None = None
    stop_requested: bool = False
    updated_at: float = field(default_factory=time.time)

    def append_log(self, line: str) -> None:
        text = (line or "").rstrip()
        if not text:
            return
        # Strip common ANSI noise so logs stay readable in the UI.
        if "\x1b" in text:
            cleaned: list[str] = []
            i = 0
            while i < len(text):
                if text[i] == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
                    i += 2
                    while i < len(text) and text[i] not in "ABCDEFGHJKSTfminsulh":
                        i += 1
                    i += 1
                    continue
                cleaned.append(text[i])
                i += 1
            text = "".join(cleaned).strip()
            if not text:
                return
        self.logs.append(text)
        if len(self.logs) > _LOG_LIMIT:
            self.logs = self.logs[-_LOG_LIMIT:]
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "port": self.port,
            "url": self.url,
            "message": self.message,
            "logs": list(self.logs[-40:]),
            "updated_at": self.updated_at,
        }


class ProjectRuntimeManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runtimes: dict[str, RuntimeState] = {}

    def get_status(self, project_id: str) -> dict:
        with self._lock:
            state = self._runtimes.get(project_id)
            if not state:
                return {
                    "project_id": project_id,
                    "status": "idle",
                    "port": None,
                    "url": None,
                    "message": "Preview runtime not started.",
                    "logs": [],
                    "updated_at": time.time(),
                }
            return state.to_dict()

    def start(self, project_id: str) -> dict:
        project_dir = settings.projects_dir / project_id
        package_json = project_dir / "package.json"
        if not package_json.is_file():
            raise FileNotFoundError(
                "No package.json found. Generate a Next.js project first."
            )

        with self._lock:
            existing = self._runtimes.get(project_id)
            if existing and existing.status in {"installing", "starting", "ready"}:
                # Reuse a live runtime; if the worker thread died, allow restart.
                thread = existing.thread
                alive = bool(thread and thread.is_alive())
                proc = existing.process
                proc_alive = bool(proc and proc.poll() is None)
                if alive or (existing.status == "ready" and proc_alive):
                    return existing.to_dict()
                existing.stop_requested = True

            port = self._allocate_port(project_id)
            state = RuntimeState(
                project_id=project_id,
                status="installing",
                port=port,
                url=self._public_url(port),
                message="Installing npm dependencies…",
            )
            self._runtimes[project_id] = state
            thread = threading.Thread(
                target=self._run_lifecycle,
                args=(project_id, project_dir, port),
                daemon=True,
                name=f"next-runtime-{project_id[:8]}",
            )
            state.thread = thread
            thread.start()
            return state.to_dict()

    def stop(self, project_id: str) -> dict:
        with self._lock:
            state = self._runtimes.get(project_id)
            if not state:
                # Do not call get_status() while holding the lock (non-reentrant).
                return {
                    "project_id": project_id,
                    "status": "idle",
                    "port": None,
                    "url": None,
                    "message": "Preview runtime not started.",
                    "logs": [],
                    "updated_at": time.time(),
                }
            state.stop_requested = True
            proc = state.process
            state.message = "Stopping preview…"
            state.status = "stopped"
            state.updated_at = time.time()

        if proc and proc.poll() is None:
            self._terminate_process(proc)

        with self._lock:
            state = self._runtimes.get(project_id)
            if state:
                state.process = None
                state.url = None
                state.port = None
                state.message = "Preview stopped."
                state.status = "stopped"
                state.updated_at = time.time()
                return state.to_dict()
        return self.get_status(project_id)

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._runtimes.keys())
        for project_id in ids:
            try:
                self.stop(project_id)
            except Exception:
                logger.exception("Failed to stop runtime for %s", project_id)

    def _port_base(self) -> int:
        return max(1024, int(getattr(settings, "runtime_port_base", 3100) or 3100))

    def _port_span(self) -> int:
        return max(1, min(500, int(getattr(settings, "runtime_port_span", 50) or 50)))

    def _bind_host(self) -> str:
        return (getattr(settings, "runtime_bind_host", None) or "127.0.0.1").strip() or "127.0.0.1"

    def _public_host(self) -> str:
        return (getattr(settings, "runtime_public_host", None) or "127.0.0.1").strip() or "127.0.0.1"

    def _public_url(self, port: int) -> str:
        return f"http://{self._public_host()}:{port}"

    def _allocate_port(self, project_id: str) -> int:
        base = self._port_base()
        span = self._port_span()
        digest = sum(ord(c) for c in project_id) % span
        for offset in range(span):
            port = base + ((digest + offset) % span)
            if self._port_free(port):
                return port
        raise RuntimeError(
            f"No free ports available for Next.js preview "
            f"(tried {base}-{base + span - 1})."
        )

    def _port_free(self, port: int) -> bool:
        bind_host = self._bind_host()
        # When binding 0.0.0.0, still probe on all interfaces.
        hosts = ["0.0.0.0"] if bind_host in {"0.0.0.0", "::"} else [bind_host, "127.0.0.1"]
        for host in hosts:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((host, port))
                except OSError:
                    return False
        return True

    def _run_lifecycle(self, project_id: str, project_dir: Path, port: int) -> None:
        try:
            self._set_status(project_id, "installing", "Installing npm dependencies…")
            self._run_npm_install(project_id, project_dir)
            if self._is_stop_requested(project_id):
                self._set_status(project_id, "stopped", "Preview stopped.")
                return

            self._set_status(project_id, "starting", f"Starting Next.js on port {port}…")
            proc = self._start_next_dev(project_id, project_dir, port)
            with self._lock:
                state = self._runtimes.get(project_id)
                if state:
                    state.process = proc

            ready = self._wait_until_ready(project_id, port, proc)
            if self._is_stop_requested(project_id):
                self._terminate_process(proc)
                self._set_status(project_id, "stopped", "Preview stopped.")
                return
            if not ready:
                code = proc.poll()
                tail = self._recent_logs(project_id, 3)
                detail = f" Next log: {tail}" if tail else ""
                self._set_status(
                    project_id,
                    "error",
                    f"Next.js failed to become ready (exit={code}).{detail}",
                )
                self._terminate_process(proc)
                return

            public = self._public_url(port)
            self._set_status(
                project_id,
                "ready",
                f"Preview ready at {public}",
                url=public,
                port=port,
            )

            # Keep watching process until exit/stop.
            while proc.poll() is None:
                if self._is_stop_requested(project_id):
                    self._terminate_process(proc)
                    self._set_status(project_id, "stopped", "Preview stopped.")
                    return
                time.sleep(0.5)

            if not self._is_stop_requested(project_id):
                tail = self._recent_logs(project_id, 2)
                detail = f" {tail}" if tail else ""
                self._set_status(
                    project_id,
                    "error",
                    f"Next.js process exited (code={proc.returncode}).{detail}",
                )
        except FileNotFoundError as exc:
            self._set_status(project_id, "error", str(exc))
        except Exception as exc:
            logger.exception("Next.js runtime failed for %s", project_id)
            self._set_status(project_id, "error", f"Preview failed: {exc}")

    def _run_npm_install(self, project_id: str, project_dir: Path) -> None:
        # Skip install if node_modules already present and next is available.
        if self._next_entry(project_dir) is not None:
            self._append_log(project_id, "Dependencies present — skipping npm install")
            return

        node_modules = project_dir / "node_modules"
        if node_modules.is_dir() and any(node_modules.iterdir()):
            # Partial install without next binary — reinstall.
            self._append_log(
                project_id,
                "node_modules present but Next.js binary missing — running npm install",
            )

        cmd = self._npm_command(
            "install",
            "--no-fund",
            "--no-audit",
            "--prefer-offline",
            "--progress=false",
            "--loglevel=info",
        )
        self._append_log(project_id, f"$ {' '.join(cmd)}")
        self._set_status(
            project_id,
            "installing",
            "Running npm install (first run can take 1–3 minutes)…",
        )

        proc = self._popen(cmd, project_dir)
        with self._lock:
            state = self._runtimes.get(project_id)
            if state:
                state.process = proc

        self._pump_until_done(project_id, proc, timeout_s=_INSTALL_TIMEOUT_S, phase="npm install")

        if self._is_stop_requested(project_id):
            raise RuntimeError("Install cancelled.")
        if proc.returncode not in (0, None):
            raise RuntimeError(f"npm install failed with exit code {proc.returncode}")
        if self._next_entry(project_dir) is None:
            raise RuntimeError(
                "npm install finished but Next.js was not found. "
                "Ensure package.json lists next/react/react-dom dependencies."
            )
        self._append_log(project_id, "npm install finished")

    def _start_next_dev(self, project_id: str, project_dir: Path, port: int) -> subprocess.Popen:
        entry = self._next_entry(project_dir)
        # 0.0.0.0 is required in Docker so published host ports can reach Next.
        hostname = self._bind_host()
        dev_args = ["dev", "--hostname", hostname, "--port", str(port)]
        if entry is not None:
            cmd = [*entry, *dev_args]
        else:
            cmd = self._npm_command("run", "dev", "--", "--hostname", hostname, "--port", str(port))

        self._append_log(project_id, f"$ {' '.join(cmd)}")
        proc = self._popen(cmd, project_dir)

        def _pump() -> None:
            self._stream_output(project_id, proc)

        threading.Thread(target=_pump, daemon=True, name=f"next-log-{project_id[:8]}").start()
        return proc

    def _wait_until_ready(self, project_id: str, port: int, proc: subprocess.Popen) -> bool:
        deadline = time.time() + _READY_TIMEOUT_S
        last_heartbeat = 0.0
        while time.time() < deadline:
            if self._is_stop_requested(project_id):
                return False
            if proc.poll() is not None:
                return False
            if self._http_ready(port):
                return True
            now = time.time()
            if now - last_heartbeat >= _HEARTBEAT_S:
                remaining = int(deadline - now)
                self._set_status(
                    project_id,
                    "starting",
                    f"Waiting for Next.js on port {port}… ({remaining}s left)",
                )
                last_heartbeat = now
            time.sleep(_HEALTH_INTERVAL_S)
        return False

    @staticmethod
    def _http_ready(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    def _pump_until_done(
        self,
        project_id: str,
        proc: subprocess.Popen,
        *,
        timeout_s: float,
        phase: str,
    ) -> None:
        """Drain stdout while process runs; emit heartbeats when quiet."""
        assert proc.stdout is not None
        done = threading.Event()

        def _reader() -> None:
            try:
                self._stream_output(project_id, proc)
            finally:
                done.set()

        reader = threading.Thread(
            target=_reader,
            daemon=True,
            name=f"npm-log-{project_id[:8]}",
        )
        reader.start()

        deadline = time.time() + timeout_s
        last_heartbeat = time.time()
        last_log_count = 0
        while True:
            if self._is_stop_requested(project_id):
                self._terminate_process(proc)
                done.wait(timeout=2)
                return
            if proc.poll() is not None and done.wait(timeout=0.2):
                return
            if time.time() > deadline:
                self._terminate_process(proc)
                done.wait(timeout=2)
                raise RuntimeError(f"{phase} timed out after {int(timeout_s)}s.")

            now = time.time()
            log_count = self._log_count(project_id)
            if log_count != last_log_count:
                last_log_count = log_count
                last_heartbeat = now
            elif now - last_heartbeat >= _HEARTBEAT_S:
                elapsed = int(now - (deadline - timeout_s))
                self._set_status(
                    project_id,
                    "installing",
                    f"{phase} still running… {elapsed}s elapsed",
                )
                self._append_log(project_id, f"… still working ({elapsed}s)")
                last_heartbeat = now
            time.sleep(0.2)

    def _stream_output(self, project_id: str, proc: subprocess.Popen) -> None:
        if not proc.stdout:
            return
        try:
            for line in proc.stdout:
                self._append_log(project_id, line)
        except Exception:
            logger.debug("Log stream ended for %s", project_id, exc_info=True)

    def _log_count(self, project_id: str) -> int:
        with self._lock:
            state = self._runtimes.get(project_id)
            return len(state.logs) if state else 0

    def _recent_logs(self, project_id: str, n: int) -> str:
        with self._lock:
            state = self._runtimes.get(project_id)
            if not state or not state.logs:
                return ""
            return " | ".join(state.logs[-n:])

    def _set_status(
        self,
        project_id: str,
        status: RuntimeStatus,
        message: str,
        *,
        url: str | None = None,
        port: int | None = None,
    ) -> None:
        with self._lock:
            state = self._runtimes.get(project_id)
            if not state:
                return
            state.status = status
            state.message = message
            if url is not None:
                state.url = url
            if port is not None:
                state.port = port
            state.updated_at = time.time()

    def _append_log(self, project_id: str, line: str) -> None:
        with self._lock:
            state = self._runtimes.get(project_id)
            if state:
                state.append_log(line)

    def _is_stop_requested(self, project_id: str) -> bool:
        with self._lock:
            state = self._runtimes.get(project_id)
            return bool(state and state.stop_requested)

    @staticmethod
    def _resolve_binary(names: tuple[str, ...]) -> str | None:
        """Find an executable on PATH, then in common install locations."""
        for name in names:
            found = shutil.which(name)
            if found:
                return found

        # Docker / bare installs often put node in /usr/local/bin but a
        # minimal PATH (IDE, systemd, stripped container) can miss it.
        extra_dirs: list[str] = list(_NODE_CANDIDATE_DIRS)
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            extra_dirs.append(str(Path(local_app) / "Programs" / "nodejs"))
        # nvm-windows symlink folder
        appdata = os.environ.get("APPDATA")
        if appdata:
            extra_dirs.append(str(Path(appdata) / "nvm"))
        # Explicit overrides for Docker/custom images
        for key in ("NODE_BIN_DIR", "NPM_DIR"):
            value = os.environ.get(key)
            if value:
                extra_dirs.insert(0, value)

        for directory in extra_dirs:
            root = Path(directory)
            if not root.is_dir():
                continue
            for name in names:
                candidate = root / name
                if candidate.is_file():
                    return str(candidate)
        return None

    @classmethod
    def _npm_executable(cls) -> str:
        npm = cls._resolve_binary(("npm", "npm.cmd", "npm.CMD"))
        if not npm:
            raise FileNotFoundError(
                "npm was not found on PATH. "
                "Install Node.js in the backend environment "
                "(Docker: rebuild the backend image — it includes Node 22)."
            )
        return npm

    @classmethod
    def _node_executable(cls) -> str | None:
        return cls._resolve_binary(("node", "node.exe"))

    def _npm_command(self, *args: str) -> list[str]:
        npm = self._npm_executable()
        # Call npm directly. On Windows, CreateProcess can run .cmd via PATHEXT
        # when the full path is provided (verified with npm.CMD). Avoid wrapping
        # in cmd /c — list2cmdline quoting breaks paths with spaces.
        return [npm, *args]

    @staticmethod
    def _next_entry(project_dir: Path) -> list[str] | None:
        """Return full argv to run the local Next.js CLI, or None if missing."""
        node = ProjectRuntimeManager._node_executable()
        js_entry = project_dir / "node_modules" / "next" / "dist" / "bin" / "next"
        if node and js_entry.is_file():
            return [node, str(js_entry)]

        if os.name == "nt":
            cmd_bin = project_dir / "node_modules" / ".bin" / "next.cmd"
            if cmd_bin.is_file():
                return [str(cmd_bin)]
        else:
            bin_path = project_dir / "node_modules" / ".bin" / "next"
            if bin_path.is_file():
                return [str(bin_path)]
        return None

    def _popen(self, cmd: list[str], project_dir: Path) -> subprocess.Popen:
        kwargs: dict = {
            "cwd": str(project_dir),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "env": self._child_env(),
            "shell": False,
        }
        if os.name == "nt":
            # Avoid flashing console windows.
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            kwargs["creationflags"] = creationflags
            kwargs["close_fds"] = False
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **kwargs)

    @classmethod
    def _child_env(cls) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("BROWSER", "none")
        env.setdefault("CI", "1")
        env.setdefault("FORCE_COLOR", "0")
        env.setdefault("NPM_CONFIG_FUND", "false")
        env.setdefault("NPM_CONFIG_AUDIT", "false")
        env.setdefault("NPM_CONFIG_PROGRESS", "false")
        # Avoid Next asking for telemetry
        env.setdefault("NEXT_TELEMETRY_DISABLED", "1")
        # Ensure PATH has node/npm for scripts and shims (critical in Docker).
        path_parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        for binary in (cls._node_executable(), cls._resolve_binary(("npm", "npm.cmd", "npm.CMD"))):
            if not binary:
                continue
            directory = str(Path(binary).parent)
            if directory not in path_parts:
                path_parts.insert(0, directory)
        for extra in ("/usr/local/bin", "/usr/bin"):
            if Path(extra).is_dir() and extra not in path_parts:
                path_parts.append(extra)
        env["PATH"] = os.pathsep.join(path_parts)
        return env

    @staticmethod
    def _terminate_process(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                # Kill the whole tree (npm/cmd → node children).
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        timeout=10,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except Exception:
                    proc.kill()
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


runtime_manager = ProjectRuntimeManager()
