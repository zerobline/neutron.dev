"""Guardrails for browser-native static app navigation patterns."""

from __future__ import annotations

import re

ROOT_HREF_PATTERN = re.compile(r"""href\s*=\s*['"]/[^'"]*['"]""", re.IGNORECASE)
ROOT_IFRAME_SRC_PATTERN = re.compile(
    r"""<iframe\b[^>]*\bsrc\s*=\s*['"]/[^'"]*['"]""",
    re.IGNORECASE,
)
ROOT_DATA_ROUTE_PATTERN = re.compile(
    r"""data-(?:tab|page|view|route|href|panel)\s*=\s*['"]/[^'"]*['"]""",
    re.IGNORECASE,
)
ROOT_LOCATION_PATTERN = re.compile(
    r"""(?:window\.|document\.)?location(?:\.href)?\s*(?:=\s*|\.\s*(?:assign|replace)\s*\(\s*)['"]/[^'"]*['"]""",
    re.IGNORECASE,
)
ROOT_PUSH_STATE_PATTERN = re.compile(
    r"""history\.(?:push|replace)State\([^)]*['"]/[^'"]*['"]""",
    re.IGNORECASE,
)

NAVIGATION_CONTRACT = (
    "STATIC NAVIGATION CONTRACT (mandatory for every generated app):\n"
    "- Model each page/tab/section as a sibling element in index.html, e.g. "
    '<section data-panel="transactions" hidden>...</section>\n'
    "- Use <button type=\"button\" data-tab=\"transactions\"> (or role=\"tab\") for nav controls\n"
    "- In app.js, bind nav clicks and toggle panel visibility with classList/hidden/aria-selected\n"
    "- Use hash routing (#transactions) if URL state is needed\n"
    "- NEVER use href=\"/...\", iframe src=\"/...\", data-tab=\"/...\", location.assign(\"/...\"), "
    "history.pushState(..., \"/...\"), or any root-relative app route\n"
    "- Asset references must stay relative: ./styles.css and ./app.js only"
)


def find_navigation_violations(content: str, file_name: str) -> list[str]:
    violations: list[str] = []
    if file_name.endswith(".html"):
        for pattern, label in (
            (ROOT_HREF_PATTERN, "root-relative href"),
            (ROOT_IFRAME_SRC_PATTERN, "iframe loading a root-relative route"),
            (ROOT_DATA_ROUTE_PATTERN, "root-relative data-* route attribute"),
        ):
            if pattern.search(content):
                violations.append(f"{file_name} contains {label}")
    if file_name.endswith(".js"):
        for pattern, label in (
            (ROOT_LOCATION_PATTERN, "location navigation to a root-relative route"),
            (ROOT_PUSH_STATE_PATTERN, "history navigation to a root-relative route"),
        ):
            if pattern.search(content):
                violations.append(f"{file_name} contains {label}")
    return violations


def find_project_navigation_violations(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for file_name, content in files.items():
        violations.extend(find_navigation_violations(content, file_name))
    return violations