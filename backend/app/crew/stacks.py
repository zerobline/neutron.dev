"""Build stack definitions (static HTML vs Next.js) for templates and engineering."""

from __future__ import annotations

from typing import Literal

BuildStack = Literal["static", "nextjs"]

DEFAULT_STACK: BuildStack = "static"

REQUIRED_STATIC_FILES = ("index.html", "styles.css", "app.js")

# Minimum runnable Next.js App Router scaffold the engineer must write.
REQUIRED_NEXTJS_FILES = (
    "package.json",
    "tsconfig.json",
    "next.config.mjs",
    "app/layout.tsx",
    "app/page.tsx",
    "app/globals.css",
)

STACK_LABELS: dict[str, str] = {
    "static": "HTML / CSS / JS",
    "nextjs": "Next.js",
}


def normalize_stack(value: object) -> BuildStack:
    if isinstance(value, str) and value.strip().lower() in {"static", "nextjs"}:
        return value.strip().lower()  # type: ignore[return-value]
    return DEFAULT_STACK


def required_files_for_stack(stack: object) -> tuple[str, ...]:
    return REQUIRED_NEXTJS_FILES if normalize_stack(stack) == "nextjs" else REQUIRED_STATIC_FILES


def stack_accepts_required_files(files: list[str], stack: object | None = None) -> bool:
    """True if files satisfy the given stack, or either stack when stack is None."""
    normalized = [item.strip().lstrip("./") for item in files if item and item.strip()]
    if stack is None:
        static_ok = all(name in normalized for name in REQUIRED_STATIC_FILES)
        next_ok = all(name in normalized for name in REQUIRED_NEXTJS_FILES)
        return static_ok or next_ok
    required = required_files_for_stack(stack)
    return all(name in normalized for name in required)
