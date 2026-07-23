import threading
import time
from pathlib import Path

from app.services.project_runtime import ProjectRuntimeManager, RuntimeState


def test_get_status_idle():
    mgr = ProjectRuntimeManager()
    status = mgr.get_status("missing")
    assert status["status"] == "idle"
    assert status["url"] is None


def test_start_requires_package_json(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.project_runtime.settings.projects_dir", tmp_path)
    mgr = ProjectRuntimeManager()
    project_id = "p1"
    (tmp_path / project_id).mkdir()
    try:
        mgr.start(project_id)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "package.json" in str(exc)


def test_stop_unknown_is_safe():
    """Must not deadlock when stopping a runtime that was never started."""
    mgr = ProjectRuntimeManager()
    status = mgr.stop("nope")
    assert status["status"] in {"idle", "stopped"}
    assert status["project_id"] == "nope"


def test_runtime_state_log_trim():
    state = RuntimeState(project_id="x")
    for i in range(250):
        state.append_log(f"line {i}")
    assert len(state.logs) <= 200
    assert state.logs[-1] == "line 249"
    assert state.append_log("") is None  # empty lines ignored
    assert len(state.logs) <= 200


def test_runtime_state_strips_ansi():
    state = RuntimeState(project_id="x")
    state.append_log("\x1b[?25h\x1b[32mReady\x1b[0m")
    assert state.logs[-1] == "Ready"


def test_start_is_idempotent_while_running(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.project_runtime.settings.projects_dir", tmp_path)
    project_id = "p-idem"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

    mgr = ProjectRuntimeManager()
    started = threading.Event()
    release = threading.Event()

    def fake_lifecycle(pid, pdir, port):
        started.set()
        release.wait(timeout=5)
        mgr._set_status(pid, "ready", "ok", url=f"http://127.0.0.1:{port}", port=port)

    monkeypatch.setattr(mgr, "_run_lifecycle", fake_lifecycle)
    first = mgr.start(project_id)
    assert first["status"] == "installing"
    assert started.wait(timeout=2)

    second = mgr.start(project_id)
    assert second["status"] == "installing"
    assert second["port"] == first["port"]

    release.set()
    time.sleep(0.05)


def test_start_restarts_dead_worker(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.project_runtime.settings.projects_dir", tmp_path)
    project_id = "p-dead"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

    mgr = ProjectRuntimeManager()
    calls = {"n": 0}

    def fake_lifecycle(pid, pdir, port):
        calls["n"] += 1
        # Thread exits immediately — simulates a dead worker left in installing.

    monkeypatch.setattr(mgr, "_run_lifecycle", fake_lifecycle)
    first = mgr.start(project_id)
    time.sleep(0.05)
    second = mgr.start(project_id)
    assert first["status"] == "installing"
    assert second["status"] == "installing"
    assert calls["n"] == 2


def test_stop_all_clears_known_runtimes():
    mgr = ProjectRuntimeManager()
    with mgr._lock:
        mgr._runtimes["a"] = RuntimeState(project_id="a", status="ready", port=3100)
        mgr._runtimes["b"] = RuntimeState(project_id="b", status="starting", port=3101)
    mgr.stop_all()
    assert mgr.get_status("a")["status"] == "stopped"
    assert mgr.get_status("b")["status"] == "stopped"


def test_allocate_port_finds_free_port(monkeypatch):
    mgr = ProjectRuntimeManager()
    calls = {"n": 0}

    def fake_free(port: int) -> bool:
        calls["n"] += 1
        return port % 2 == 0

    monkeypatch.setattr(mgr, "_port_free", fake_free)
    port = mgr._allocate_port("abc")
    assert port >= 3100
    assert port % 2 == 0
    assert calls["n"] >= 1


def test_http_ready_false_when_closed():
    assert ProjectRuntimeManager._http_ready(1) is False


def test_npm_executable_missing(monkeypatch):
    monkeypatch.setattr(
        ProjectRuntimeManager,
        "_resolve_binary",
        staticmethod(lambda _names: None),
    )
    try:
        ProjectRuntimeManager._npm_executable()
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "npm" in str(exc).lower()
        assert "docker" in str(exc).lower() or "node" in str(exc).lower()


def test_resolve_binary_checks_candidate_dir(tmp_path, monkeypatch):
    npm = tmp_path / "npm"
    npm.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("app.services.project_runtime.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "app.services.project_runtime._NODE_CANDIDATE_DIRS",
        (str(tmp_path),),
    )
    found = ProjectRuntimeManager._resolve_binary(("npm",))
    assert found == str(npm)


def test_next_entry_prefers_node_js(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ProjectRuntimeManager,
        "_node_executable",
        classmethod(lambda cls: "node.exe"),
    )
    next_js = tmp_path / "node_modules" / "next" / "dist" / "bin" / "next"
    next_js.parent.mkdir(parents=True)
    next_js.write_text("// next", encoding="utf-8")
    entry = ProjectRuntimeManager._next_entry(tmp_path)
    assert entry == ["node.exe", str(next_js)]


def test_npm_command_invokes_npm_directly(monkeypatch):
    mgr = ProjectRuntimeManager()
    monkeypatch.setattr(mgr, "_npm_executable", lambda: r"C:\Program Files\nodejs\npm.CMD")
    cmd = mgr._npm_command("install", "--no-fund")
    assert cmd[0].endswith("npm.CMD")
    assert cmd[1:] == ["install", "--no-fund"]


def test_public_url_uses_settings(monkeypatch):
    monkeypatch.setattr("app.services.project_runtime.settings.runtime_public_host", "localhost")
    mgr = ProjectRuntimeManager()
    assert mgr._public_url(3123) == "http://localhost:3123"


def test_allocate_port_respects_span(monkeypatch):
    monkeypatch.setattr("app.services.project_runtime.settings.runtime_port_base", 4000)
    monkeypatch.setattr("app.services.project_runtime.settings.runtime_port_span", 3)
    mgr = ProjectRuntimeManager()
    monkeypatch.setattr(mgr, "_port_free", lambda port: port == 4002)
    assert mgr._allocate_port("x") == 4002
