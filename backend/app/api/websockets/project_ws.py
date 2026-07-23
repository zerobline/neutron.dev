import asyncio
import logging
import re
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.auth.dependencies import get_websocket_user
from app.config import cors_allowed_origins, settings
from app.models import ProjectConnectorSettings
from app.providers import get_provider
from app.services import project_service, provider_settings_service
from app.crew.connectors import save_project_connectors
from app.crew.checkpoints import checkpoint_available, latest_checkpoint
from app.crew.flows.project_flow import ProjectCreationFlow
from app.crew.feedback import WebSocketFeedbackProvider
from app.crew.schemas import REQUIRED_PROJECT_FILES

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

DIRECT_EDIT_AGENT = "engineer"
# Mentions map to agent ids. Engineer edits files; others run advisory consults.
AGENT_MENTION_ALIASES = {
    "engineer": "engineer",
    "ravi": "engineer",
    "team_leader": "team_leader",
    "kai": "team_leader",
    "leader": "team_leader",
    "product_manager": "product_manager",
    "pm": "product_manager",
    "nina": "product_manager",
    "architect": "architect",
    "theo": "architect",
    "data_scientist": "data_scientist",
    "scientist": "data_scientist",
    "zara": "data_scientist",
    "analyst": "data_scientist",
}
# Back-compat alias used by older tests/helpers.
DIRECT_EDIT_MENTION_ALIASES = AGENT_MENTION_ALIASES

AGENT_DISPLAY = {
    "engineer": "Ravi",
    "team_leader": "Kai",
    "product_manager": "Nina",
    "architect": "Theo",
    "data_scientist": "Zara",
}


def parse_direct_agent_request(content: object, requested_agent: object = None) -> tuple[str | None, str, str | None]:
    """Resolve a post-build @mention into a focused agent request.

    Unmentioned follow-ups retain the existing direct-engineer behavior. The
    explicit target field is treated as untrusted input and must agree with a
    leading mention when both are supplied.
    """
    if not isinstance(content, str):
        return (None, "", "Message content must be text.")

    normalized_content = content.strip()
    mention = re.match(r"^@([a-z][a-z0-9_-]*)\b\s*", normalized_content, re.IGNORECASE)
    mentioned_agent = None
    if mention:
        mentioned_agent = AGENT_MENTION_ALIASES.get(mention.group(1).lower())
        if mentioned_agent is None:
            return (
                None,
                normalized_content,
                "Unknown agent mention. Try @ravi, @nina, @kai, @theo, or @zara.",
            )

    explicit_agent = None
    if requested_agent is not None:
        if not isinstance(requested_agent, str):
            return (None, normalized_content, "Target agent must be text.")
        explicit_agent = AGENT_MENTION_ALIASES.get(requested_agent.strip().lower())
        if explicit_agent is None:
            return (
                None,
                normalized_content,
                "Unknown target agent. Use engineer, product_manager, team_leader, architect, or data_scientist.",
            )

    if mentioned_agent and explicit_agent and mentioned_agent != explicit_agent:
        return (
            None,
            normalized_content,
            "Mention and target_agent do not match.",
        )

    target_agent = mentioned_agent or explicit_agent or DIRECT_EDIT_AGENT
    request = normalized_content[mention.end():].strip() if mention else normalized_content
    if not request:
        display = AGENT_DISPLAY.get(target_agent, target_agent)
        hints = {
            "engineer": "@ravi",
            "team_leader": "@kai",
            "product_manager": "@nina",
            "architect": "@theo",
            "data_scientist": "@zara",
        }
        return (
            None,
            "",
            f"Tell {display} what you need after the mention (e.g. {hints.get(target_agent, '@' + target_agent)} …).",
        )
    return (target_agent, request, None)


def classify_build_error(exc: Exception) -> dict[str, str]:
    message = str(exc)
    lowered = message.lower()
    if "usage limit" in lowered or "quota" in lowered or "billing cycle" in lowered:
        return {
            "category": "quota",
            "message": "LLM provider quota reached.",
            "details": message,
            "next_action": "Switch provider/model in Settings, add credits, or wait for the provider quota to refresh.",
        }
    if "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return {
            "category": "auth",
            "message": "LLM provider authentication failed.",
            "details": message,
            "next_action": "Check the API key and provider settings, then resume the build.",
        }
    if "token budget exceeded" in lowered:
        return {
            "category": "token_budget",
            "message": "The build hit the per-build token budget.",
            "details": message,
            "next_action": "Simplify the prompt, or raise MAX_BUILD_TOKENS in backend/.env.",
        }
    # xAI / LiteLLM capacity errors (often surface as MidStreamFallbackError mid-build).
    if any(
        token in lowered
        for token in (
            "at capacity",
            "high demand",
            "service tier",
            "priority processing",
            "midstreamfallback",
            "model is currently at capacity",
            "overloaded",
            "service unavailable",
        )
    ):
        return {
            "category": "provider_capacity",
            "message": "The AI model is temporarily at capacity (provider overload).",
            "details": message,
            "next_action": (
                "Wait 2–5 minutes and start the build again, switch to a lighter model "
                "(e.g. grok-3-mini), or use another provider in Settings → Cloud & AI."
            ),
        }
    if "rate limit" in lowered or "too many requests" in lowered:
        return {
            "category": "rate_limit",
            "message": "LLM provider rate limit reached.",
            "details": message,
            "next_action": "Wait a few minutes, lower request volume, or switch to another provider/model.",
        }
    if "without writing any project files" in lowered or "skipped tool calls" in lowered:
        return {
            "category": "tool_execution",
            "message": "No project files were created.",
            "details": message,
            "next_action": "Retry the build or switch to a provider/model with reliable tool calling (for example OpenAI GPT-4o).",
        }
    return {
        "category": "runtime",
        "message": message or "Build failed.",
        "details": message,
        "next_action": "Check backend logs, adjust the prompt or provider settings, then resume the build.",
    }


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}
        self.feedback_providers: dict[str, WebSocketFeedbackProvider] = {}
        self.flow_tasks: dict[str, asyncio.Task] = {}
        self._start_locks: dict[str, asyncio.Lock] = {}

    def get_start_lock(self, project_id: str) -> asyncio.Lock:
        if project_id not in self._start_locks:
            self._start_locks[project_id] = asyncio.Lock()
        return self._start_locks[project_id]

    def has_active_connections(self, project_id: str) -> bool:
        return bool(self.active.get(project_id))

    async def connect(self, project_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(project_id, []).append(ws)

    def disconnect(self, project_id: str, ws: WebSocket):
        if project_id in self.active:
            self.active[project_id] = [w for w in self.active[project_id] if w is not ws]
            if not self.active[project_id]:
                self.active.pop(project_id, None)
                self._start_locks.pop(project_id, None)

    async def send_event(self, project_id: str, event: dict):
        for ws in self.active.get(project_id, []):
            try:
                await ws.send_json(event)
            except Exception:
                logger.debug("Failed to send WS event to %s", project_id, exc_info=True)

    def set_feedback_provider(self, project_id: str, provider: WebSocketFeedbackProvider):
        self.feedback_providers[project_id] = provider

    def get_feedback_provider(self, project_id: str) -> WebSocketFeedbackProvider | None:
        return self.feedback_providers.get(project_id)

    def remove_feedback_provider(self, project_id: str):
        self.feedback_providers.pop(project_id, None)

    def set_flow_task(self, project_id: str, task: asyncio.Task):
        self.flow_tasks[project_id] = task
        task.add_done_callback(lambda done_task: self._remove_flow_task(project_id, done_task))

    def get_flow_task(self, project_id: str) -> asyncio.Task | None:
        task = self.flow_tasks.get(project_id)
        if task and not task.done():
            return task
        return None

    def _remove_flow_task(self, project_id: str, task: asyncio.Task):
        if self.flow_tasks.get(project_id) is task:
            self.flow_tasks.pop(project_id, None)

    async def cancel_flow(self, project_id: str):
        task = self.get_flow_task(project_id)
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Cancelled build flow for project %s", project_id)

    async def cancel_all_flows(self):
        project_ids = list(self.flow_tasks)
        await asyncio.gather(
            *(self.cancel_flow(project_id) for project_id in project_ids),
            return_exceptions=True,
        )


manager = ConnectionManager()


def _project_has_required_files(project_id: str) -> bool:
    """Best-effort check used to recover from late CrewAI internal crashes.
    If the core files exist on disk we can still report success to the user.
    """
    try:
        proj_dir = settings.projects_dir / project_id
        return all((proj_dir / name).exists() for name in REQUIRED_PROJECT_FILES)
    except Exception:
        return False


def _emit_project_complete(emit_func):
    """Helper to emit project_complete in recovery paths (extracted for testability and coverage)."""
    try:
        emit_func({
            "type": "project_complete",
            "files": list(REQUIRED_PROJECT_FILES),
            "message": "Project generated successfully.",
        })
    except Exception:
        pass  # best effort


VALID_BUILD_MODES = {"team", "engineer", "goal", "iterate", "consult"}


def normalize_build_mode(mode: str) -> str:
    return mode if mode in VALID_BUILD_MODES else "team"


def websocket_origin_allowed(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    return not origin or origin in cors_allowed_origins()


def prompt_too_long_error(length: int) -> dict:
    return {
        "type": "error",
        "category": "prompt_too_long",
        "message": f"Prompt is too long ({length} characters, limit {settings.max_prompt_chars}).",
        "next_action": "Shorten the prompt or attach large content as an uploaded file.",
    }


def builds_at_capacity_error() -> dict:
    return {
        "type": "error",
        "category": "at_capacity",
        "message": "The build queue is at capacity right now.",
        "next_action": "Please wait a moment and try again.",
    }


def server_at_build_capacity() -> bool:
    limit = settings.max_concurrent_builds
    if limit <= 0:
        return False
    running = sum(1 for task in manager.flow_tasks.values() if not task.done())
    return running >= limit


def validate_feedback_payload(data: dict) -> tuple[str | None, str, str | None]:
    action = data.get("action")
    feedback = data.get("feedback", "")
    if action not in {"approve", "revise"}:
        return (None, "", "Feedback action must be 'approve' or 'revise'.")
    if not isinstance(feedback, str):
        return (None, "", "Feedback must be text.")
    normalized = feedback.strip()
    if action == "revise" and not normalized:
        return (None, "", "Revision feedback cannot be empty.")
    return (action, normalized, None)


async def send_feedback_error(ws: WebSocket, message: str) -> None:
    await ws.send_json({
        "type": "feedback_error",
        "category": "invalid_feedback",
        "message": message,
        "next_action": "Review the pending phase and submit valid feedback.",
    })


async def run_project_flow(
    project_id: str,
    user_prompt: str,
    mode: str = "team",
    connectors: ProjectConnectorSettings | dict | None = None,
    user_id: str | None = None,
    iteration_request: str = "",
    consult_agent: str | None = None,
    *,
    restore_from: str | None = None,
    fork_branch: str | None = None,
):
    loop = asyncio.get_running_loop()
    feedback_provider = WebSocketFeedbackProvider()
    manager.set_feedback_provider(project_id, feedback_provider)

    current_phase = ""
    current_agent = ""

    def emit(event: dict):
        nonlocal current_phase, current_agent
        if event.get("type") == "phase_start":
            current_phase = str(event.get("phase") or current_phase)
        if event.get("type") in {
            "agent_start",
            "agent_thinking",
            "agent_complete",
            "agent_step",
            "stream_chunk",
            "tool_call",
            "tool_result",
        }:
            current_agent = str(event.get("agent") or current_agent)
        asyncio.run_coroutine_threadsafe(
            manager.send_event(project_id, event), loop
        )
        if event.get("type") == "phase_start":
            status_map = {
                "leading": "leading",
                "analyzing": "analyzing",
                "planning": "planning",
                "architecting": "architecting",
                "building": "building",
            }
            phase = event.get("phase")
            status = status_map.get(phase) if isinstance(phase, str) else None
            if status:
                project_service.update_project_status(project_id, status)
        # Persist structured phase cards so refresh rehydrates PhaseResultCard UI.
        # agent_complete is status-only in the live client; do not double-save it.
        if event.get("type") == "phase_result":
            summary = str(event.get("summary") or event.get("content") or "").strip()
            if summary:
                project_service.save_message(
                    project_id,
                    "agent",
                    summary,
                    event.get("agent") if isinstance(event.get("agent"), str) else None,
                    kind="phase_result",
                    metadata={
                        "phase": event.get("phase"),
                        "kind": event.get("kind"),
                        "headline": event.get("headline"),
                        "summary": summary,
                        "spec": event.get("spec"),
                        "has_structured_spec": bool(
                            event.get("has_structured_spec") or event.get("spec")
                        ),
                    },
                )
        if event.get("type") == "human_feedback_request":
            project_service.update_project_status(project_id, "awaiting_feedback")

    def run_flow():
        try:
            normalized_mode = normalize_build_mode(mode)
            if fork_branch and restore_from:
                flow = ProjectCreationFlow.fork_from_checkpoint(
                    project_id,
                    user_prompt,
                    restore_from=restore_from,
                    branch=fork_branch,
                    event_callback=emit,
                    feedback_provider=feedback_provider,
                    mode=normalized_mode,
                    connector_settings=connectors,
                    user_id=user_id,
                    iteration_request=iteration_request,
                )
            else:
                flow = ProjectCreationFlow(
                    project_id=project_id,
                    user_prompt=user_prompt,
                    event_callback=emit,
                    feedback_provider=feedback_provider,
                    mode=normalized_mode,
                    connector_settings=connectors,
                    user_id=user_id,
                    iteration_request=iteration_request,
                    consult_agent=consult_agent,
                    restore_from=restore_from,
                )
            if restore_from:
                emit({
                    "type": "checkpoint_resume",
                    "checkpoint": restore_from,
                    "message": "Resuming build from the latest saved checkpoint...",
                })
            flow.kickoff_flow()
            project_service.update_project_status(project_id, "complete")
        except Exception as exc:
            logger.exception("Build flow failed for project %s", project_id)

            # CrewAI internals (checkpoint listener + streaming + threading) can
            # panic or raise "No result available" even after the engineer has
            # successfully written all files (seen in Docker logs as
            # pyo3 "dictionary changed size during iteration" during model_dump).
            # If the required output files exist on disk, recover and report
            # success so the user experience matches previous stable behavior.
            if _project_has_required_files(project_id):
                logger.warning(
                    "Recovered project %s: files present on disk despite internal CrewAI error (%s). "
                    "Treating as complete.",
                    project_id, type(exc).__name__
                )
                project_service.update_project_status(project_id, "complete")
                _emit_project_complete(emit)
            else:
                error = classify_build_error(exc)
                error_event = {
                    "type": "error",
                    "message": error["message"],
                    "category": error["category"],
                    "next_action": error["next_action"],
                    "phase": current_phase,
                    "agent": current_agent,
                }
                if checkpoint_available(project_id):
                    error_event["checkpoint"] = latest_checkpoint(project_id)
                    error_event["can_resume"] = True
                    error_event["next_action"] = (
                        error_event.get("next_action")
                        or "Use Resume to continue from the last saved checkpoint."
                    )
                else:
                    error_event["can_resume"] = False
                emit(error_event)
                # Notify UI of latest checkpoint location when available.
                if error_event.get("checkpoint"):
                    emit({
                        "type": "checkpoint_saved",
                        "checkpoint": error_event["checkpoint"],
                        "message": "Checkpoint available — you can resume this build.",
                    })
                project_service.update_project_status(project_id, "error")
        finally:
            manager.remove_feedback_provider(project_id)

    try:
        await asyncio.to_thread(run_flow)
    except asyncio.CancelledError:
        project_service.update_project_status(project_id, "error")
        logger.info("Build flow cancelled for project %s", project_id)
        manager.remove_feedback_provider(project_id)


@router.websocket("/ws/project/{project_id}")
async def project_websocket(ws: WebSocket, project_id: str):
    if not websocket_origin_allowed(ws):
        await ws.close(code=4403, reason="Origin not allowed")
        return
    current_user = get_websocket_user(ws)
    project_owner_user_id = project_service.get_project_owner_user_id(project_id)
    if project_owner_user_id is not None and current_user is None:
        await ws.close(code=4401, reason="Authentication required")
        return
    if project_owner_user_id is not None and current_user is not None and project_owner_user_id != current_user.id:
        await ws.close(code=4403, reason="Project access denied")
        return

    project = project_service.get_project(project_id, current_user.id if current_user else None)
    if not project:
        await ws.close(code=4004, reason="Project not found")
        return

    await manager.connect(project_id, ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type in {"start_build", "resume_build", "fork_build"}:
                async with manager.get_start_lock(project_id):
                    existing_task = manager.get_flow_task(project_id)
                    if existing_task:
                        await ws.send_json({"type": "error", "message": "Build already running for this project"})
                        continue
                    if current_user:
                        ready, provider_message = provider_settings_service.provider_ready_for_build(current_user.id)
                        if not ready:
                            await ws.send_json({
                                "type": "error",
                                "category": "provider_not_configured",
                                "message": provider_message,
                                "next_action": "Open Settings → Cloud & AI and connect a provider.",
                            })
                            continue
                    else:
                        env_config = settings.effective_litellm_config()
                        provider_def = get_provider(env_config["provider"])
                        if provider_def.requires_api_key and not env_config["api_key"]:
                            await ws.send_json({
                                "type": "error",
                                "category": "provider_not_configured",
                                "message": f"{provider_def.label} API key is not configured. Set it in your backend/.env file.",
                                "next_action": "Add the API key to backend/.env and restart the server.",
                            })
                            continue
                    prompt = data.get("prompt", project.description)
                    if isinstance(prompt, str) and len(prompt) > settings.max_prompt_chars:
                        await ws.send_json(prompt_too_long_error(len(prompt)))
                        continue
                    if server_at_build_capacity():
                        await ws.send_json(builds_at_capacity_error())
                        continue
                    mode = normalize_build_mode(data.get("mode", "team"))
                    raw_connectors = data.get("connectors")
                    connectors = None
                    if raw_connectors is not None:
                        connectors = ProjectConnectorSettings.model_validate(raw_connectors)
                        save_project_connectors(project_id, connectors)

                    restore_from = None
                    fork_branch = None
                    if msg_type == "resume_build":
                        restore_from = data.get("checkpoint") or latest_checkpoint(project_id)
                        if not restore_from:
                            await ws.send_json({
                                "type": "error",
                                "category": "no_checkpoint",
                                "message": (
                                    "No checkpoint found for this project yet. "
                                    "Checkpoints are saved after each completed phase — "
                                    "start a new build first, or switch to Engineer mode "
                                    "to continue from files already on disk."
                                ),
                                "next_action": (
                                    "Click Start build to create a new run. "
                                    "After the next failure or phase, Resume will work."
                                ),
                            })
                            continue
                    elif msg_type == "fork_build":
                        restore_from = data.get("checkpoint") or latest_checkpoint(project_id)
                        if not restore_from:
                            await ws.send_json({
                                "type": "error",
                                "category": "no_checkpoint",
                                "message": (
                                    "No checkpoint found to fork from. "
                                    "Run a build long enough to finish at least one phase first."
                                ),
                                "next_action": "Start a new build, then fork after a phase completes.",
                            })
                            continue
                        fork_branch = data.get("branch") or f"fork-{int(time.time())}"

                    action_label = {
                        "start_build": "Starting",
                        "resume_build": "Resuming",
                        "fork_build": "Forking",
                    }[msg_type]
                    logger.info("%s build for project %s in %s mode", action_label, project_id, mode)
                    if msg_type == "start_build":
                        project_service.save_message(project_id, "user", prompt)
                    elif msg_type == "resume_build":
                        project_service.save_message(project_id, "user", "[resume] Continue build from checkpoint")
                    else:
                        project_service.save_message(
                            project_id,
                            "user",
                            f"[fork:{fork_branch}] Branch build from checkpoint",
                        )
                    project_service.update_project_status(project_id, "building" if mode == "engineer" else "leading")
                    flow_task = asyncio.create_task(
                        run_project_flow(
                            project_id,
                            prompt,
                            mode,
                            connectors,
                            current_user.id if current_user else None,
                            restore_from=restore_from,
                            fork_branch=fork_branch,
                        )
                    )
                    manager.set_flow_task(project_id, flow_task)

            elif msg_type == "human_feedback":
                action, feedback, validation_error = validate_feedback_payload(data)
                if validation_error:
                    await send_feedback_error(ws, validation_error)
                    continue
                provider = manager.get_feedback_provider(project_id)
                if not provider or not provider.has_pending:
                    await send_feedback_error(ws, "No feedback request is currently pending.")
                    continue
                if not provider.submit_feedback(action or "", feedback):
                    await send_feedback_error(ws, "The feedback request is no longer pending.")
                    continue
                if feedback:
                    project_service.save_message(project_id, "user", f"[{action}] {feedback}")

            elif msg_type == "message":
                content = data.get("content", "")
                target_agent, iteration_request, routing_error = parse_direct_agent_request(
                    content,
                    data.get("target_agent"),
                )
                if routing_error:
                    await ws.send_json({
                        "type": "error",
                        "category": "invalid_agent_mention",
                        "message": routing_error,
                        "next_action": "Start the message with @engineer and describe the focused change.",
                    })
                    continue
                if len(iteration_request) > settings.max_prompt_chars:
                    await ws.send_json(prompt_too_long_error(len(iteration_request)))
                    continue
                if server_at_build_capacity():
                    await ws.send_json(builds_at_capacity_error())
                    continue

                current_status = project_service.get_project_status(project_id)
                if current_status == "building" or manager.get_flow_task(project_id):
                    await ws.send_json({"type": "error", "message": "A build is currently running. Please wait for it to finish."})
                    continue

                logger.info("Saving user message for project %s", project_id)
                project_service.save_message(project_id, "user", content)

                if current_status not in ("complete", "error"):
                    await ws.send_json({"type": "error", "message": "Cannot iterate on a project that hasn't been built yet. Click Start Building."})
                    continue

                async with manager.get_start_lock(project_id):
                    existing_task = manager.get_flow_task(project_id)
                    if existing_task:
                        await ws.send_json({"type": "error", "message": "Build already running for this project"})
                        continue
                    if current_user:
                        ready, provider_message = provider_settings_service.provider_ready_for_build(current_user.id)
                        if not ready:
                            await ws.send_json({
                                "type": "error",
                                "category": "provider_not_configured",
                                "message": provider_message,
                                "next_action": "Open Settings → Cloud & AI and connect a provider.",
                            })
                            continue
                    else:
                        env_config = settings.effective_litellm_config()
                        provider_def = get_provider(env_config["provider"])
                        if provider_def.requires_api_key and not env_config["api_key"]:
                            await ws.send_json({
                                "type": "error",
                                "category": "provider_not_configured",
                                "message": f"{provider_def.label} API key is not configured. Set it in your backend/.env file.",
                                "next_action": "Add the API key to backend/.env and restart the server.",
                            })
                            continue
                    is_engineer = target_agent == "engineer"
                    mode = "iterate" if is_engineer else "consult"
                    display = AGENT_DISPLAY.get(target_agent, target_agent)
                    route_message = (
                        "Ravi is applying this as a focused edit. Planning and architecture phases are skipped."
                        if is_engineer
                        else f"{display} is reviewing your request and will advise without rewriting the full project."
                    )
                    logger.info(
                        "Starting %s for project %s via agent %s",
                        mode,
                        project_id,
                        target_agent,
                    )
                    await ws.send_json({
                        "type": "agent_routed",
                        "agent": target_agent,
                        "message": route_message,
                    })
                    project_service.update_project_status(project_id, "building")
                    flow_task = asyncio.create_task(
                        run_project_flow(
                            project_id,
                            project.description,
                            mode=mode,
                            user_id=current_user.id if current_user else None,
                            iteration_request=iteration_request,
                            consult_agent=None if is_engineer else target_agent,
                        )
                    )
                    manager.set_flow_task(project_id, flow_task)

            elif msg_type == "undo_last_edit":
                current_status = project_service.get_project_status(project_id)
                if current_status == "building" or manager.get_flow_task(project_id):
                    await ws.send_json({
                        "type": "error",
                        "message": "Cannot undo while a build is running.",
                    })
                    continue
                try:
                    from app.crew.edit_history import undo_last_edit

                    result = undo_last_edit(project_id)
                    project_service.save_message(
                        project_id,
                        "system",
                        result.get("message") or "Last edit undone.",
                    )
                    await ws.send_json({
                        "type": "edit_undone",
                        "restored": result.get("restored") or [],
                        "message": result.get("message") or "Last edit undone.",
                    })
                    # Refresh file contents for the client
                    files = project_service.get_project_files(project_id)
                    for f in files:
                        await ws.send_json({
                            "type": "file_created",
                            "file_path": f["file_path"],
                            "content": f.get("content") or "",
                        })
                except FileNotFoundError as exc:
                    await ws.send_json({
                        "type": "error",
                        "category": "no_undo",
                        "message": str(exc),
                        "next_action": "Make an @engineer edit first, then you can undo it.",
                    })
                except Exception as exc:
                    logger.exception("Undo failed for project %s", project_id)
                    await ws.send_json({
                        "type": "error",
                        "message": f"Undo failed: {exc}",
                    })

    except WebSocketDisconnect:
        manager.disconnect(project_id, ws)
        if not manager.has_active_connections(project_id):
            feedback = manager.get_feedback_provider(project_id)
            if feedback and feedback.has_pending:
                feedback.submit_feedback("approve", "")
            # Refreshes and brief network drops must not destroy in-progress
            # work. The task remains registered until its worker thread exits,
            # so reconnects cannot accidentally launch a duplicate build.
            logger.info("Client disconnected from project %s; build continues in background", project_id)
    except Exception:
        logger.exception("WebSocket error for project %s", project_id)
        try:
            await ws.send_json({"type": "error", "message": "WebSocket connection error"})
        except Exception:
            logger.debug("Failed to send WebSocket error event for %s", project_id, exc_info=True)
        manager.disconnect(project_id, ws)
