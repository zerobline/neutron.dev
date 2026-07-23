"""Post-build completion helpers: quality checklist + suggested next actions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.crew.stacks import normalize_stack, required_files_for_stack

# Heuristic: app.js (or similar) contains seed arrays of objects for demo UI.
_SEEDED_ARRAY_RE = re.compile(
    r"(?:const|let|var)\s+\w+\s*=\s*\[\s*\{",
    re.MULTILINE,
)
_OBJECT_LITERAL_RE = re.compile(r"\{\s*['\"]?\w+['\"]?\s*:")


FOLLOW_UP_SUGGESTIONS: list[dict[str, str]] = [
    {
        "id": "mock_data",
        "label": "Fill with mock data",
        "prompt": (
            "@engineer Fill the app with realistic mock data so tables, cards, lists, "
            "and charts look populated on first load (at least 6–12 demo rows)."
        ),
    },
    {
        "id": "dark_mode",
        "label": "Add dark mode",
        "prompt": (
            "@engineer Add a polished dark mode toggle in the header and persist the "
            "preference in localStorage without breaking existing styles."
        ),
    },
    {
        "id": "mobile",
        "label": "Improve mobile",
        "prompt": (
            "@engineer Improve the mobile layout and touch-friendly navigation while "
            "keeping the desktop experience intact."
        ),
    },
    {
        "id": "polish",
        "label": "Polish the UI",
        "prompt": (
            "@engineer Polish spacing, typography, hover states, and empty/loading states "
            "so the UI feels production-ready."
        ),
    },
    {
        "id": "export",
        "label": "Add export / share",
        "prompt": (
            "@engineer Add a simple export or share action (e.g. download JSON/CSV or "
            "copy a shareable summary) that fits this app."
        ),
    },
]


def project_dir_for(project_id: str) -> Path:
    return settings.projects_dir / project_id


def _read_text_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def has_seeded_demo_data(project_id: str) -> bool:
    """Best-effort check that JS/TS includes seeded demo collections."""
    root = project_dir_for(project_id)
    candidates = [
        root / "app.js",
        root / "main.js",
        root / "script.js",
        root / "data.js",
        root / "app" / "page.tsx",
        root / "app" / "data.ts",
        root / "lib" / "data.ts",
        root / "lib" / "mock-data.ts",
    ]
    # Also scan a few shallow app/**/*.tsx files for seed arrays.
    app_dir = root / "app"
    if app_dir.is_dir():
        for path in list(app_dir.rglob("*.tsx"))[:20] + list(app_dir.rglob("*.ts"))[:20]:
            if path.is_file():
                candidates.append(path)

    for path in candidates:
        text = _read_text_if_exists(path)
        if not text:
            continue
        if _SEEDED_ARRAY_RE.search(text) and len(_OBJECT_LITERAL_RE.findall(text)) >= 3:
            return True
        # Long enough array literals with multiple objects
        if text.count("[{") + text.count("[ {") >= 1 and text.count("{") >= 6:
            return True
    return False


def build_quality_checklist(
    project_id: str,
    files: list[str] | None = None,
    *,
    stack: str = "static",
) -> dict[str, Any]:
    root = project_dir_for(project_id)
    present = set(files or [])
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                present.add(path.relative_to(root).as_posix())

    stack_name = normalize_stack(stack)
    required = required_files_for_stack(stack_name)
    required_ok = all(name in present or (root / name).is_file() for name in required)
    has_index = "index.html" in present or (root / "index.html").is_file()
    has_css = any(name.endswith(".css") for name in present) or (root / "styles.css").is_file()
    has_js = (
        any(name.endswith((".js", ".tsx", ".ts", ".jsx")) for name in present)
        or (root / "app.js").is_file()
    )
    has_package = "package.json" in present or (root / "package.json").is_file()
    seeded = has_seeded_demo_data(project_id)

    if stack_name == "nextjs":
        items = [
            {
                "id": "required_files",
                "label": "Next.js scaffold written",
                "ok": required_ok,
                "detail": "package.json, app router entry, globals.css, config",
            },
            {
                "id": "entry_point",
                "label": "App Router home page",
                "ok": "app/page.tsx" in present or (root / "app/page.tsx").is_file(),
                "detail": "app/page.tsx is present",
            },
            {
                "id": "styles",
                "label": "Global styles",
                "ok": has_css,
                "detail": "CSS / design tokens included",
            },
            {
                "id": "interactions",
                "label": "React / client UI",
                "ok": has_js,
                "detail": "TSX/TS modules power the UI",
            },
            {
                "id": "package_json",
                "label": "npm project ready",
                "ok": has_package,
                "detail": "Download ZIP then run npm install && npm run dev",
            },
            {
                "id": "seeded_demo_data",
                "label": "Demo data seeded",
                "ok": seeded,
                "detail": (
                    "Lists should look populated on first load"
                    if seeded
                    else "UI may look empty — try “Fill with mock data”"
                ),
            },
        ]
    else:
        items = [
            {
                "id": "required_files",
                "label": "Core files written",
                "ok": required_ok,
                "detail": "index.html, styles.css, and app.js",
            },
            {
                "id": "entry_point",
                "label": "Preview entry point",
                "ok": has_index,
                "detail": "index.html is ready to open",
            },
            {
                "id": "styles",
                "label": "Styles included",
                "ok": has_css,
                "detail": "CSS is linked for layout and polish",
            },
            {
                "id": "interactions",
                "label": "Client interactions",
                "ok": has_js,
                "detail": "JavaScript powers navigation and UI behavior",
            },
            {
                "id": "seeded_demo_data",
                "label": "Demo data seeded",
                "ok": seeded,
                "detail": (
                    "Lists and tables should look populated on first load"
                    if seeded
                    else "UI may look empty — try “Fill with mock data”"
                ),
            },
        ]

    return {
        "required_files": required_ok,
        "entry_point": has_index if stack_name == "static" else required_ok,
        "styles": has_css,
        "interactions": has_js,
        "seeded_demo_data": seeded,
        "stack": stack_name,
        "file_count": len(present),
        "items": items,
    }


def follow_up_suggestions(*, checklist: dict[str, Any] | None = None, mode: str = "team") -> list[dict[str, str]]:
    """Order suggestions so the most useful next action is first."""
    suggestions = [dict(item) for item in FOLLOW_UP_SUGGESTIONS]
    seeded = bool((checklist or {}).get("seeded_demo_data"))
    if seeded:
        # Mock data already present — promote polish / dark mode.
        suggestions = [s for s in suggestions if s["id"] != "mock_data"] + [
            s for s in suggestions if s["id"] == "mock_data"
        ]
    if mode == "iterate":
        # After a focused edit, polish and mobile are common next steps.
        order = ["polish", "mobile", "dark_mode", "export", "mock_data"]
        rank = {sid: i for i, sid in enumerate(order)}
        suggestions.sort(key=lambda s: rank.get(s["id"], 99))
    return suggestions[:4]
