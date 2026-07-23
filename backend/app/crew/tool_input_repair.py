"""Repair mangled CrewAI tool Action Input before tools run.

LLMs (especially under ReAct + json_repair) often emit tool args as:
- a JSON *array* of partial objects instead of one object
- keys with leading/trailing spaces (e.g. ``" content"``)
- content strings that leak trailing ``Thought:`` / ``Action:`` text

CrewAI's ``ToolUsage._validate_tool_input`` only accepts a plain dict and
otherwise fails with "not a valid key, value dictionary", so required files
never get written. We monkey-patch that method to coerce common failure modes.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from json import JSONDecodeError
from typing import Any

logger = logging.getLogger(__name__)

_REACT_LEAK_MARKERS = (
    "\nThought:",
    "\nAction:",
    "\nAction Input:",
    "\nObservation:",
    "\nFinal Answer:",
)

_PATCHED = False


def _normalize_rel_path(path: str) -> str:
    """Normalize a relative path without treating '.' as a character class for lstrip."""
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _strip_react_leak(text: str) -> str:
    """Remove ReAct protocol text accidentally appended to file content."""
    if not text:
        return text
    cut = len(text)
    for marker in _REACT_LEAK_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < cut:
            # Only cut if there is meaningful content before the leak.
            if idx >= 40:
                cut = idx
    cleaned = text if cut == len(text) else text[:cut].rstrip()
    # Drop an unclosed fence if the model started ```tsx then leaked.
    if cleaned.count("```") % 2 == 1:
        cleaned = cleaned.rsplit("```", 1)[0].rstrip()
    return cleaned


def _normalize_keys(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        k = str(key).strip()
        if k in out and k not in {"content", "file_path"}:
            continue
        # Prefer non-empty values when duplicates appear after strip.
        if k in out and (value is None or value == ""):
            continue
        out[k] = value
    return out


def _pick_write_payload(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the best {file_path, content} object from a list of dicts."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for raw in candidates:
        item = _normalize_keys(raw)
        path = item.get("file_path") or item.get("path") or item.get("filename")
        content = item.get("content") or item.get("file_content") or item.get("code")
        if path is None:
            continue
        score = 0
        if content is not None and str(content).strip():
            score += 10 + min(len(str(content)), 5000) // 100
        if str(path).endswith((".tsx", ".ts", ".jsx", ".js", ".css", ".json", ".mjs", ".html")):
            score += 2
        payload = {
            "file_path": _normalize_rel_path(str(path)),
            "content": _strip_react_leak(str(content) if content is not None else ""),
        }
        scored.append((score, payload))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best = scored[0][1]
    if not best["content"]:
        return None
    return best


def coerce_tool_arguments(arguments: Any, *, tool_name: str | None = None) -> dict[str, Any] | None:
    """Coerce repaired / partial tool arguments into a single kwargs dict."""
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        normalized = _normalize_keys(arguments)
        # Single-object write payload with alternate key names
        if tool_name and "write" in tool_name.lower():
            path = normalized.get("file_path") or normalized.get("path") or normalized.get("filename")
            content = normalized.get("content") or normalized.get("file_content") or normalized.get("code")
            if path is not None and content is not None:
                return {
                    "file_path": _normalize_rel_path(str(path)),
                    "content": _strip_react_leak(str(content)),
                }
        if "content" in normalized and isinstance(normalized["content"], str):
            normalized["content"] = _strip_react_leak(normalized["content"])
        if "file_path" in normalized and isinstance(normalized["file_path"], str):
            normalized["file_path"] = _normalize_rel_path(normalized["file_path"])
        return normalized

    if isinstance(arguments, list):
        dicts = [item for item in arguments if isinstance(item, dict)]
        if not dicts:
            return None
        # write_code_file often arrives as [noise_obj, {file_path, content}, ...]
        if tool_name is None or "write" in (tool_name or "").lower() or "code" in (tool_name or "").lower():
            picked = _pick_write_payload(dicts)
            if picked:
                return picked
        # Generic: merge later keys over earlier ones
        merged: dict[str, Any] = {}
        for item in dicts:
            merged.update(_normalize_keys(item))
        if "content" in merged and isinstance(merged["content"], str):
            merged["content"] = _strip_react_leak(merged["content"])
        if "file_path" in merged and isinstance(merged["file_path"], str):
            merged["file_path"] = _normalize_rel_path(str(merged["file_path"]))
        return merged if merged else None

    return None


def _parse_loose(tool_input: str) -> Any:
    """Parse tool input string with several fallbacks (mirrors CrewAI order)."""
    text = tool_input.strip()
    # Strip accidental markdown fences around JSON.
    fence = re.match(r"^```(?:json|javascript|js)?\s*([\s\S]*?)\s*```$", text, re.I)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except (JSONDecodeError, TypeError):
        pass

    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass

    try:
        import json5

        return json5.loads(text)
    except Exception:
        pass

    try:
        from json_repair import repair_json

        repaired = str(repair_json(text, skip_json_loads=True))
        return json.loads(repaired)
    except Exception:
        return None


def install_tool_input_repair() -> None:
    """Monkey-patch CrewAI ToolUsage._validate_tool_input once."""
    global _PATCHED
    if _PATCHED:
        return
    try:
        from crewai.tools.tool_usage import ToolUsage
    except Exception:
        logger.exception("Could not import CrewAI ToolUsage for input repair")
        return

    original = ToolUsage._validate_tool_input

    def _validate_tool_input(self: Any, tool_input: str | None) -> dict[str, Any]:
        tool_name = None
        try:
            action = getattr(self, "action", None)
            tool_name = getattr(action, "tool", None) if action is not None else None
        except Exception:
            tool_name = None

        if tool_input is None:
            return {}
        if not isinstance(tool_input, str) or not tool_input.strip():
            raise Exception(
                "Tool input must be a valid dictionary in JSON or Python literal format"
            )

        # First try original path (dict-only success cases stay unchanged).
        try:
            return original(self, tool_input)
        except Exception as original_error:
            parsed = _parse_loose(tool_input)
            coerced = coerce_tool_arguments(parsed, tool_name=str(tool_name) if tool_name else None)
            if coerced is not None and isinstance(coerced, dict):
                logger.warning(
                    "Repaired tool Action Input for %s (keys=%s)",
                    tool_name or "unknown",
                    list(coerced.keys()),
                )
                return coerced
            raise original_error

    ToolUsage._validate_tool_input = _validate_tool_input  # type: ignore[method-assign]
    _PATCHED = True
    logger.info("Installed CrewAI tool Action Input repair patch")
