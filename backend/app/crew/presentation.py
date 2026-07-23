"""Turn phase results into Manus-style presentation payloads for the workspace UI.

Machine-facing structured specs stay intact for the flow. This module extracts a
short human summary plus typed card data so chat never has to dump raw JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.crew.schemas import (
    AnalysisReportSpec,
    ArchitectureSpec,
    BuildSummarySpec,
    ProjectBriefSpec,
    ProjectPlanSpec,
)

PHASE_RESULT_KINDS = {
    "leading": "brief",
    "analyzing": "analysis",
    "planning": "plan",
    "architecting": "architecture",
    "building": "build",
}

_SPEC_BY_PHASE: dict[str, type[BaseModel]] = {
    "leading": ProjectBriefSpec,
    "analyzing": AnalysisReportSpec,
    "planning": ProjectPlanSpec,
    "architecting": ArchitectureSpec,
    "building": BuildSummarySpec,
}

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

# Engineering wrap-ups often dump file inventories as markdown. Those must never
# become the user-facing phase card summary.
_INVENTORY_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*)?(?:"
    r"files?\s+written|file\s+list|files?\s+created|files?\s+updated|"
    r"behaviors?\s+implemented|known\s+gaps?|implementation\s+notes?|"
    r"what\s+was\s+built|output\s+files?|project\s+files?"
    r")\b",
    re.IGNORECASE,
)
_FILE_LIKE_LINE_RE = re.compile(
    r"^(?:[-*•]\s+)?[`'\"]?[\w./\\-]+\.(html|css|js|ts|tsx|jsx|json|md|py|svg|txt)[`'\"]?\s*$",
    re.IGNORECASE,
)
_BULLET_LINE_RE = re.compile(r"^[-*•]\s+\S")


def _first_nonempty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _clip(text: str, limit: int = 320) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def looks_like_json_blob(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    if cleaned[0] in "{[":
        return True
    if cleaned.startswith("```"):
        return True
    if '"headline"' in cleaned and '"summary"' in cleaned:
        return True
    return False


def looks_like_inventory(text: str) -> bool:
    """True when text is mostly a file/behavior inventory, not a human summary."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if _INVENTORY_HEADING_RE.search(cleaned.split("\n", 1)[0].strip()):
        return True
    # Whole-doc inventory: multiple inventory headings or dense file lists.
    if len(_INVENTORY_HEADING_RE.findall(cleaned)) >= 1 and cleaned.count("\n") >= 2:
        # Only treat as inventory when body is list-heavy (not a prose paragraph
        # that merely mentions "files written").
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        non_heading = [ln for ln in lines if not ln.startswith("#")]
        if not non_heading:
            return True
        file_like = sum(1 for ln in non_heading if _FILE_LIKE_LINE_RE.match(ln))
        bullets = sum(1 for ln in non_heading if _BULLET_LINE_RE.match(ln))
        if file_like >= 2 or (bullets >= 3 and file_like + bullets >= len(non_heading) * 0.6):
            return True
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if len(lines) >= 2:
        file_like = sum(1 for ln in lines if _FILE_LIKE_LINE_RE.match(ln))
        if file_like >= max(2, int(len(lines) * 0.6)):
            return True
    return False


def _load_json_candidate(text: str) -> Any | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    candidates = [cleaned]
    for match in _JSON_FENCE_RE.finditer(cleaned):
        candidates.append(match.group(1).strip())

    # Some models emit prose then a JSON object; try the outermost braces.
    if "{" in cleaned and "}" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if end > start:
            candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
    return None


def _summary_from_mapping(data: dict[str, Any]) -> str:
    for key in ("summary", "overview", "user_intent", "system_overview", "headline"):
        value = data.get(key)
        if isinstance(value, str) and value.strip() and not looks_like_json_blob(value):
            return _clip(value)
    for key in ("recommendations", "mvp_features", "workflows", "behaviors_implemented"):
        value = data.get(key)
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, str) and item.strip()]
            if items:
                return _clip("; ".join(items[:3]))
    return ""


def _headline_from_mapping(data: dict[str, Any], fallback: str) -> str:
    for key in ("headline", "title", "name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip() and not looks_like_json_blob(value):
            return _clip(value, 80)
    summary = _summary_from_mapping(data)
    return _first_nonempty(_clip(summary, 80), fallback)


def _summary_from_prose(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if looks_like_json_blob(cleaned):
        payload = _load_json_candidate(cleaned)
        if isinstance(payload, dict):
            return _summary_from_mapping(payload)
        return ""
    if looks_like_inventory(cleaned):
        # Prefer a prose paragraph before inventory sections when present.
        blocks = [block.strip() for block in cleaned.split("\n\n") if block.strip()]
        for block in blocks:
            if block.startswith("#") or block.startswith("```"):
                continue
            if looks_like_json_blob(block) or looks_like_inventory(block):
                continue
            if _BULLET_LINE_RE.match(block) or _FILE_LIKE_LINE_RE.match(block):
                continue
            return _clip(block)
        return ""
    # Prefer the first non-heading paragraph for free-form markdown outputs.
    blocks = [block.strip() for block in cleaned.split("\n\n") if block.strip()]
    for block in blocks:
        if block.startswith("#"):
            continue
        if block.startswith("```"):
            continue
        if looks_like_json_blob(block) or looks_like_inventory(block):
            continue
        if _FILE_LIKE_LINE_RE.match(block):
            continue
        return _clip(block)
    if looks_like_json_blob(cleaned) or looks_like_inventory(cleaned):
        return ""
    return _clip(cleaned)


def extract_spec(result: Any, model_type: type[BaseModel]) -> BaseModel | None:
    spec = getattr(result, "pydantic", None)
    if isinstance(spec, model_type):
        return spec

    # CrewAI/provider path sometimes leaves only raw text/JSON even when the
    # task requested output_pydantic. Recover a validated model when possible.
    raw = getattr(result, "raw", result)
    if isinstance(raw, model_type):
        return raw
    if isinstance(raw, BaseModel):
        try:
            return model_type.model_validate(raw.model_dump())
        except ValidationError:
            return None
    if isinstance(raw, dict):
        try:
            return model_type.model_validate(raw)
        except ValidationError:
            return None
    if isinstance(raw, str):
        payload = _load_json_candidate(raw)
        if isinstance(payload, dict):
            try:
                return model_type.model_validate(payload)
            except ValidationError:
                return None
    return None


def human_summary_for_result(result: Any, output_text: str, phase: str) -> str:
    model_type = _SPEC_BY_PHASE.get(phase)
    if model_type is not None:
        spec = extract_spec(result, model_type)
        if isinstance(spec, ProjectBriefSpec):
            return _first_nonempty(spec.summary, spec.user_intent)
        if isinstance(spec, AnalysisReportSpec):
            return _first_nonempty(spec.summary, " ".join(spec.recommendations[:2]))
        if isinstance(spec, ProjectPlanSpec):
            return _first_nonempty(spec.summary, spec.overview)
        if isinstance(spec, ArchitectureSpec):
            return _first_nonempty(spec.summary, spec.system_overview)
        if isinstance(spec, BuildSummarySpec):
            return _first_nonempty(spec.summary, " ".join(spec.behaviors_implemented[:2]))

    prose = _summary_from_prose(output_text)
    if prose:
        return prose
    payload = _load_json_candidate(output_text)
    if isinstance(payload, dict):
        return _summary_from_mapping(payload)
    return ""


def headline_for_result(result: Any, output_text: str, phase: str, fallback: str) -> str:
    model_type = _SPEC_BY_PHASE.get(phase)
    if model_type is not None:
        spec = extract_spec(result, model_type)
        if isinstance(spec, ProjectBriefSpec):
            return _first_nonempty(spec.headline, _clip(spec.user_intent, 80), fallback)
        if isinstance(spec, AnalysisReportSpec):
            return _first_nonempty(spec.headline, _clip(spec.summary, 80), fallback)
        if isinstance(spec, ProjectPlanSpec):
            return _first_nonempty(spec.headline, _clip(spec.overview, 80), fallback)
        if isinstance(spec, ArchitectureSpec):
            return _first_nonempty(spec.headline, _clip(spec.system_overview, 80), fallback)
        if isinstance(spec, BuildSummarySpec):
            return _first_nonempty(spec.headline, _clip(spec.summary, 80), fallback)

    payload = _load_json_candidate(output_text)
    if isinstance(payload, dict):
        return _headline_from_mapping(payload, fallback)

    first_line = output_text.strip().splitlines()[0] if output_text.strip() else ""
    if first_line.startswith("#"):
        first_line = first_line.lstrip("#").strip()
    if looks_like_json_blob(first_line):
        return fallback
    return _first_nonempty(_clip(first_line, 80), fallback)


def humanize_text(text: str, *, fallback: str = "") -> str:
    """Return user-facing prose, never a raw JSON blob or file inventory dump."""
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    if looks_like_json_blob(cleaned):
        payload = _load_json_candidate(cleaned)
        if isinstance(payload, dict):
            return _first_nonempty(_summary_from_mapping(payload), fallback)
        return fallback
    if looks_like_inventory(cleaned):
        prose = _summary_from_prose(cleaned)
        return prose or fallback
    return _clip(cleaned)


def build_phase_result_event(
    *,
    phase: str,
    agent: str,
    result: Any,
    output_text: str,
    task_label: str,
) -> dict[str, Any]:
    kind = PHASE_RESULT_KINDS.get(phase, "markdown")
    model_type = _SPEC_BY_PHASE.get(phase)
    spec_payload: dict[str, Any] | None = None
    if model_type is not None:
        spec = extract_spec(result, model_type)
        if spec is not None:
            spec_payload = spec.model_dump()
        else:
            payload = _load_json_candidate(output_text)
            if isinstance(payload, dict):
                try:
                    recovered = model_type.model_validate(payload)
                    spec_payload = recovered.model_dump()
                except ValidationError:
                    # Keep only the human fields if full validation fails.
                    if payload.get("headline") or payload.get("summary"):
                        spec_payload = {
                            key: payload.get(key)
                            for key in ("headline", "summary")
                            if isinstance(payload.get(key), str)
                        } or None

    summary = human_summary_for_result(result, output_text, phase) or humanize_text(
        output_text,
        fallback=task_label,
    )
    headline = headline_for_result(result, output_text, phase, task_label)
    if looks_like_json_blob(summary) or looks_like_inventory(summary):
        summary = task_label
    if looks_like_json_blob(headline) or looks_like_inventory(headline):
        headline = task_label

    return {
        "type": "phase_result",
        "phase": phase,
        "agent": agent,
        "kind": kind,
        "headline": headline,
        "summary": summary,
        "content": summary,
        "spec": spec_payload,
        "has_structured_spec": isinstance(spec_payload, dict) and len(spec_payload) > 2,
    }
