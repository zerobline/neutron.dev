import asyncio
import logging
import time
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.api.websockets.project_ws import (
    ConnectionManager,
    _emit_project_complete,
    _project_has_required_files,
    classify_build_error,
    manager,
    normalize_build_mode,
    parse_direct_agent_request,
    project_websocket,
    run_project_flow,
    server_at_build_capacity,
    validate_feedback_payload,
    websocket_origin_allowed,
)
from app.models import ProjectCreate
from app.services import auth_service, project_service
from app.crew.schemas import REQUIRED_PROJECT_FILES


@pytest.mark.parametrize(
    ("content", "requested_agent", "expected"),
    [
        ("@engineer add a pricing section", None, ("engineer", "add a pricing section", None)),
        ("  @Ravi fix mobile navigation", "engineer", ("engineer", "fix mobile navigation", None)),
        ("adjust the spacing", None, ("engineer", "adjust the spacing", None)),
        ("change the heading", "ravi", ("engineer", "change the heading", None)),
        ("@nina cut MVP scope", None, ("product_manager", "cut MVP scope", None)),
        ("@kai prioritize shipping", None, ("team_leader", "prioritize shipping", None)),
        ("@theo simplify layout", None, ("architect", "simplify layout", None)),
        ("@zara suggest metrics", None, ("data_scientist", "suggest metrics", None)),
    ],
)
def test_parse_direct_agent_request_routes_engineer_mentions(content, requested_agent, expected):
    assert parse_direct_agent_request(content, requested_agent) == expected


@pytest.mark.parametrize(
    ("content", "requested_agent", "message"),
    [
        ("@nobody change this", None, "Unknown agent mention"),
        ("@engineer", None, "Tell Ravi"),
        (123, None, "must be text"),
        ("change this", 123, "Target agent must be text"),
        ("change this", "ghost", "Unknown target agent"),
        ("@nina hello", "engineer", "do not match"),
    ],
)
def test_parse_direct_agent_request_rejects_invalid_routes(content, requested_agent, message):
    agent, request, error = parse_direct_agent_request(content, requested_agent)
    assert agent is None
    assert isinstance(request, str)
    assert message in (error or "")


@pytest.fixture
def fresh_manager():
    return ConnectionManager()


@pytest.fixture(autouse=True)
def authenticated_client(request, monkeypatch):
    if "client" in request.fixturenames:
        client = request.getfixturevalue("client")
        client.post("/api/auth/register", json={"email": "ws@example.com", "password": "password123"})
        if request.node.get_closest_marker("provider_gate"):
            return
        client.put(
            "/api/settings/provider",
            json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"},
        )


def test_classify_build_error_quota():
    result = classify_build_error(RuntimeError("You've reached your usage limit for this billing cycle"))
    assert result["category"] == "quota"
    assert "quota" in result["message"].lower()
    assert "Switch provider" in result["next_action"]


def test_classify_build_error_auth():
    result = classify_build_error(RuntimeError("Unauthorized API key"))
    assert result["category"] == "auth"
    assert "API key" in result["next_action"]


def test_classify_build_error_rate_limit():
    result = classify_build_error(RuntimeError("rate limit: too many requests"))
    assert result["category"] == "rate_limit"


def test_classify_build_error_provider_capacity():
    result = classify_build_error(
        RuntimeError(
            "litellm.MidStreamFallbackError: InternalServerError: XaiException - "
            "The model is currently at capacity due to high demand."
        )
    )
    assert result["category"] == "provider_capacity"
    assert "capacity" in result["message"].lower()
    assert "wait" in result["next_action"].lower() or "switch" in result["next_action"].lower()


def test_classify_build_error_tool_execution():
    result = classify_build_error(RuntimeError("Build finished without writing any project files. The LLM skipped tool calls and only returned text."))
    assert result["category"] == "tool_execution"
    assert "No project files were created." in result["message"]
    assert "tool calling" in result["next_action"]


def test_classify_build_error_runtime():
    result = classify_build_error(RuntimeError("boom"))
    assert result["category"] == "runtime"
    assert result["message"] == "boom"


async def test_manager_connect_and_disconnect(fresh_manager):
    ws = AsyncMock()
    await fresh_manager.connect("p1", ws)
    assert ws in fresh_manager.active["p1"]

    fresh_manager.disconnect("p1", ws)
    assert "p1" not in fresh_manager.active


async def test_manager_disconnect_keeps_other_connections(fresh_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await fresh_manager.connect("p1", ws1)
    await fresh_manager.connect("p1", ws2)

    fresh_manager.disconnect("p1", ws1)

    assert fresh_manager.active["p1"] == [ws2]


async def test_manager_has_active_connections(fresh_manager):
    ws = AsyncMock()
    assert fresh_manager.has_active_connections("p1") is False
    await fresh_manager.connect("p1", ws)
    assert fresh_manager.has_active_connections("p1") is True
    fresh_manager.disconnect("p1", ws)
    assert fresh_manager.has_active_connections("p1") is False


def test_manager_get_start_lock_returns_same_lock(fresh_manager):
    assert fresh_manager.get_start_lock("p1") is fresh_manager.get_start_lock("p1")


async def test_manager_disconnect_unknown_project(fresh_manager):
    ws = AsyncMock()
    fresh_manager.disconnect("unknown", ws)


async def test_manager_send_event(fresh_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    bad_ws = AsyncMock()
    bad_ws.send_json.side_effect = RuntimeError("boom")

    await fresh_manager.connect("p1", ws1)
    await fresh_manager.connect("p1", ws2)
    await fresh_manager.connect("p1", bad_ws)

    await fresh_manager.send_event("p1", {"type": "test"})

    ws1.send_json.assert_awaited_once_with({"type": "test"})
    ws2.send_json.assert_awaited_once_with({"type": "test"})
    bad_ws.send_json.assert_called_once_with({"type": "test"})


def test_manager_feedback_provider_lifecycle(fresh_manager):
    from app.crew.feedback import WebSocketFeedbackProvider

    provider = WebSocketFeedbackProvider()
    fresh_manager.set_feedback_provider("p1", provider)
    assert fresh_manager.get_feedback_provider("p1") is provider

    fresh_manager.remove_feedback_provider("p1")
    assert fresh_manager.get_feedback_provider("p1") is None

    # Removing again is a no-op
    fresh_manager.remove_feedback_provider("p1")


def test_manager_get_feedback_provider_missing(fresh_manager):
    assert fresh_manager.get_feedback_provider("missing") is None


async def test_manager_flow_task_lifecycle(fresh_manager):
    task = asyncio.create_task(asyncio.sleep(0))
    fresh_manager.set_flow_task("p1", task)
    assert fresh_manager.get_flow_task("p1") is task
    await task
    await asyncio.sleep(0)
    assert fresh_manager.get_flow_task("p1") is None


async def test_manager_remove_flow_task_ignores_old_task(fresh_manager):
    old_task = asyncio.create_task(asyncio.sleep(0))
    new_task = asyncio.create_task(asyncio.sleep(10))
    fresh_manager.set_flow_task("p1", new_task)

    fresh_manager._remove_flow_task("p1", old_task)

    assert fresh_manager.get_flow_task("p1") is new_task
    await old_task
    new_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await new_task


async def test_manager_cancel_flow(fresh_manager, caplog):
    task = asyncio.create_task(asyncio.sleep(10))
    fresh_manager.set_flow_task("p1", task)

    with caplog.at_level(logging.INFO):
        await fresh_manager.cancel_flow("p1")

    assert task.cancelled()
    assert "Cancelled build flow for project p1" in caplog.text


async def test_manager_cancel_flow_no_task(fresh_manager):
    await fresh_manager.cancel_flow("missing")


async def test_manager_cancel_all_flows(fresh_manager):
    task1 = asyncio.create_task(asyncio.sleep(10))
    task2 = asyncio.create_task(asyncio.sleep(10))
    fresh_manager.set_flow_task("p1", task1)
    fresh_manager.set_flow_task("p2", task2)

    await fresh_manager.cancel_all_flows()

    assert task1.cancelled()
    assert task2.cancelled()


def test_websocket_rejects_unknown_project(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/project/unknown"):
            pass
    assert exc_info.value.code == 4004


def test_websocket_rejects_cross_site_origin(client):
    owner = client.post("/api/auth/register", json={"email": "origin@example.com", "password": "password123"})
    project = client.post("/api/projects", json={"name": "Private", "description": "D"}).json()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/project/{project['id']}",
            headers={"origin": "https://evil.example"},
        ):
            pass
    assert exc_info.value.code == 4403


def test_websocket_origin_helper_allows_configured_and_non_browser_clients():
    configured = MagicMock(headers={"origin": "http://localhost:3000"})
    missing = MagicMock(headers={})
    assert websocket_origin_allowed(configured) is True
    assert websocket_origin_allowed(missing) is True


def test_websocket_accepts_query_token_when_cookie_unavailable(client):
    owner = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    token, _ = auth_service.create_session(owner.json()["id"])
    project = client.post("/api/projects", json={"name": "Private", "description": "D"}).json()
    client.cookies.clear()

    with client.websocket_connect(f"/ws/project/{project['id']}?token={token}") as ws:
        ws.send_json({"type": "message", "content": "hello"})

    messages = project_service.get_messages(project["id"])
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"


def test_websocket_rejects_unauthenticated_private_project(client):
    owner = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert owner.status_code == 201
    project = client.post("/api/projects", json={"name": "Private", "description": "D"}).json()
    client.post("/api/auth/logout")
    client.cookies.clear()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/project/{project['id']}"):
            pass
    assert exc_info.value.code == 4401


def test_websocket_rejects_wrong_owner_private_project(client):
    owner = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert owner.status_code == 201
    project = client.post("/api/projects", json={"name": "Private", "description": "D"}).json()
    client.post("/api/auth/logout")
    other = client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123"})
    assert other.status_code == 201

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/project/{project['id']}"):
            pass
    assert exc_info.value.code == 4403


def test_websocket_handles_user_message(client, caplog):
    project = client.post("/api/projects", json={"name": "WS", "description": "D"}).json()
    project_id = project["id"]

    with caplog.at_level(logging.INFO), client.websocket_connect(f"/ws/project/{project_id}") as ws:
        ws.send_json({"type": "message", "content": "hello"})

    messages = project_service.get_messages(project_id)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert f"Saving user message for project {project_id}" in caplog.text


def test_websocket_start_build_triggers_flow_team_mode(client, caplog):
    project = client.post("/api/projects", json={"name": "WS Build", "description": "Build me"}).json()
    project_id = project["id"]

    with caplog.at_level(logging.INFO), patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build a landing page"})

    mock_run.assert_awaited_once()
    assert mock_run.call_args[0][0] == project_id
    assert mock_run.call_args[0][1] == "Build a landing page"
    assert mock_run.call_args[0][2] == "team"
    assert f"Starting build for project {project_id} in team mode" in caplog.text

    updated = project_service.get_project(project_id)
    assert updated.status == "leading"
    messages = project_service.get_messages(project_id)
    assert messages[0]["role"] == "user"


def test_websocket_start_build_engineer_mode(client):
    project = client.post("/api/projects", json={"name": "WS Eng", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it", "mode": "engineer"})

    mock_run.assert_awaited_once()
    assert mock_run.call_args[0][2] == "engineer"

    updated = project_service.get_project(project_id)
    assert updated.status == "building"


def test_websocket_start_build_goal_mode(client):
    project = client.post("/api/projects", json={"name": "WS Goal", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Reach goal", "mode": "goal"})

    mock_run.assert_awaited_once()
    assert mock_run.call_args[0][2] == "goal"
    assert project_service.get_project(project_id).status == "leading"


def test_websocket_start_build_unknown_mode_falls_back_to_team(client):
    project = client.post("/api/projects", json={"name": "WS Bad", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it", "mode": "bad"})

    assert normalize_build_mode("bad") == "team"
    assert mock_run.call_args[0][2] == "team"
    assert project_service.get_project(project_id).status == "leading"


def test_websocket_start_build_persists_connector_payload(client):
    project = client.post("/api/projects", json={"name": "WS Conn", "description": "Build me"}).json()
    project_id = project["id"]
    connectors = {
        "custom_mcp_servers": [
            {
                "id": "remote",
                "name": "Remote MCP",
                "transport": "http",
                "command_or_url": "https://example.com/mcp",
                "notes": "Use specs",
            }
        ]
    }

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it", "connectors": connectors})

    passed_connectors = mock_run.call_args[0][3]
    assert passed_connectors.custom_mcp_servers[0].name == "Remote MCP"
    saved = client.get(f"/api/projects/{project_id}/connectors").json()
    assert saved["custom_mcp_servers"] == connectors["custom_mcp_servers"]
    assert saved["default_mcps"] == [
        {"key": "github", "enabled": True},
        {"key": "linear", "enabled": True},
    ]


def test_websocket_start_build_uses_description_when_no_prompt(client):
    project = client.post("/api/projects", json={"name": "WS Build", "description": "Default prompt"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build"})

    mock_run.assert_awaited_once_with(
        project_id,
        "Default prompt",
        "team",
        None,
        ANY,
        restore_from=None,
        fork_branch=None,
    )


def test_websocket_disconnect_keeps_flow_when_other_connection_remains(client):
    project = client.post("/api/projects", json={"name": "WS Multi", "description": "Build me"}).json()
    project_id = project["id"]
    hang = asyncio.Event()

    async def never_finishes(*args, **kwargs):
        await hang.wait()

    with patch("app.api.websockets.project_ws.run_project_flow", side_effect=never_finishes):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws1:
            ws1.send_json({"type": "start_build", "prompt": "one"})
            for _ in range(100):
                if manager.get_flow_task(project_id) is not None:
                    break
                time.sleep(0.01)
            assert manager.get_flow_task(project_id) is not None

            with client.websocket_connect(f"/ws/project/{project_id}") as ws2:
                assert manager.has_active_connections(project_id)

            # ws2 disconnected but ws1 still active — flow stays
            assert manager.has_active_connections(project_id)
            assert manager.get_flow_task(project_id) is not None

        # ws1 disconnected — last connection gone, flow cancelled
        hang.set()
        assert not manager.has_active_connections(project_id)


def test_websocket_disconnect_cancels_flow_when_last_connection(client):
    project = client.post("/api/projects", json={"name": "WS Cancel", "description": "Build me"}).json()
    project_id = project["id"]

    async def never_finishes(*args, **kwargs):
        await asyncio.sleep(30)

    with patch("app.api.websockets.project_ws.run_project_flow", side_effect=never_finishes):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "one"})
            for _ in range(100):
                if manager.get_flow_task(project_id) is not None:
                    break
                time.sleep(0.01)
            assert manager.get_flow_task(project_id) is not None

    # After disconnect (last connection), flow should be cancelled
    assert not manager.has_active_connections(project_id)


def test_websocket_disconnect_unblocks_pending_feedback(client):
    project = client.post("/api/projects", json={"name": "WS FB Disconnect", "description": "Build me"}).json()
    project_id = project["id"]

    from app.crew.feedback import WebSocketFeedbackProvider

    provider = MagicMock(spec=WebSocketFeedbackProvider)
    provider.has_pending = True
    manager.set_feedback_provider(project_id, provider)

    try:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            pass  # disconnect immediately

        provider.submit_feedback.assert_called_once_with("approve", "")
    finally:
        manager.remove_feedback_provider(project_id)


def test_websocket_start_build_skips_provider_check_for_legacy_projects(client, temp_db):
    client.post("/api/auth/logout")
    client.cookies.clear()
    project = project_service.create_project(ProjectCreate(name="Legacy", description="Build me"), owner_user_id=None)

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project.id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it"})

    mock_run.assert_awaited_once()


def test_websocket_start_build_rejects_unauthenticated_without_env_key(client, temp_db):
    client.post("/api/auth/logout")
    client.cookies.clear()
    project = project_service.create_project(ProjectCreate(name="NoKey", description="Build me"), owner_user_id=None)

    settings.llm_provider = "xai"
    settings.llm_model = "xai/grok-3-mini"
    settings.xai_api_key = None

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project.id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert event["category"] == "provider_not_configured"
    assert "Grok / xAI" in event["message"]
    mock_run.assert_not_called()


@pytest.mark.provider_gate
def test_websocket_start_build_rejects_unconfigured_provider(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "WS Provider", "description": "Build me"}).json()
    project_id = project["id"]

    monkeypatch.setattr(
        "app.api.websockets.project_ws.provider_settings_service.provider_ready_for_build",
        lambda _user_id: (False, "Add your OpenAI API key in Settings → Cloud & AI before starting a build."),
    )

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert event["category"] == "provider_not_configured"
    mock_run.assert_not_called()


def test_websocket_rejects_duplicate_start_build(client):
    project = client.post("/api/projects", json={"name": "WS Dupe", "description": "Build me"}).json()
    project_id = project["id"]

    async def never_finishes(*args, **kwargs):
        await asyncio.sleep(10)

    with patch("app.api.websockets.project_ws.run_project_flow", side_effect=never_finishes):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "one"})
            ws.send_json({"type": "start_build", "prompt": "two"})
            assert ws.receive_json() == {
                "type": "error",
                "message": "Build already running for this project",
            }


def test_websocket_human_feedback_with_provider(client):
    project = client.post("/api/projects", json={"name": "WS FB", "description": "D"}).json()
    project_id = project["id"]

    from app.crew.feedback import WebSocketFeedbackProvider

    provider = MagicMock(spec=WebSocketFeedbackProvider)
    provider.has_pending = True

    def clear_pending(action: str, feedback: str = ""):
        provider.has_pending = False
        return True

    provider.submit_feedback.side_effect = clear_pending
    manager.set_feedback_provider(project_id, provider)

    try:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "human_feedback", "action": "revise", "feedback": "add dark mode"})

        provider.submit_feedback.assert_called_once_with("revise", "add dark mode")
        messages = project_service.get_messages(project_id)
        assert any("[revise] add dark mode" in m["content"] for m in messages)
    finally:
        manager.remove_feedback_provider(project_id)


def test_websocket_human_feedback_no_feedback_text(client):
    project = client.post("/api/projects", json={"name": "WS FB2", "description": "D"}).json()
    project_id = project["id"]

    from app.crew.feedback import WebSocketFeedbackProvider

    provider = MagicMock(spec=WebSocketFeedbackProvider)
    provider.has_pending = True

    def clear_pending(action: str, feedback: str = ""):
        provider.has_pending = False
        return True

    provider.submit_feedback.side_effect = clear_pending
    manager.set_feedback_provider(project_id, provider)

    try:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "human_feedback", "action": "approve"})

        provider.submit_feedback.assert_called_once_with("approve", "")
        messages = project_service.get_messages(project_id)
        assert len(messages) == 0
    finally:
        manager.remove_feedback_provider(project_id)


def test_websocket_human_feedback_no_provider(client):
    project = client.post("/api/projects", json={"name": "WS FB3", "description": "D"}).json()
    project_id = project["id"]

    with client.websocket_connect(f"/ws/project/{project_id}") as ws:
        ws.send_json({"type": "human_feedback", "action": "approve"})
        event = ws.receive_json()
    assert event["type"] == "feedback_error"
    assert "No feedback request" in event["message"]


def test_validate_feedback_payload_rejects_invalid_action():
    from app.api.websockets.project_ws import validate_feedback_payload

    action, fb, err = validate_feedback_payload({"action": "bad"})
    assert action is None
    assert err and "approve" in err


def test_validate_feedback_payload_rejects_non_string_feedback():
    from app.api.websockets.project_ws import validate_feedback_payload

    action, fb, err = validate_feedback_payload({"action": "approve", "feedback": 123})
    assert action is None
    assert err and "text" in err.lower()


def test_validate_feedback_payload_rejects_empty_revise_feedback():
    from app.api.websockets.project_ws import validate_feedback_payload

    action, fb, err = validate_feedback_payload({"action": "revise", "feedback": "   "})
    assert action is None
    assert err and "empty" in err.lower()


def test_websocket_human_feedback_invalid_action_sends_error(client):
    project = client.post("/api/projects", json={"name": "WS FB BadAction", "description": "D"}).json()
    project_id = project["id"]

    with client.websocket_connect(f"/ws/project/{project_id}") as ws:
        ws.send_json({"type": "human_feedback", "action": "destroy"})
        event = ws.receive_json()
    assert event["type"] == "feedback_error"
    assert "approve" in event["message"] or "revise" in event["message"]


def test_websocket_ignores_unknown_message_type(client):
    project = client.post("/api/projects", json={"name": "WS Unknown", "description": "D"}).json()
    project_id = project["id"]

    with client.websocket_connect(f"/ws/project/{project_id}") as ws:
        ws.send_json({"type": "unknown"})
        ws.send_json({"type": "message", "content": "after unknown"})

    messages = project_service.get_messages(project_id)
    assert [message["content"] for message in messages] == ["after unknown"]


async def test_run_project_flow_success(temp_db):
    project = project_service.create_project(ProjectCreate(name="Flow", description="D"))
    fake_flow = MagicMock()
    fake_flow.kickoff_flow.return_value = None

    with patch("app.api.websockets.project_ws.ProjectCreationFlow", return_value=fake_flow) as mock_flow:
        await run_project_flow(project.id, "prompt")

    mock_flow.assert_called_once()
    call_kwargs = mock_flow.call_args.kwargs
    assert call_kwargs["project_id"] == project.id
    assert call_kwargs["user_prompt"] == "prompt"
    assert call_kwargs["mode"] == "team"
    assert call_kwargs["connector_settings"] is None
    assert callable(call_kwargs["event_callback"])
    fake_flow.kickoff_flow.assert_called_once()

    updated = project_service.get_project(project.id)
    assert updated.status == "complete"


async def test_run_project_flow_with_mode(temp_db):
    project = project_service.create_project(ProjectCreate(name="Flow Eng", description="D"))
    fake_flow = MagicMock()
    fake_flow.kickoff_flow.return_value = None

    with patch("app.api.websockets.project_ws.ProjectCreationFlow", return_value=fake_flow) as mock_flow:
        await run_project_flow(project.id, "prompt", "engineer")

    assert mock_flow.call_args.kwargs["mode"] == "engineer"


async def test_run_project_flow_normalizes_invalid_mode(temp_db):
    project = project_service.create_project(ProjectCreate(name="Flow Bad", description="D"))
    fake_flow = MagicMock()
    fake_flow.kickoff_flow.return_value = None

    with patch("app.api.websockets.project_ws.ProjectCreationFlow", return_value=fake_flow) as mock_flow:
        await run_project_flow(project.id, "prompt", "invalid")

    assert mock_flow.call_args.kwargs["mode"] == "team"


async def test_run_project_flow_emits_status_and_message(temp_db):
    project = project_service.create_project(
        ProjectCreate(name="Flow", description="D")
    )

    def make_flow(*args, **kwargs):
        instance = MagicMock()

        def kickoff_flow():
            callback = kwargs["event_callback"]
            callback({"type": "phase_start", "phase": "leading", "message": "Starting"})
            callback({"type": "phase_start", "phase": "unknown", "message": "Ignored"})
            callback({"type": "agent_complete", "agent": "team_leader", "content": "done"})
            callback({
                "type": "phase_result",
                "phase": "leading",
                "agent": "team_leader",
                "kind": "brief",
                "headline": "Scope locked",
                "summary": "A clear brief for the landing page.",
                "spec": {"mvp_inclusions": ["Hero"]},
                "has_structured_spec": True,
            })
            callback({"type": "human_feedback_request", "phase": "leading", "agent": "team_leader"})

        instance.kickoff_flow.side_effect = kickoff_flow
        return instance

    with patch("app.api.websockets.project_ws.ProjectCreationFlow", side_effect=make_flow):
        await run_project_flow(project.id, "prompt")

    updated = project_service.get_project(project.id)
    assert updated.status == "complete"
    messages = project_service.get_messages(project.id)
    phase_msgs = [
        m for m in messages
        if m["role"] == "agent" and m["agent"] == "team_leader" and m.get("kind") == "phase_result"
    ]
    assert len(phase_msgs) == 1
    assert phase_msgs[0]["content"] == "A clear brief for the landing page."
    assert phase_msgs[0]["metadata"]["headline"] == "Scope locked"
    assert phase_msgs[0]["metadata"]["kind"] == "brief"


async def test_run_project_flow_error_sets_status(temp_db):
    project = project_service.create_project(
        ProjectCreate(name="Flow Err", description="D")
    )

    with patch("app.api.websockets.project_ws.ProjectCreationFlow") as mock_flow:
        instance = mock_flow.return_value
        instance.kickoff_flow.side_effect = RuntimeError("LLM failed")

        await run_project_flow(project.id, "prompt")

        instance.kickoff_flow.assert_called_once()
        call_kwargs = mock_flow.call_args.kwargs
        assert callable(call_kwargs["event_callback"])
        call_kwargs["event_callback"]({"type": "error", "message": "LLM failed"})

    updated = project_service.get_project(project.id)
    assert updated.status == "error"


async def test_run_project_flow_recovers_to_complete_when_files_present(temp_db, monkeypatch):
    """Cover the recovery path: internal error + _project_has returns True → complete + project_complete emit."""
    project = project_service.create_project(
        ProjectCreate(name="Flow Recover", description="D")
    )

    # Force the recovery branch without needing real FS
    with patch("app.api.websockets.project_ws._project_has_required_files", return_value=True), \
         patch("app.api.websockets.project_ws.asyncio.run_coroutine_threadsafe"), \
         patch("asyncio.run_coroutine_threadsafe"), \
         patch("app.api.websockets.project_ws.asyncio.to_thread", side_effect=lambda f, *a, **k: f(*a, **k)):
        with patch("app.api.websockets.project_ws.ProjectCreationFlow") as mock_flow:
            instance = mock_flow.return_value
            instance.kickoff_flow.side_effect = RuntimeError("No result available")

            await run_project_flow(project.id, "prompt")

    updated = project_service.get_project(project.id)
    assert updated.status == "complete"


async def test_run_project_flow_does_not_recover_when_no_files(temp_db):
    """Cover the else path of recovery: no files on disk after error → error status."""
    project = project_service.create_project(
        ProjectCreate(name="Flow NoRecover", description="D")
    )

    with patch("app.api.websockets.project_ws._project_has_required_files", return_value=False):
        with patch("app.api.websockets.project_ws.ProjectCreationFlow") as mock_flow:
            instance = mock_flow.return_value
            instance.kickoff_flow.side_effect = RuntimeError("boom")

            await run_project_flow(project.id, "prompt")

    updated = project_service.get_project(project.id)
    assert updated.status == "error"


async def test_run_project_flow_cancelled_sets_error_status(temp_db):
    project = project_service.create_project(
        ProjectCreate(name="Flow Cancel", description="D")
    )

    async def cancel_self(*args, **kwargs):
        raise asyncio.CancelledError()

    with patch("app.api.websockets.project_ws.asyncio.to_thread", side_effect=cancel_self):
        await run_project_flow(project.id, "prompt")

    updated = project_service.get_project(project.id)
    assert updated.status == "error"


def test_websocket_general_exception_disconnects(client):
    project = client.post("/api/projects", json={"name": "WS Exc", "description": "D"}).json()

    with patch.object(manager, "disconnect") as mock_disconnect:
        with client.websocket_connect(f"/ws/project/{project['id']}") as ws:
            ws.send_text("not json")

    mock_disconnect.assert_called_once_with(project["id"], ANY)


def test_websocket_message_triggers_iteration_when_complete(client, caplog):
    project = client.post("/api/projects", json={"name": "WS Iter", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with caplog.at_level(logging.INFO), patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "add a contact page"})

    mock_run.assert_awaited_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == project_id
    assert call_args[0][1] == "Build me"
    assert call_args.kwargs["mode"] == "iterate"
    assert call_args.kwargs["iteration_request"] == "add a contact page"
    assert f"Starting iterate for project {project_id} via agent engineer" in caplog.text

    updated = project_service.get_project(project_id)
    assert updated.status == "building"


def test_websocket_engineer_mention_routes_focused_iteration(client):
    project = client.post("/api/projects", json={"name": "WS Mention", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({
                "type": "message",
                "content": "@engineer add a compact pricing section",
                "target_agent": "engineer",
            })
            routed = ws.receive_json()

    assert routed == {
        "type": "agent_routed",
        "agent": "engineer",
        "message": "Ravi is applying this as a focused edit. Planning and architecture phases are skipped.",
    }
    mock_run.assert_awaited_once()
    assert mock_run.call_args.kwargs["mode"] == "iterate"
    assert mock_run.call_args.kwargs["iteration_request"] == "add a compact pricing section"
    assert project_service.get_messages(project_id)[0]["content"] == "@engineer add a compact pricing section"


def test_websocket_routes_architect_mention_to_consult_mode(client):
    project = client.post("/api/projects", json={"name": "WS Bad Mention", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "@architect add a page"})
            event = ws.receive_json()

    assert event == {
        "type": "agent_routed",
        "agent": "architect",
        "message": "Theo is reviewing your request and will advise without rewriting the full project.",
    }
    mock_run.assert_awaited_once()
    assert mock_run.call_args.kwargs["mode"] == "consult"
    assert mock_run.call_args.kwargs["consult_agent"] == "architect"
    assert mock_run.call_args.kwargs["iteration_request"] == "add a page"


def test_websocket_message_no_iteration_when_not_complete(client):
    project = client.post("/api/projects", json={"name": "WS NoIter", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "hello"})

    mock_run.assert_not_called()
    messages = project_service.get_messages(project_id)
    assert messages[0]["content"] == "hello"


def test_websocket_message_no_iteration_when_empty(client):
    project = client.post("/api/projects", json={"name": "WS Empty", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "  "})

    mock_run.assert_not_called()


def test_websocket_message_rejects_iteration_during_active_flow(client):
    project = client.post("/api/projects", json={"name": "WS IterDupe", "description": "Build me"}).json()
    project_id = project["id"]

    async def never_finishes(*args, **kwargs):
        await asyncio.sleep(10)

    with patch("app.api.websockets.project_ws.run_project_flow", side_effect=never_finishes):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it"})
            for _ in range(100):
                if manager.get_flow_task(project_id) is not None:
                    break
                time.sleep(0.01)
            project_service.update_project_status(project_id, "complete")
            ws.send_json({"type": "message", "content": "add a page"})
            assert ws.receive_json() == {
                "type": "error",
                "message": "A build is currently running. Please wait for it to finish.",
            }


@pytest.mark.provider_gate
def test_websocket_message_iteration_rejects_unconfigured_provider(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "WS IterProv", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    monkeypatch.setattr(
        "app.api.websockets.project_ws.provider_settings_service.provider_ready_for_build",
        lambda _user_id: (False, "Configure a provider first."),
    )

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "add a page"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert event["category"] == "provider_not_configured"
    mock_run.assert_not_called()


def test_websocket_message_iteration_skips_provider_check_for_legacy_projects(client, temp_db):
    client.post("/api/auth/logout")
    client.cookies.clear()
    project = project_service.create_project(ProjectCreate(name="Legacy Iter", description="Build me"), owner_user_id=None)
    project_service.update_project_status(project.id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project.id}") as ws:
            ws.send_json({"type": "message", "content": "add a page"})

    mock_run.assert_awaited_once()


def test_websocket_message_iteration_rejects_unauthenticated_without_env_key(client, temp_db):
    client.post("/api/auth/logout")
    client.cookies.clear()
    project = project_service.create_project(ProjectCreate(name="NoKeyIter", description="Build me"), owner_user_id=None)
    project_service.update_project_status(project.id, "complete")

    settings.llm_provider = "xai"
    settings.llm_model = "xai/grok-3-mini"
    settings.xai_api_key = None

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project.id}") as ws:
            ws.send_json({"type": "message", "content": "add a page"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert event["category"] == "provider_not_configured"
    assert "Grok / xAI" in event["message"]
    mock_run.assert_not_called()


async def test_run_project_flow_iterate_mode(temp_db):
    project = project_service.create_project(ProjectCreate(name="Flow Iter", description="D"))
    fake_flow = MagicMock()
    fake_flow.kickoff_flow.return_value = None

    with patch("app.api.websockets.project_ws.ProjectCreationFlow", return_value=fake_flow) as mock_flow:
        await run_project_flow(project.id, "prompt", "iterate", iteration_request="add nav")

    call_kwargs = mock_flow.call_args.kwargs
    assert call_kwargs["mode"] == "iterate"
    assert call_kwargs["iteration_request"] == "add nav"
    fake_flow.kickoff_flow.assert_called_once()


def test_websocket_resume_build_uses_latest_checkpoint(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    project = client.post("/api/projects", json={"name": "WS Resume", "description": "Build me"}).json()
    project_id = project["id"]
    checkpoint_location = f"{tmp_path / project_id / '.checkpoints' / 'flow.db'}#abc123"

    with (
        patch("app.api.websockets.project_ws.latest_checkpoint", return_value=checkpoint_location),
        patch("app.api.websockets.project_ws.run_project_flow") as mock_run,
    ):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "resume_build", "prompt": "Build me"})

    mock_run.assert_awaited_once()
    assert mock_run.call_args.kwargs["restore_from"] == checkpoint_location
    messages = project_service.get_messages(project_id)
    assert messages[0]["content"] == "[resume] Continue build from checkpoint"


def test_websocket_resume_build_without_checkpoint_returns_error(client, monkeypatch):
    monkeypatch.setattr("app.api.websockets.project_ws.latest_checkpoint", lambda _project_id: None)
    # keep name for readability; body below asserts no_checkpoint messaging
    project = client.post("/api/projects", json={"name": "WS Resume Missing", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "resume_build"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert "No checkpoint found" in event["message"]
    mock_run.assert_not_called()


def test_validate_feedback_payload_rejects_invalid_action():
    action, feedback, error = validate_feedback_payload({"action": "reject"})
    assert action is None
    assert feedback == ""
    assert error == "Feedback action must be 'approve' or 'revise'."


def test_validate_feedback_payload_rejects_non_text_feedback():
    action, feedback, error = validate_feedback_payload({"action": "approve", "feedback": 42})
    assert action is None
    assert error == "Feedback must be text."


def test_validate_feedback_payload_rejects_empty_revision():
    action, feedback, error = validate_feedback_payload({"action": "revise", "feedback": "   "})
    assert action is None
    assert error == "Revision feedback cannot be empty."


def test_websocket_human_feedback_rejects_invalid_payload(client):
    project = client.post("/api/projects", json={"name": "WS FB Invalid", "description": "D"}).json()
    project_id = project["id"]

    with client.websocket_connect(f"/ws/project/{project_id}") as ws:
        ws.send_json({"type": "human_feedback", "action": "reject"})
        event = ws.receive_json()

    assert event["type"] == "feedback_error"
    assert "approve" in event["message"]


def test_websocket_human_feedback_rejects_stale_request(client):
    project = client.post("/api/projects", json={"name": "WS FB Stale", "description": "D"}).json()
    project_id = project["id"]

    from app.crew.feedback import WebSocketFeedbackProvider

    provider = MagicMock(spec=WebSocketFeedbackProvider)
    provider.has_pending = True
    provider.submit_feedback.return_value = False
    manager.set_feedback_provider(project_id, provider)

    try:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "human_feedback", "action": "approve"})
            event = ws.receive_json()

        assert event["type"] == "feedback_error"
        assert "no longer pending" in event["message"].lower()
    finally:
        manager.remove_feedback_provider(project_id)


def test_websocket_fork_build_without_checkpoint_returns_error(client, monkeypatch):
    monkeypatch.setattr("app.api.websockets.project_ws.latest_checkpoint", lambda _project_id: None)
    project = client.post("/api/projects", json={"name": "WS Fork Missing", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "fork_build"})
            event = ws.receive_json()

    assert event["type"] == "error"
    assert "No checkpoint found to fork from" in event["message"]
    mock_run.assert_not_called()


def test_websocket_message_rejects_iteration_when_task_appears_inside_lock(client):
    project = client.post("/api/projects", json={"name": "WS IterRace", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    pending_task = AsyncMock()
    pending_task.done.return_value = False
    call_count = {"n": 0}

    def fake_get_flow_task(pid):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        if call_count["n"] == 2:
            return pending_task
        return None

    with patch.object(manager, "get_flow_task", side_effect=fake_get_flow_task):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "add a page"})
            event = ws.receive_json()
    assert event == {
        "type": "error",
        "message": "Build already running for this project",
    }


def test_websocket_fork_build_passes_branch_and_checkpoint(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    project = client.post("/api/projects", json={"name": "WS Fork", "description": "Build me"}).json()
    project_id = project["id"]
    checkpoint_location = f"{tmp_path / project_id / '.checkpoints' / 'flow.db'}#fork-me"

    with (
        patch("app.api.websockets.project_ws.latest_checkpoint", return_value=checkpoint_location),
        patch("app.api.websockets.project_ws.run_project_flow") as mock_run,
    ):
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "fork_build", "branch": "experiment-a"})

    assert mock_run.call_args.kwargs["restore_from"] == checkpoint_location
    assert mock_run.call_args.kwargs["fork_branch"] == "experiment-a"


async def test_run_project_flow_fork_branch_uses_fork_helper(temp_db, tmp_path, monkeypatch):
    project = project_service.create_project(ProjectCreate(name="Flow Fork", description="D"))
    fake_flow = MagicMock()
    fake_flow.kickoff_flow.return_value = None

    with patch("app.api.websockets.project_ws.ProjectCreationFlow.fork_from_checkpoint", return_value=fake_flow) as mock_fork:
        await run_project_flow(
            project.id,
            "prompt",
            restore_from="db#fork",
            fork_branch="experiment-a",
        )

    mock_fork.assert_called_once()
    fake_flow.kickoff_flow.assert_called_once()


async def test_run_project_flow_emits_checkpoint_on_error(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    project = project_service.create_project(ProjectCreate(name="Flow Error", description="D"))
    checkpoint_location = f"{tmp_path / project.id / '.checkpoints' / 'flow.db'}#saved"

    sent_events: list[dict] = []

    async def capture_send(project_id, event):
        sent_events.append(event)

    fake_flow = MagicMock()
    fake_flow.kickoff_flow.side_effect = RuntimeError("boom")

    with (
        patch("app.api.websockets.project_ws.manager.send_event", side_effect=capture_send),
        patch("app.api.websockets.project_ws.checkpoint_available", return_value=True),
        patch("app.api.websockets.project_ws.latest_checkpoint", return_value=checkpoint_location),
        patch("app.api.websockets.project_ws.ProjectCreationFlow", return_value=fake_flow),
    ):
        await run_project_flow(project.id, "prompt")

    error_event = next(event for event in sent_events if event["type"] == "error")
    assert error_event["checkpoint"] == checkpoint_location
    assert error_event["can_resume"] is True


async def test_websocket_error_event_failure_is_logged(temp_db, caplog):
    project = project_service.create_project(ProjectCreate(name="WS Send Fail", description="D"))
    ws = AsyncMock()
    ws.headers = {}
    ws.receive_json.side_effect = RuntimeError("receive failed")
    ws.send_json.side_effect = RuntimeError("send failed")

    with (
        caplog.at_level(logging.DEBUG),
        patch("app.auth.dependencies.get_websocket_user", return_value=None),
    ):
        await project_websocket(ws, project.id)

    assert "Failed to send WebSocket error event" in caplog.text


def test_project_has_required_files_try_path(settings_projects_dir):
    """Cover lines 143-144 (the all(...) in try of _project_has_required_files)."""
    pid = "phrf1"
    pdir = settings_projects_dir / pid
    pdir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_PROJECT_FILES:
        (pdir / name).touch()
    assert _project_has_required_files(pid) is True


def test_project_has_required_files_except_path(monkeypatch):
    """Cover the except return False inside _project_has_required_files."""
    monkeypatch.setattr("app.api.websockets.project_ws.settings", type("s", (), {"projects_dir": None})())
    assert _project_has_required_files("boom") is False


def test_emit_project_complete_helper():
    """Cover the body of _emit_project_complete (the emit call and except pass)."""
    calls = []
    def fake_emit(ev):
        calls.append(ev)
    _emit_project_complete(fake_emit)
    assert len(calls) == 1
    assert calls[0]["type"] == "project_complete"

    # also the except path
    def bad_emit(ev):
        raise RuntimeError("emit fail")
    # should not raise
    _emit_project_complete(bad_emit)



def test_classify_build_error_token_budget():
    result = classify_build_error(RuntimeError("Build token budget exceeded: 90001 tokens used, limit 90000."))
    assert result["category"] == "token_budget"
    assert "MAX_BUILD_TOKENS" in result["next_action"]


def test_websocket_start_build_rejects_long_prompt(client, monkeypatch):
    monkeypatch.setattr(settings, "max_prompt_chars", 10)
    project = client.post("/api/projects", json={"name": "WS Long", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "x" * 11})
            event = ws.receive_json()

    assert event["category"] == "prompt_too_long"
    mock_run.assert_not_called()


def test_websocket_start_build_rejects_at_capacity(client, monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_builds", 0)
    assert server_at_build_capacity() is False
    monkeypatch.setattr(settings, "max_concurrent_builds", 1)
    monkeypatch.setattr(
        "app.api.websockets.project_ws.server_at_build_capacity", lambda: True
    )
    project = client.post("/api/projects", json={"name": "WS Cap", "description": "Build me"}).json()
    project_id = project["id"]

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "start_build", "prompt": "Build it"})
            event = ws.receive_json()

    assert event["category"] == "at_capacity"
    mock_run.assert_not_called()


def test_server_at_build_capacity_counts_running_tasks(monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_builds", 1)

    class FakeTask:
        def __init__(self, done):
            self._done = done

        def done(self):
            return self._done

    monkeypatch.setattr(manager, "flow_tasks", {"a": FakeTask(False)})
    assert server_at_build_capacity() is True
    monkeypatch.setattr(manager, "flow_tasks", {"a": FakeTask(True)})
    assert server_at_build_capacity() is False


def test_websocket_message_rejects_long_iteration(client, monkeypatch):
    monkeypatch.setattr(settings, "max_prompt_chars", 10)
    project = client.post("/api/projects", json={"name": "WS LongIter", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "y" * 11})
            event = ws.receive_json()

    assert event["category"] == "prompt_too_long"
    mock_run.assert_not_called()


def test_websocket_message_rejects_iteration_at_capacity(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.websockets.project_ws.server_at_build_capacity", lambda: True
    )
    project = client.post("/api/projects", json={"name": "WS CapIter", "description": "Build me"}).json()
    project_id = project["id"]
    project_service.update_project_status(project_id, "complete")

    with patch("app.api.websockets.project_ws.run_project_flow") as mock_run:
        with client.websocket_connect(f"/ws/project/{project_id}") as ws:
            ws.send_json({"type": "message", "content": "add a page"})
            event = ws.receive_json()

    assert event["category"] == "at_capacity"
    mock_run.assert_not_called()
