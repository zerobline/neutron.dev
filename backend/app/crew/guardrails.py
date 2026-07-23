import re
from typing import Any

from app.crew.schemas import (
    AnalysisReportSpec,
    ArchitectureSpec,
    ProjectBriefSpec,
    ProjectPlanSpec,
    REQUIRED_PROJECT_FILES,
)

UNSUPPORTED_STATIC_RUNTIME_TERMS = (
    "next.js",
    "nextjs",
    "react",
    "jsx",
    "tsx",
    "npm run",
    "webpack",
    "vite",
    "server-side rendering",
    "server route",
)


def _output_text(output: Any) -> str:
    raw = getattr(output, "raw", output)
    if isinstance(raw, str):
        return raw
    return str(raw)


def validate_project_brief(output: Any) -> tuple[bool, Any]:
    spec = getattr(output, "pydantic", None)
    if isinstance(spec, ProjectBriefSpec):
        if not spec.target_users:
            return (False, "Project brief must include at least one target user.")
        if not spec.functional_requirements:
            return (False, "Project brief must include at least one functional requirement.")
        if not spec.mvp_inclusions:
            return (False, "Project brief must include at least one MVP inclusion.")
        if not spec.success_criteria:
            return (False, "Project brief must include at least one success criterion.")
        return (True, output)

    text = _output_text(output)
    if len(text.split()) < 60:
        return (
            False,
            "Project brief is too short. Include intent, users, requirements, MVP scope, and success criteria.",
        )
    return (True, output)


def validate_analysis_report(output: Any) -> tuple[bool, Any]:
    spec = getattr(output, "pydantic", None)
    if isinstance(spec, AnalysisReportSpec):
        if not spec.workflows:
            return (False, "Analysis report must include at least one workflow.")
        if not spec.recommendations:
            return (False, "Analysis report must include at least one recommendation.")
        return (True, output)

    text = _output_text(output)
    if len(text.split()) < 70:
        return (
            False,
            "Analysis report is too short. Include workflows, risks, recommendations, and evidence gaps.",
        )
    return (True, output)


def validate_project_plan(output: Any) -> tuple[bool, Any]:
    spec = getattr(output, "pydantic", None)
    if isinstance(spec, ProjectPlanSpec):
        if not spec.pages:
            return (False, "Project plan must include at least one page.")
        if not spec.mvp_features:
            return (False, "Project plan must include at least one MVP feature.")
        if not spec.milestones:
            return (False, "Project plan must include at least one milestone.")
        return (True, output)

    text = _output_text(output)
    if len(text.split()) < 80:
        return (
            False,
            "Project plan is too short. Include overview, MVP features, pages, product data needs, and milestones.",
        )
    return (True, output)


def _unsupported_runtime_term(text: str) -> str | None:
    lowered = text.lower()
    for term in UNSUPPORTED_STATIC_RUNTIME_TERMS:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")
        for match in pattern.finditer(lowered):
            clause_boundaries = list(re.finditer(r"[;:\n]|[.!?](?=\s|$)", lowered))
            clause_start = max(
                (boundary.end() for boundary in clause_boundaries if boundary.end() <= match.start()),
                default=0,
            )
            clause_end = min(
                (boundary.start() for boundary in clause_boundaries if boundary.start() >= match.end()),
                default=len(lowered),
            )
            prefix = lowered[clause_start:match.start()]
            suffix = lowered[match.end():clause_end]
            negated_before = re.search(
                r"(?:\bno\b|\bnot\b|\bwithout\b|\bnever\b|\bavoid(?:s|ed|ing)?\b|\bdo(?:es)?\s+not\b)"
                r".{0,120}$",
                prefix,
            )
            negated_after = re.match(r"s?\s+(?:(?:is|are|was|were|will be)\s+)?not\b", suffix)
            if negated_before or negated_after:
                continue
            return term
    return None


def validate_architecture_spec(output: Any, *, stack: str = "static") -> tuple[bool, Any]:
    from app.crew.stacks import normalize_stack, required_files_for_stack

    stack_name = normalize_stack(stack)
    required = required_files_for_stack(stack_name)
    spec = getattr(output, "pydantic", None)
    if isinstance(spec, ArchitectureSpec):
        missing = [name for name in required if name not in spec.required_files]
        if missing:
            return (
                False,
                f"Architecture spec must list required files for {stack_name}: {', '.join(missing)}",
            )
        if stack_name == "static":
            architecture_text = " ".join(
                [
                    spec.system_overview,
                    *spec.components,
                    *spec.layouts,
                    *spec.component_specs,
                    *spec.external_dependencies,
                ]
            )
            unsupported = _unsupported_runtime_term(architecture_text)
            if unsupported:
                return (
                    False,
                    f"Architecture must be directly servable without unsupported runtime requirement '{unsupported}'.",
                )
        return (True, output)

    text = _output_text(output).lower()
    for required_name in required:
        if required_name.lower() not in text:
            return (
                False,
                f"Architecture output must mention required file '{required_name}' in required_files.",
            )
    if stack_name == "static":
        unsupported = _unsupported_runtime_term(text)
        if unsupported:
            return (
                False,
                f"Architecture must be directly servable without unsupported runtime requirement '{unsupported}'.",
            )
    return (True, output)


def make_architecture_guardrail(stack: str = "static"):
    """CrewAI guardrail factory so architecture validation matches the project stack."""

    def _guardrail(output: Any) -> tuple[bool, Any]:
        return validate_architecture_spec(output, stack=stack)

    return _guardrail
