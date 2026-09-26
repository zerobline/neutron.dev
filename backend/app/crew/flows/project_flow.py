from typing import Any, Callable
from pydantic import BaseModel, Field, PrivateAttr
from crewai import CheckpointConfig
from crewai.flow.flow import Flow, listen, start
from app.config import settings
from app.crew.checkpoints import build_checkpoint_config
from app.crew.completion import build_quality_checklist, follow_up_suggestions
from app.crew.presentation import (
    build_phase_result_event,
    extract_spec,
    human_summary_for_result,
    humanize_text,
    looks_like_json_blob,
)
from app.crew.schemas import (
    AnalysisReportSpec,
    ArchitectureSpec,
    BuildSummarySpec,
    ProjectBriefSpec,
    ProjectPlanSpec,
    REQUIRED_PROJECT_FILES,
)
from app.crew.stacks import normalize_stack, required_files_for_stack
from app.crew.streaming import (
    FLOW_ONLY_CHANNELS,
    consume_stream_output,
    is_consumable_stream,
    kickoff_with_streaming,
)
from app.models import ProjectConnectorSettings
from app.crew.connectors import (
    ConnectorContextTool,
    get_connector_context,
    load_project_connectors,
    merge_connector_settings,
    resolve_agent_mcps,
)
from app.crew.skills_loader import resolve_agent_skills
from app.crew.uploads import get_upload_context
from app.crew.agents.team_leader import create_team_leader_agent
from app.crew.agents.data_scientist import create_data_scientist_agent
from app.crew.agents.product_manager import create_pm_agent
from app.crew.agents.architect import create_architect_agent
from app.crew.agents.engineer import create_engineer_agent
from app.crew.tasks.leadership_tasks import create_leadership_task
from app.crew.tasks.analysis_tasks import create_analysis_task
from app.crew.tasks.planning_tasks import create_planning_task
from app.crew.tasks.architecture_tasks import create_architecture_task
from app.crew.static_navigation import find_project_navigation_violations
from app.crew.tasks.engineering_tasks import (
    create_engineering_recovery_tasks,
    create_engineering_task,
    create_iteration_task,
    create_navigation_recovery_task,
)
from app.crew.tasks.consult_tasks import create_consult_task
from app.crew.edit_history import finalize_edit_snapshot, snapshot_before_edit
from app.crew.crews import (
    create_leadership_crew,
    create_analysis_crew,
    create_planning_crew,
    create_architecture_crew,
    create_consult_crew,
    create_engineering_crew,
    create_engineering_recovery_crew,
)
from app.crew.tools.code_writer import CodeWriterTool
from app.crew.tools.file_reader import FileReaderTool
from app.crew.feedback import WebSocketFeedbackProvider
from app.services.project_service import update_project_token_usage


def _has_written_required_files(project_id: str) -> bool:
    """Lightweight check used inside the flow to tolerate late CrewAI errors
    (e.g. checkpoint panics after files are already written).
    """
    try:
        from app.config import settings
        from app.crew.schemas import REQUIRED_PROJECT_FILES
        proj_dir = settings.projects_dir / project_id
        return all((proj_dir / name).exists() for name in REQUIRED_PROJECT_FILES)
    except Exception:
        return False


def _safe_raw(result) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return humanize_text(result, fallback=result)
    pydantic = getattr(result, "pydantic", None)
    if isinstance(pydantic, BaseModel):
        # Prefer human summary fields when present so chat/review never default
        # to a raw JSON dump for structured phases.
        summary = getattr(pydantic, "summary", None)
        if isinstance(summary, str) and summary.strip() and not looks_like_json_blob(summary):
            return summary.strip()
        overview = getattr(pydantic, "overview", None)
        if isinstance(overview, str) and overview.strip() and not looks_like_json_blob(overview):
            return overview.strip()
        user_intent = getattr(pydantic, "user_intent", None)
        if isinstance(user_intent, str) and user_intent.strip() and not looks_like_json_blob(user_intent):
            return user_intent.strip()
        system_overview = getattr(pydantic, "system_overview", None)
        if isinstance(system_overview, str) and system_overview.strip() and not looks_like_json_blob(system_overview):
            return system_overview.strip()
        # Last resort for machine context only; UI presentation humanizes again.
        return pydantic.model_dump_json(indent=2)
    raw = getattr(result, "raw", "")
    if isinstance(raw, str):
        return humanize_text(raw, fallback=raw)
    return humanize_text(str(raw), fallback=str(raw))


def _extract_spec(result: Any, model_type: type[BaseModel]) -> BaseModel | None:
    return extract_spec(result, model_type)


NO_FILES_WRITTEN_ERROR = (
    "Build finished without writing all required project files."
)
ITERATION_NO_FILES_WRITTEN_ERROR = (
    "Iteration finished without writing any project files via write_code_file."
)
INVALID_NAVIGATION_ERROR = "Build used invalid root-relative navigation"
TOKEN_BUDGET_ERROR = "Build token budget exceeded"
MAX_PHASE_ATTEMPTS = 3
FULL_BUILD_PHASES = ("leading", "analyzing", "planning", "architecting", "building")
DIRECT_BUILD_PHASES = ("building",)
COMPACT_CONTEXT_PROMPT = "Accepted output from the preceding phase is supplied as task context."


def _revision_prompt(base_prompt: str, previous_output: str, feedback: str) -> str:
    return (
        f"{base_prompt}\n\n--- Revision request for this phase ---\n"
        f"Previous candidate:\n{previous_output}\n\n"
        f"User feedback:\n{feedback}\n\n"
        "Produce a complete replacement for this phase. Preserve unrelated approved scope."
    )


GOAL_MODE_DIRECTIVE = (
    "\n\n--- Goal mode ---\n"
    "Plan and build autonomously toward the user's goal. "
    "Do not pause for human review between phases; use each agent's output as context for the next step."
)


class TokenUsageSummary(BaseModel):
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    successful_requests: int = 0


class ProjectFlowState(BaseModel):
    project_id: str = ""
    user_prompt: str = ""
    mode: str = "team"
    stack: str = "static"
    leadership_output: str = ""
    analysis_output: str = ""
    plan_output: str = ""
    architecture_output: str = ""
    engineering_output: str = ""
    iteration_request: str = ""
    consult_agent: str = ""
    brief_spec: dict[str, Any] | None = None
    analysis_spec: dict[str, Any] | None = None
    plan_spec: dict[str, Any] | None = None
    architecture_spec: dict[str, Any] | None = None
    build_summary_spec: dict[str, Any] | None = None
    files_created: list[str] = Field(default_factory=list)
    connector_settings: ProjectConnectorSettings = Field(default_factory=ProjectConnectorSettings)
    user_id: str | None = None
    status: str = "created"
    error: str | None = None
    token_usage: TokenUsageSummary = Field(default_factory=TokenUsageSummary)
    context_prepared: bool = False


class ProjectCreationFlow(Flow[ProjectFlowState]):
    """Flow for project creation. Transient runtime fields (callbacks, providers)
    use PrivateAttr so they are excluded from Pydantic serialization / checkpoints.
    """
    _event_callback: Callable[[dict], None] | None = PrivateAttr(default=None)
    _feedback_provider: WebSocketFeedbackProvider | None = PrivateAttr(default=None)
    _restore_from: str | None = PrivateAttr(default=None)
    _files_created: list[str] = PrivateAttr(default_factory=list)
    _writes_this_run: int = PrivateAttr(default=0)
    _files_written_this_run: list[str] = PrivateAttr(default_factory=list)

    def __init__(
        self,
        project_id: str = "",
        user_prompt: str = "",
        event_callback: Callable[[dict], None] | None = None,
        feedback_provider: WebSocketFeedbackProvider | None = None,
        mode: str = "team",
        connector_settings: ProjectConnectorSettings | dict | None = None,
        user_id: str | None = None,
        iteration_request: str = "",
        consult_agent: str | None = None,
        restore_from: str | None = None,
    ):
        # Always enable checkpoints so resume/fork work after failures.
        # Events are restricted to post-crew/post-method moments (see
        # checkpoints.SAFE_CHECKPOINT_EVENTS) so we do not model_dump while
        # streaming tools mutate PrivateAttr trackers mid-crew.
        # CrewAI Flow.fork() instantiates the Flow class with no arguments
        # before restoring checkpoint state. Avoid creating a checkpoint config
        # for that temporary empty instance; fork_from_checkpoint() installs the
        # real project-scoped checkpoint immediately after restoration.
        ckpt = (
            build_checkpoint_config(project_id, restore_from=restore_from)
            if project_id
            else False
        )
        super().__init__(
            stream=True,
            checkpoint=ckpt,
        )
        self._restore_from = restore_from
        self.state.project_id = project_id
        self.state.user_prompt = user_prompt
        self.state.mode = mode
        self.state.user_id = user_id
        self.state.iteration_request = iteration_request
        self.state.consult_agent = (consult_agent or "").strip()
        # Resolve stack from the project record (set by Next.js templates, etc.).
        try:
            from app.services import project_service as _project_service

            project = _project_service.get_project(project_id)
            self.state.stack = normalize_stack(getattr(project, "stack", None) if project else "static")
        except Exception:
            self.state.stack = "static"
        saved_connectors = load_project_connectors(project_id)
        self.state.connector_settings = merge_connector_settings(saved_connectors, connector_settings)
        self._event_callback = event_callback
        self._feedback_provider = feedback_provider
        # Seed private tracker from (restored) state so that file appends during
        # resumed engineering continue the prior list without dupes.
        self._files_created = list(self.state.files_created or [])

    def _emit(self, event: dict):
        if self._event_callback:
            self._event_callback(event)

    def _agent_mcps(self) -> list:
        # Return as plain list for Agent(mcps=...) — avoids list-invariance issues with MCPServerConfig.
        return list(resolve_agent_mcps(self.state.connector_settings, user_id=self.state.user_id))

    def _agent_skills(self, agent_key: str) -> list[str] | None:
        # CrewAI rejects empty skills lists (MinLen 1); pass None when nothing is enabled.
        paths = resolve_agent_skills(self.state.project_id, agent_key=agent_key)
        return paths or None

    def _phase_sequence(self) -> tuple[str, ...]:
        if self.state.mode in ("engineer", "iterate", "consult"):
            return DIRECT_BUILD_PHASES
        return FULL_BUILD_PHASES

    def _phase_details(self, phase: str, *, complete: bool) -> dict[str, int]:
        phases = self._phase_sequence()
        try:
            step = phases.index(phase) + 1
        except ValueError:
            step = len(phases)
        completed_steps = step if complete else max(0, step - 1)
        return {
            "step": step,
            "total_steps": len(phases),
            "percent": round(completed_steps / len(phases) * 100),
        }

    def _start_phase(self, phase: str, message: str) -> None:
        self.state.status = phase
        self._emit({
            "type": "phase_start",
            "phase": phase,
            "message": message,
            **self._phase_details(phase, complete=False),
        })

    def _complete_phase(self, phase: str) -> None:
        self._emit({
            "type": "phase_progress",
            "phase": phase,
            "status": "complete",
            **self._phase_details(phase, complete=True),
        })
        # Surface latest CrewAI checkpoint (written on method_execution_finished).
        try:
            from app.crew.checkpoints import latest_checkpoint

            location = latest_checkpoint(self.state.project_id)
            if location:
                self._emit({
                    "type": "checkpoint_saved",
                    "checkpoint": location,
                    "phase": phase,
                    "message": f"Checkpoint saved after {phase}.",
                })
        except Exception:
            pass

    def build_kickoff_checkpoint(self) -> CheckpointConfig:
        return build_checkpoint_config(self.state.project_id, restore_from=self._restore_from)

    def kickoff_flow(self):
        if self._restore_from:
            checkpoint = self.build_kickoff_checkpoint()
            output = self.kickoff(from_checkpoint=checkpoint)
        else:
            output = self.kickoff()
        if is_consumable_stream(output):
            try:
                # Outer flow stream only forwards flow/lifecycle frames. Crew
                # kickoffs already emit llm/tools with the correct agent_hint;
                # re-emitting them here caused duplicate steps and wrong agents.
                return consume_stream_output(
                    output,
                    self._emit,
                    channels=FLOW_ONLY_CHANNELS,
                )
            except Exception:
                # CrewAI can raise after files are written (checkpoint/stream races).
                if _has_written_required_files(self.state.project_id):
                    return None
                raise
        return output

    @classmethod
    def fork_from_checkpoint(
        cls,
        project_id: str,
        user_prompt: str,
        *,
        restore_from: str,
        branch: str | None = None,
        event_callback: Callable[[dict], None] | None = None,
        feedback_provider: WebSocketFeedbackProvider | None = None,
        mode: str = "team",
        connector_settings: ProjectConnectorSettings | dict | None = None,
        user_id: str | None = None,
        iteration_request: str = "",
    ) -> "ProjectCreationFlow":
        config = build_checkpoint_config(project_id, restore_from=restore_from)
        flow = cls.fork(config, branch=branch)
        flow.state.project_id = project_id
        flow.state.user_prompt = user_prompt
        flow.state.context_prepared = False
        flow.state.mode = mode
        flow.state.user_id = user_id
        flow.state.iteration_request = iteration_request
        saved_connectors = load_project_connectors(project_id)
        flow.state.connector_settings = merge_connector_settings(saved_connectors, connector_settings)
        flow._event_callback = event_callback
        flow._feedback_provider = feedback_provider
        flow.stream = True
        flow.checkpoint = build_checkpoint_config(project_id)
        flow._restore_from = None
        flow._files_created = list(flow.state.files_created or [])
        return flow

    @staticmethod
    def _usage_value(usage: Any, name: str) -> int:
        value = usage.get(name, 0) if isinstance(usage, dict) else getattr(usage, name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    def _accumulate_tokens(self, result) -> None:
        usage = getattr(result, "token_usage", None)
        if not usage:
            return
        # Assign a fresh TokenUsageSummary instead of mutating fields in-place.
        # This avoids "dictionary changed size" panics in concurrent Pydantic
        # model_dump() performed by CrewAI checkpoint listeners.
        tu = self.state.token_usage
        self.state.token_usage = TokenUsageSummary(
            total_tokens=tu.total_tokens + self._usage_value(usage, "total_tokens"),
            prompt_tokens=tu.prompt_tokens + self._usage_value(usage, "prompt_tokens"),
            completion_tokens=tu.completion_tokens + self._usage_value(usage, "completion_tokens"),
            successful_requests=tu.successful_requests + self._usage_value(usage, "successful_requests"),
        )
        budget = settings.max_build_tokens
        usage_payload = self.state.token_usage.model_dump()
        update_project_token_usage(
            self.state.project_id,
            **usage_payload,
            token_budget=budget,
        )
        event = {
            "type": "token_usage",
            "phase": self.state.status,
            "usage": usage_payload,
            "token_budget": budget,
        }
        if budget > 0:
            event["percent"] = round(self.state.token_usage.total_tokens / budget * 100, 1)
        self._emit(event)
        if budget > 0 and self.state.token_usage.total_tokens > budget:
            raise RuntimeError(
                f"{TOKEN_BUDGET_ERROR}: {self.state.token_usage.total_tokens} tokens used, limit {budget}."
            )

    def _run_reviewed_phase(
        self,
        *,
        phase: str,
        agent_name: str,
        task_label: str,
        run_attempt: Callable[[str], Any],
        store_result: Callable[[Any, str], None],
    ) -> str:
        prompt = self.state.user_prompt
        for attempt in range(1, MAX_PHASE_ATTEMPTS + 1):
            label = task_label if attempt == 1 else f"Revising: {task_label}"
            self._emit({
                "type": "agent_start",
                "agent": agent_name,
                "task": label,
                "attempt": attempt,
                "max_attempts": MAX_PHASE_ATTEMPTS,
            })
            result = run_attempt(prompt)
            self._accumulate_tokens(result)
            output = _safe_raw(result)
            store_result(result, output)
            phase_result = build_phase_result_event(
                phase=phase,
                agent=agent_name,
                result=result,
                output_text=output,
                task_label=task_label,
            )
            summary = phase_result.get("summary") or human_summary_for_result(result, output, phase)
            self._emit({
                "type": "agent_complete",
                "agent": agent_name,
                "content": summary,
                "summary": summary,
                "attempt": attempt,
                "max_attempts": MAX_PHASE_ATTEMPTS,
            })
            self._emit(phase_result)

            if self.state.mode == "goal" or not self._feedback_provider:
                self._complete_phase(phase)
                return output

            self._emit({
                "type": "human_feedback_request",
                "phase": phase,
                "agent": agent_name,
                "content": summary,
                "summary": summary,
                "spec": phase_result.get("spec"),
                "kind": phase_result.get("kind"),
                "headline": phase_result.get("headline"),
                "message": f"Review {agent_name}'s output before proceeding",
                "attempt": attempt,
                "max_attempts": MAX_PHASE_ATTEMPTS,
            })
            review = self._feedback_provider.request_feedback(phase, agent_name, output)
            action = review.get("action", "approve")
            feedback = review.get("feedback", "")
            self._emit({
                "type": "human_feedback_response",
                "phase": phase,
                "action": action,
                "feedback": feedback,
                "attempt": attempt,
                "max_attempts": MAX_PHASE_ATTEMPTS,
            })
            if action != "revise":
                self._complete_phase(phase)
                return output
            if attempt == MAX_PHASE_ATTEMPTS:
                raise RuntimeError(f"Revision limit reached for phase '{phase}'.")
            prompt = _revision_prompt(self.state.user_prompt, output, feedback)

        raise RuntimeError(f"Revision limit reached for phase '{phase}'.")

    @start()
    def gather_requirements(self):
        if not self.state.context_prepared:
            upload_ctx = get_upload_context(self.state.project_id)
            if upload_ctx:
                self.state.user_prompt += upload_ctx
            connector_ctx = get_connector_context(self.state.connector_settings, user_id=self.state.user_id)
            if connector_ctx:
                self.state.user_prompt += connector_ctx
            if self.state.mode == "goal":
                self.state.user_prompt += GOAL_MODE_DIRECTIVE
            self.state.context_prepared = True
        if self.state.mode == "iterate":
            self._start_phase("building", "Engineer is reading existing files and preparing updates...")
        elif self.state.mode == "consult":
            name = {
                "team_leader": "Kai",
                "product_manager": "Nina",
                "architect": "Theo",
                "data_scientist": "Zara",
            }.get(self.state.consult_agent, "An agent")
            self._start_phase("building", f"{name} is reviewing your question...")
        elif self.state.mode == "goal":
            self._start_phase("leading", "Goal mode activated — the team will plan and build autonomously without pausing for review.")
        elif self.state.mode == "engineer":
            self._start_phase("building", "Engineer mode — Ravi is jumping straight into building your project.")
        else:
            self._start_phase("leading", "Kai is reviewing your request to understand the scope and key requirements.")
        return self.state.user_prompt

    @listen(gather_requirements)
    def run_leadership(self):
        if self.state.mode in ("engineer", "iterate", "consult"):
            return ""
        def run_attempt(prompt: str):
            leader = create_team_leader_agent(
                user_id=self.state.user_id,
                mcps=self._agent_mcps(),
                skills=self._agent_skills("team_leader"),
            )
            task = create_leadership_task(leader, prompt)
            crew = create_leadership_crew(leader, task)
            return kickoff_with_streaming(crew, self._emit, agent_hint="team_leader")

        def store_result(result, output: str):
            brief_spec = _extract_spec(result, ProjectBriefSpec)
            self.state.brief_spec = brief_spec.model_dump() if brief_spec is not None else None
            self.state.leadership_output = output

        return self._run_reviewed_phase(
            phase="leading",
            agent_name="team_leader",
            task_label="Reviewing your brief and breaking it into clear requirements",
            run_attempt=run_attempt,
            store_result=store_result,
        )

    @listen(run_leadership)
    def run_analysis(self):
        if self.state.mode in ("engineer", "iterate", "consult"):
            return ""
        self._start_phase("analyzing", "Zara is researching the market landscape and relevant technologies.")

        def run_attempt(prompt: str):
            analyst = create_data_scientist_agent(
                user_id=self.state.user_id,
                mcps=self._agent_mcps(),
                skills=self._agent_skills("data_scientist"),
            )
            leader_task = create_leadership_task(create_team_leader_agent(user_id=self.state.user_id), COMPACT_CONTEXT_PROMPT)
            leader_task._output = type("obj", (object,), {"raw": self.state.leadership_output})()
            task = create_analysis_task(analyst, prompt)
            crew = create_analysis_crew(analyst, task, context_tasks=[leader_task])
            return kickoff_with_streaming(crew, self._emit, agent_hint="data_scientist")

        def store_result(result, output: str):
            analysis_spec = _extract_spec(result, AnalysisReportSpec)
            self.state.analysis_spec = analysis_spec.model_dump() if analysis_spec is not None else None
            self.state.analysis_output = output

        return self._run_reviewed_phase(
            phase="analyzing", agent_name="data_scientist",
            task_label="Analyzing supplied evidence, users, risks, and technology options",
            run_attempt=run_attempt, store_result=store_result,
        )

    @listen(run_analysis)
    def run_planning(self):
        if self.state.mode in ("engineer", "iterate", "consult"):
            return ""
        self._start_phase("planning", "Nina is turning research and requirements into a detailed project plan.")

        def run_attempt(prompt: str):
            pm = create_pm_agent(
                user_id=self.state.user_id,
                mcps=self._agent_mcps(),
                skills=self._agent_skills("product_manager"),
            )
            analysis_task = create_analysis_task(create_data_scientist_agent(user_id=self.state.user_id), COMPACT_CONTEXT_PROMPT)
            analysis_task._output = type("obj", (object,), {"raw": self.state.analysis_output})()
            task = create_planning_task(pm, prompt)
            crew = create_planning_crew(pm, task, context_tasks=[analysis_task])
            return kickoff_with_streaming(crew, self._emit, agent_hint="product_manager")

        def store_result(result, output: str):
            plan_spec = _extract_spec(result, ProjectPlanSpec)
            self.state.plan_spec = plan_spec.model_dump() if plan_spec is not None else None
            self.state.plan_output = output

        return self._run_reviewed_phase(
            phase="planning", agent_name="product_manager",
            task_label="Defining product scope, user journeys, acceptance criteria, and milestones",
            run_attempt=run_attempt, store_result=store_result,
        )

    @listen(run_planning)
    def run_architecture(self):
        if self.state.mode in ("engineer", "iterate", "consult"):
            return ""
        self._start_phase("architecting", "Theo is designing the system architecture, component structure, and UI layout.")

        def run_attempt(prompt: str):
            architect = create_architect_agent(
                user_id=self.state.user_id,
                mcps=self._agent_mcps(),
                skills=self._agent_skills("architect"),
            )
            plan_task = create_planning_task(create_pm_agent(user_id=self.state.user_id), COMPACT_CONTEXT_PROMPT)
            plan_task._output = type("obj", (object,), {"raw": self.state.plan_output})()
            task = create_architecture_task(architect, prompt, stack=self.state.stack)
            crew = create_architecture_crew(architect, task, context_tasks=[plan_task])
            return kickoff_with_streaming(crew, self._emit, agent_hint="architect")

        def store_result(result, output: str):
            architecture_spec = _extract_spec(result, ArchitectureSpec)
            self.state.architecture_spec = architecture_spec.model_dump() if architecture_spec is not None else None
            self.state.architecture_output = output

        return self._run_reviewed_phase(
            phase="architecting", agent_name="architect",
            task_label="Designing a directly served static architecture and UI specification",
            run_attempt=run_attempt, store_result=store_result,
        )

    def _engineering_context_tasks(self):
        context_tasks = []
        if self.state.architecture_output:
            arch_task = create_architecture_task(create_architect_agent(user_id=self.state.user_id), COMPACT_CONTEXT_PROMPT)
            arch_task._output = type("obj", (object,), {"raw": self.state.architecture_output})()
            context_tasks.append(arch_task)
        if self.state.plan_output:
            plan_task = create_planning_task(create_pm_agent(user_id=self.state.user_id), COMPACT_CONTEXT_PROMPT)
            plan_task._output = type("obj", (object,), {"raw": self.state.plan_output})()
            context_tasks.append(plan_task)
        return context_tasks

    def _track_code_writer(self, code_writer: CodeWriterTool) -> None:
        original_run = code_writer._run

        def tracked_run(file_path: str, content: str) -> str:
            result = original_run(file_path=file_path, content=content)
            self._writes_this_run += 1
            # Track in a plain list (PrivateAttr) rather than mutating state model
            # during the long-running engineering crew. We only write the list back
            # into self.state (triggering Pydantic bookkeeping) at safe points after
            # crew kickoffs complete. This avoids "dictionary changed size during
            # iteration" panics inside CrewAI checkpoint listener's model_dump.
            if file_path not in self._files_created:
                self._files_created.append(file_path)
            if file_path not in self._files_written_this_run:
                self._files_written_this_run.append(file_path)
            self._emit({"type": "file_created", "file_path": file_path, "content": content})
            return result

        code_writer._run = tracked_run

    def _missing_required_files(self) -> list[str]:
        # Union private tracker + persisted state so that in-flight or restored
        # file lists are considered even if sync hasn't happened yet.
        seen = set(self._files_created) | set(self.state.files_created or [])
        required = required_files_for_stack(self.state.stack)
        # Also count files that exist on disk (agents may write without tracking edge cases).
        project_dir = settings.projects_dir / self.state.project_id
        for name in required:
            if (project_dir / name).is_file():
                seen.add(name)
        return [name for name in required if name not in seen]

    def _sync_files_created(self) -> None:
        """Copy private tracker into the Pydantic state at quiescent points.

        Called after engineering (and recovery) crews return so that
        self.state.files_created is up to date for checkpoints, finalize(),
        and _ensure checks. The assignment is the only time we touch the
        pydantic list field for files during/after a crew run.
        """
        self.state.files_created = list(self._files_created)

    def _load_project_file_contents(self) -> dict[str, str]:
        project_dir = settings.projects_dir / self.state.project_id
        contents: dict[str, str] = {}
        for name in required_files_for_stack(self.state.stack):
            path = project_dir / name
            if path.is_file():
                try:
                    contents[name] = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
        # Static navigation checks also inspect any HTML written this run.
        if normalize_stack(self.state.stack) == "static":
            for name in self._files_created:
                if name.endswith(".html") and name not in contents:
                    path = project_dir / name
                    if path.is_file():
                        try:
                            contents[name] = path.read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError):
                            continue
        return contents

    def _navigation_violations(self) -> list[str]:
        # App Router links are valid for Next.js — skip static nav contract.
        if normalize_stack(self.state.stack) == "nextjs":
            return []
        return find_project_navigation_violations(self._load_project_file_contents())

    def _run_navigation_recovery(self, engineer, context_tasks, violations: list[str]):
        self._emit({
            "type": "stream_chunk",
            "agent": "engineer",
            "content": "Navigation used forbidden root-relative routes. Rewriting index.html and app.js...",
        })
        recovery_task = create_navigation_recovery_task(engineer, self.state.user_prompt, violations)
        crew = create_engineering_crew(engineer, recovery_task, context_tasks=context_tasks)
        result = kickoff_with_streaming(crew, self._emit, agent_hint="engineer")
        self._accumulate_tokens(result)
        return _safe_raw(result)

    def _run_engineering_recovery(self, engineer, context_tasks, missing_files: list[str]):
        self._emit({
            "type": "stream_chunk",
            "agent": "engineer",
            "content": f"Missing required files: {', '.join(missing_files)}. Retrying those file writes...",
        })
        recovery_tasks = create_engineering_recovery_tasks(
            engineer,
            self.state.user_prompt,
            missing_files=missing_files,
            stack=self.state.stack,
        )
        crew = create_engineering_recovery_crew(engineer, recovery_tasks, context_tasks=context_tasks)
        result = kickoff_with_streaming(crew, self._emit, agent_hint="engineer")
        self._accumulate_tokens(result)
        return result

    def _ensure_engineering_files_created(self):
        missing = self._missing_required_files()
        if missing:
            raise RuntimeError(f"{NO_FILES_WRITTEN_ERROR} Missing: {', '.join(missing)}")

    def _run_consult(self) -> str:
        """Post-build advisory response from Kai/Nina/Theo/Zara (no file writes)."""
        agent_key = self.state.consult_agent or "team_leader"
        creators = {
            "team_leader": (create_team_leader_agent, "team_leader", "Kai is advising on scope and priorities"),
            "product_manager": (create_pm_agent, "product_manager", "Nina is advising on product direction"),
            "architect": (create_architect_agent, "architect", "Theo is advising on structure and design"),
            "data_scientist": (create_data_scientist_agent, "data_scientist", "Zara is advising on data and metrics"),
        }
        create_fn, agent_hint, task_label = creators.get(
            agent_key,
            (create_team_leader_agent, "team_leader", "Reviewing your question"),
        )
        self._emit({"type": "agent_start", "agent": agent_hint, "task": task_label})
        self.state.status = "building"
        agent = create_fn(
            user_id=self.state.user_id,
            mcps=self._agent_mcps(),
            skills=self._agent_skills(agent_hint),
        )
        task = create_consult_task(
            agent,
            self.state.user_prompt,
            self.state.iteration_request,
            agent_key,
        )
        crew = create_consult_crew(agent, task)
        result = kickoff_with_streaming(crew, self._emit, agent_hint=agent_hint)
        self._accumulate_tokens(result)
        output = _safe_raw(result)
        summary = human_summary_for_result(result, output, "building") or humanize_text(
            output,
            fallback=task_label,
        )
        if looks_like_json_blob(summary) or not summary.strip():
            summary = output.strip()[:500] if output.strip() else task_label
        self._emit({
            "type": "agent_complete",
            "agent": agent_hint,
            "content": summary,
            "summary": summary,
        })
        self._emit(
            build_phase_result_event(
                phase="building",
                agent=agent_hint,
                result=result,
                output_text=output,
                task_label=task_label,
            )
        )
        self._complete_phase("building")
        self.state.engineering_output = output
        return output

    @listen(run_architecture)
    def run_engineering(self):
        if self.state.mode == "consult":
            return self._run_consult()

        if self.state.mode not in ("engineer", "iterate"):
            self._start_phase("building", "Ravi is translating the architecture into working code.")
        task_label = "Reading existing files and applying your changes" if self.state.mode == "iterate" else "Writing HTML, CSS, and JavaScript files"
        self._emit({"type": "agent_start", "agent": "engineer", "task": task_label})
        self.state.status = "building"
        self._writes_this_run = 0
        self._files_written_this_run = []

        # Seed from persisted state (for resumes/iterates that re-enter engineering)
        for f in self.state.files_created or []:
            if f not in self._files_created:
                self._files_created.append(f)

        if self.state.mode == "iterate":
            snapshot_before_edit(self.state.project_id, self.state.iteration_request)

        code_writer = CodeWriterTool(project_id=self.state.project_id)
        file_reader = FileReaderTool(project_id=self.state.project_id)
        tools = [code_writer, file_reader]
        # Always expose sanitized connector status; live MCP tools come from `mcps`.
        tools.append(
            ConnectorContextTool(
                connector_settings=self.state.connector_settings,
                user_id=self.state.user_id,
            )
        )
        engineer = create_engineer_agent(
            tools=tools,
            user_id=self.state.user_id,
            mcps=self._agent_mcps(),
            skills=self._agent_skills("engineer"),
        )
        context_tasks = self._engineering_context_tasks()
        self._track_code_writer(code_writer)

        if self.state.mode == "iterate":
            eng_task = create_iteration_task(
                engineer,
                self.state.user_prompt,
                self.state.iteration_request,
                stack=self.state.stack,
            )
        else:
            eng_task = create_engineering_task(
                engineer,
                self.state.user_prompt,
                stack=self.state.stack,
            )
        crew = create_engineering_crew(engineer, eng_task, context_tasks=context_tasks)
        result = kickoff_with_streaming(crew, self._emit, agent_hint="engineer")
        self._accumulate_tokens(result)
        self._sync_files_created()
        output = _safe_raw(result)

        if self.state.mode == "iterate":
            if self._writes_this_run == 0:
                raise RuntimeError(ITERATION_NO_FILES_WRITTEN_ERROR)
        else:
            missing_files = self._missing_required_files()
            if missing_files:
                recovery_result = self._run_engineering_recovery(engineer, context_tasks, missing_files)
                output = _safe_raw(recovery_result)
                self._sync_files_created()
            self._ensure_engineering_files_created()

        nav_violations = self._navigation_violations()
        if nav_violations:
            output = self._run_navigation_recovery(engineer, context_tasks, nav_violations)
            self._sync_files_created()
            nav_violations = self._navigation_violations()
            if nav_violations:
                raise RuntimeError(f"{INVALID_NAVIGATION_ERROR}: {'; '.join(nav_violations)}")

        files_written = list(self._files_created)
        changed_this_run = list(self._files_written_this_run)
        # Engineering tasks often return free-form markdown (file inventories).
        # human_summary_for_result strips inventory dumps; fall back to a short
        # human default when no prose paragraph is available.
        prose_summary = human_summary_for_result(result, output, "building")
        if self.state.mode == "iterate":
            if changed_this_run:
                default_summary = (
                    f"Updated {len(changed_this_run)} file"
                    f"{'s' if len(changed_this_run) != 1 else ''}: "
                    f"{', '.join(changed_this_run[:6])}"
                    f"{'…' if len(changed_this_run) > 6 else ''}."
                )
            else:
                default_summary = "Updated the existing project based on your request."
        else:
            default_summary = (
                f"Wrote {len(files_written)} project file"
                f"{'s' if len(files_written) != 1 else ''} and wired the core browser interactions."
                if files_written
                else "Wrote the browser-native project files and wired the core interactions."
            )
        checklist = build_quality_checklist(
            self.state.project_id,
            files_written,
            stack=self.state.stack,
        )
        known_gaps = []
        if not checklist.get("seeded_demo_data"):
            known_gaps.append("Demo data may be thin — use “Fill with mock data” if the preview looks empty.")
        build_summary = BuildSummarySpec(
            headline="Project files ready" if self.state.mode != "iterate" else "Focused edit applied",
            summary=prose_summary or default_summary,
            files_written=changed_this_run if self.state.mode == "iterate" and changed_this_run else files_written,
            behaviors_implemented=[
                item
                for item in [
                    "Directly served static entry point",
                    "Responsive styles",
                    "Client-side interactions and navigation",
                    "Seeded demo data on first load" if checklist.get("seeded_demo_data") else "",
                ]
                if item
            ],
            known_gaps=known_gaps,
        )
        self.state.build_summary_spec = build_summary.model_dump()
        self.state.engineering_output = output
        summary = build_summary.summary
        self._emit({
            "type": "agent_complete",
            "agent": "engineer",
            "content": summary,
            "summary": summary,
        })
        self._emit(
            build_phase_result_event(
                phase="building",
                agent="engineer",
                result=type("obj", (object,), {"pydantic": build_summary, "raw": output})(),
                output_text=output,
                task_label=task_label,
            )
        )
        if self.state.mode == "iterate":
            try:
                diff_payload = finalize_edit_snapshot(
                    self.state.project_id,
                    list(self._files_written_this_run),
                )
                self._emit({
                    "type": "edit_diff",
                    "files_changed": diff_payload.get("files_changed") or [],
                    "diffs": diff_payload.get("diffs") or [],
                    "can_undo": bool(diff_payload.get("can_undo")),
                    "message": "File changes ready to review.",
                })
            except Exception:
                # Diff is best-effort; never fail the build over presentation.
                pass
        self._complete_phase("building")
        return output

    @listen(run_engineering)
    def finalize(self):
        self.state.status = "complete"
        usage_payload = self.state.token_usage.model_dump()
        update_project_token_usage(
            self.state.project_id,
            **usage_payload,
            token_budget=settings.max_build_tokens,
        )
        if self.state.mode == "iterate":
            changed = list(self._files_written_this_run)
            if changed:
                message = (
                    f"Update applied — changed {len(changed)} file"
                    f"{'s' if len(changed) != 1 else ''}."
                )
            else:
                message = "Project updated!"
        elif self.state.mode == "consult":
            name = {
                "team_leader": "Kai",
                "product_manager": "Nina",
                "architect": "Theo",
                "data_scientist": "Zara",
            }.get(self.state.consult_agent, "Agent")
            message = f"{name} finished advising. Ask @ravi to implement any changes."
        elif self.state.mode == "goal":
            message = "Goal mode build complete!"
        else:
            message = "Project generation complete!"

        files = list(self.state.files_created or self._files_created)
        changed_files = list(self._files_written_this_run)
        checklist = build_quality_checklist(
            self.state.project_id,
            files,
            stack=self.state.stack,
        )
        suggestions = follow_up_suggestions(checklist=checklist, mode=self.state.mode)

        self._emit({
            "type": "project_complete",
            "files": files,
            "files_changed": changed_files,
            "mode": self.state.mode,
            "message": message,
            "checklist": checklist,
            "suggestions": suggestions,
            "usage": usage_payload,
            "token_budget": settings.max_build_tokens,
            "percent": 100,
            "can_undo": self.state.mode == "iterate" and bool(changed_files),
        })
        return self.state
