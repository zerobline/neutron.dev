"""CrewAI skill packages for Neutron agents.

Skills are SKILL.md directories that inject domain instructions into agent
prompts. Built-in packs live under settings.skills_dir; custom packs live under
projects/{id}/skills/. Selection (enabled + agent targets) is stored in
projects/{id}/skills.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from app.config import settings
from app.models import (
    ProjectSkillSettings,
    ProjectSkillsResponse,
    SkillAssignment,
    SkillCatalogItem,
    SkillCreate,
)

SKILLS_FILE = "skills.json"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _settings_path(project_id: str) -> Path:
    return settings.projects_dir / project_id / SKILLS_FILE


def _project_skills_dir(project_id: str) -> Path:
    return settings.projects_dir / project_id / "skills"


def _builtin_skills_dir() -> Path:
    return settings.skills_dir


def is_valid_skill_name(name: str) -> bool:
    return bool(name) and len(name) <= 64 and SKILL_NAME_RE.fullmatch(name) is not None


def load_project_skill_settings(project_id: str) -> ProjectSkillSettings:
    path = _settings_path(project_id)
    if not path.exists():
        return ProjectSkillSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ProjectSkillSettings()
    try:
        return ProjectSkillSettings.model_validate(data)
    except Exception:
        return ProjectSkillSettings()


def save_project_skill_settings(
    project_id: str,
    skill_settings: ProjectSkillSettings,
) -> ProjectSkillSettings:
    path = _settings_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skill_settings.model_dump_json(indent=2), encoding="utf-8")
    return skill_settings


def _parse_skill_md(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    name = str(meta.get("name") or path.parent.name).strip().lower()
    description = str(meta.get("description") or "").strip()
    if not name or not description:
        return None
    recommended: list[str] = []
    raw_meta = meta.get("metadata") or {}
    if isinstance(raw_meta, dict):
        raw_agents = raw_meta.get("recommended_agents") or raw_meta.get("agents") or ""
        if isinstance(raw_agents, str):
            recommended = [part.strip() for part in raw_agents.replace(",", " ").split() if part.strip()]
        elif isinstance(raw_agents, list):
            recommended = [str(part).strip() for part in raw_agents if str(part).strip()]
    body = match.group(2).strip()
    return {
        "name": name,
        "description": description,
        "recommended_agents": recommended,
        "body": body,
        "path": path.parent,
        "preview": body[:240] + ("…" if len(body) > 240 else ""),
    }


def _discover_in_dir(root: Path, source: str) -> list[dict]:
    if not root.is_dir():
        return []
    found: list[dict] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        parsed = _parse_skill_md(skill_md)
        if parsed is None:
            continue
        # Directory name is authoritative for path resolution.
        dir_name = child.name.strip().lower()
        if not is_valid_skill_name(dir_name):
            continue
        parsed["name"] = dir_name
        parsed["source"] = source
        found.append(parsed)
    return found


def list_available_skills(project_id: str | None = None) -> list[dict]:
    """Builtin catalog plus optional project custom skills (custom wins on name)."""
    by_name: dict[str, dict] = {}
    for item in _discover_in_dir(_builtin_skills_dir(), "builtin"):
        by_name[item["name"]] = item
    if project_id:
        for item in _discover_in_dir(_project_skills_dir(project_id), "custom"):
            by_name[item["name"]] = item
    return list(by_name.values())


def get_project_skills_response(project_id: str) -> ProjectSkillsResponse:
    selections = {item.name: item for item in load_project_skill_settings(project_id).skills}
    catalog: list[SkillCatalogItem] = []
    for skill in list_available_skills(project_id):
        assignment = selections.get(skill["name"])
        catalog.append(
            SkillCatalogItem(
                name=skill["name"],
                description=skill["description"],
                source=skill["source"],
                recommended_agents=skill.get("recommended_agents") or [],
                enabled=assignment.enabled if assignment else False,
                agents=assignment.agents if assignment else ["all"],
                body_preview=skill.get("preview"),
            )
        )
    return ProjectSkillsResponse(skills=catalog)


def update_project_skills(project_id: str, update: ProjectSkillSettings) -> ProjectSkillsResponse:
    available = {item["name"] for item in list_available_skills(project_id)}
    filtered = [item for item in update.skills if item.name in available]
    save_project_skill_settings(project_id, ProjectSkillSettings(skills=filtered))
    return get_project_skills_response(project_id)


def _write_skill_md(directory: Path, name: str, description: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    skill_md = directory / "SKILL.md"
    # Escape description if it contains special YAML chars by using a plain scalar.
    safe_description = description.replace("\n", " ").strip()
    content = (
        f"---\n"
        f"name: {name}\n"
        f"description: {json.dumps(safe_description)}\n"
        f"metadata:\n"
        f"  author: user\n"
        f"  version: \"1.0\"\n"
        f"---\n\n"
        f"{body.strip()}\n"
    )
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


def create_custom_skill(project_id: str, data: SkillCreate) -> ProjectSkillsResponse:
    name = data.name
    if not is_valid_skill_name(name):
        raise ValueError(
            "Skill name must be 1–64 chars of lowercase letters, digits, and hyphens "
            "(e.g. brand-voice)."
        )
    if len(data.body) > settings.max_skill_body_chars:
        raise ValueError(f"Skill body exceeds {settings.max_skill_body_chars} characters.")

    custom_dir = _project_skills_dir(project_id)
    existing_custom = _discover_in_dir(custom_dir, "custom")
    target = custom_dir / name
    if not target.exists() and len(existing_custom) >= settings.max_custom_skills_per_project:
        raise ValueError(
            f"Project custom skill limit is {settings.max_custom_skills_per_project}."
        )

    # Prevent overwriting a builtin name as custom (would shadow catalog).
    builtin_names = {item["name"] for item in _discover_in_dir(_builtin_skills_dir(), "builtin")}
    if name in builtin_names:
        raise ValueError(f"'{name}' is a built-in skill name. Choose a different name.")

    _write_skill_md(target, name, data.description, data.body)

    settings_model = load_project_skill_settings(project_id)
    others = [item for item in settings_model.skills if item.name != name]
    others.append(
        SkillAssignment(
            name=name,
            enabled=data.enabled,
            agents=data.agents,  # type: ignore[arg-type]
        )
    )
    save_project_skill_settings(project_id, ProjectSkillSettings(skills=others))
    return get_project_skills_response(project_id)


def delete_custom_skill(project_id: str, name: str) -> ProjectSkillsResponse:
    name = name.strip().lower().replace("_", "-")
    if not is_valid_skill_name(name):
        raise ValueError("Invalid skill name.")
    target = _project_skills_dir(project_id) / name
    if not target.is_dir():
        raise FileNotFoundError(f"Custom skill '{name}' not found.")
    skill_md = target / "SKILL.md"
    if skill_md.is_file():
        skill_md.unlink()
    # Remove empty skill directory (ignore non-empty leftovers).
    try:
        target.rmdir()
    except OSError:
        # Directory may still contain optional references/; remove tree carefully.
        import shutil

        shutil.rmtree(target, ignore_errors=True)

    settings_model = load_project_skill_settings(project_id)
    remaining = [item for item in settings_model.skills if item.name != name]
    save_project_skill_settings(project_id, ProjectSkillSettings(skills=remaining))
    return get_project_skills_response(project_id)


def _skill_applies(assignment: SkillAssignment, agent_key: str | None) -> bool:
    if not assignment.enabled:
        return False
    if agent_key is None:
        return True
    if "all" in assignment.agents:
        return True
    return agent_key in assignment.agents


def resolve_agent_skills(
    project_id: str,
    agent_key: str | None = None,
) -> list:
    """Return activated CrewAI Skill objects for Agent(skills=...).

    CrewAI's path loader only discovers skill *subdirectories* of a search root,
    so we load each selected package via load_skill_metadata + activate_skill.

    Returns an empty list when nothing is enabled (callers should pass None).
    """
    from crewai.skills.loader import activate_skill, load_skill_metadata

    available = {item["name"]: item for item in list_available_skills(project_id)}
    selections = load_project_skill_settings(project_id).skills
    loaded: list = []
    seen: set[str] = set()
    for assignment in selections:
        if not _skill_applies(assignment, agent_key):
            continue
        skill = available.get(assignment.name)
        if skill is None:
            continue
        path: Path = skill["path"]
        key = str(path.resolve())
        if key in seen:
            continue
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            meta = load_skill_metadata(path)
            loaded.append(activate_skill(meta))
            seen.add(key)
        except Exception:
            continue
    return loaded
