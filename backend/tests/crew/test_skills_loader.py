import json
from pathlib import Path

import pytest

from app.config import settings
from app.crew.skills_loader import (
    create_custom_skill,
    delete_custom_skill,
    get_project_skills_response,
    is_valid_skill_name,
    list_available_skills,
    load_project_skill_settings,
    resolve_agent_skills,
    save_project_skill_settings,
    update_project_skills,
)
from app.models import ProjectSkillSettings, SkillAssignment, SkillCreate


def test_is_valid_skill_name():
    assert is_valid_skill_name("mvp-scope-discipline")
    assert is_valid_skill_name("a")
    assert not is_valid_skill_name("")
    assert not is_valid_skill_name("Bad_Name")
    assert not is_valid_skill_name("-leading")
    assert not is_valid_skill_name("trailing-")
    assert not is_valid_skill_name("has space")


def test_list_available_skills_includes_builtins():
    skills = list_available_skills()
    names = {s["name"] for s in skills}
    assert "mvp-scope-discipline" in names
    assert "browser-native-spa" in names
    assert all(s["source"] == "builtin" for s in skills)


def test_load_project_skill_settings_missing(settings_projects_dir):
    assert load_project_skill_settings("missing").skills == []


def test_save_and_load_project_skill_settings_roundtrip(settings_projects_dir):
    saved = save_project_skill_settings(
        "p1",
        ProjectSkillSettings(
            skills=[
                SkillAssignment(name="mvp-scope-discipline", enabled=True, agents=["team_leader"]),
            ]
        ),
    )
    loaded = load_project_skill_settings("p1")
    assert loaded.skills[0].name == saved.skills[0].name
    assert loaded.skills[0].enabled is True
    assert loaded.skills[0].agents == ["team_leader"]


def test_load_project_skill_settings_ignores_invalid_json(settings_projects_dir):
    project_dir = settings_projects_dir / "p1"
    project_dir.mkdir(parents=True)
    (project_dir / "skills.json").write_text("not-json", encoding="utf-8")
    assert load_project_skill_settings("p1").skills == []


def test_load_project_skill_settings_ignores_invalid_schema(settings_projects_dir):
    project_dir = settings_projects_dir / "p1"
    project_dir.mkdir(parents=True)
    (project_dir / "skills.json").write_text(
        json.dumps({"skills": [{"name": "", "enabled": True}]}),
        encoding="utf-8",
    )
    assert load_project_skill_settings("p1").skills == []


def test_get_project_skills_response_defaults_disabled(settings_projects_dir):
    response = get_project_skills_response("p1")
    assert len(response.skills) >= 6
    assert all(not item.enabled for item in response.skills)


def test_update_project_skills_filters_unknown(settings_projects_dir):
    response = update_project_skills(
        "p1",
        ProjectSkillSettings(
            skills=[
                SkillAssignment(name="mvp-scope-discipline", enabled=True, agents=["all"]),
                SkillAssignment(name="does-not-exist", enabled=True, agents=["all"]),
            ]
        ),
    )
    enabled = [s for s in response.skills if s.enabled]
    assert len(enabled) == 1
    assert enabled[0].name == "mvp-scope-discipline"


def test_resolve_agent_skills_filters_by_agent(settings_projects_dir):
    save_project_skill_settings(
        "p1",
        ProjectSkillSettings(
            skills=[
                SkillAssignment(name="mvp-scope-discipline", enabled=True, agents=["team_leader"]),
                SkillAssignment(name="browser-native-spa", enabled=True, agents=["engineer"]),
                SkillAssignment(name="accessibility-wcag", enabled=True, agents=["all"]),
                SkillAssignment(name="architecture-simplicity", enabled=False, agents=["architect"]),
            ]
        ),
    )
    leader_skills = resolve_agent_skills("p1", agent_key="team_leader")
    engineer_skills = resolve_agent_skills("p1", agent_key="engineer")
    leader_names = {s.name for s in leader_skills}
    engineer_names = {s.name for s in engineer_skills}
    assert "mvp-scope-discipline" in leader_names
    assert "accessibility-wcag" in leader_names
    assert "browser-native-spa" not in leader_names
    assert "browser-native-spa" in engineer_names
    assert "architecture-simplicity" not in engineer_names
    pm_names = {s.name for s in resolve_agent_skills("p1", agent_key="product_manager")}
    assert pm_names == {"accessibility-wcag"}
    assert all(s.instructions for s in leader_skills)


def test_create_and_delete_custom_skill(settings_projects_dir):
    created = create_custom_skill(
        "p1",
        SkillCreate(
            name="Brand_Voice",
            description="Write in a friendly brand voice.",
            body="Use short sentences and avoid jargon.",
            agents=["product_manager"],
            enabled=True,
        ),
    )
    names = {s.name for s in created.skills}
    assert "brand-voice" in names
    custom = next(s for s in created.skills if s.name == "brand-voice")
    assert custom.source == "custom"
    assert custom.enabled is True
    assert custom.agents == ["product_manager"]

    resolved = resolve_agent_skills("p1", agent_key="product_manager")
    assert {s.name for s in resolved} == {"brand-voice"}
    assert resolved[0].instructions

    deleted = delete_custom_skill("p1", "brand-voice")
    assert "brand-voice" not in {s.name for s in deleted.skills}
    assert resolve_agent_skills("p1", agent_key="product_manager") == []


def test_create_custom_skill_rejects_invalid_name(settings_projects_dir):
    with pytest.raises(ValueError, match="Skill name"):
        create_custom_skill(
            "p1",
            SkillCreate(name="!!", description="d", body="body"),
        )


def test_create_custom_skill_rejects_builtin_name(settings_projects_dir):
    with pytest.raises(ValueError, match="built-in"):
        create_custom_skill(
            "p1",
            SkillCreate(
                name="mvp-scope-discipline",
                description="override",
                body="body",
            ),
        )


def test_create_custom_skill_rejects_oversized_body(settings_projects_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_skill_body_chars", 10)
    with pytest.raises(ValueError, match="exceeds"):
        create_custom_skill(
            "p1",
            SkillCreate(name="too-long", description="d", body="x" * 20),
        )


def test_create_custom_skill_respects_max_count(settings_projects_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_custom_skills_per_project", 1)
    create_custom_skill(
        "p1",
        SkillCreate(name="one", description="d", body="body one"),
    )
    with pytest.raises(ValueError, match="limit"):
        create_custom_skill(
            "p1",
            SkillCreate(name="two", description="d", body="body two"),
        )


def test_delete_custom_skill_not_found(settings_projects_dir):
    with pytest.raises(FileNotFoundError):
        delete_custom_skill("p1", "missing-skill")


def test_delete_custom_skill_invalid_name(settings_projects_dir):
    with pytest.raises(ValueError, match="Invalid"):
        delete_custom_skill("p1", "Bad Name")


def test_parse_skips_invalid_skill_directories(settings_projects_dir, monkeypatch):
    root = settings_projects_dir / "catalog"
    root.mkdir()
    # No SKILL.md
    (root / "empty").mkdir()
    # Invalid frontmatter
    bad = root / "bad-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("not a skill", encoding="utf-8")
    # Invalid yaml
    bad_yaml = root / "bad-yaml"
    bad_yaml.mkdir()
    (bad_yaml / "SKILL.md").write_text("---\n: :\n---\nbody\n", encoding="utf-8")
    # Missing description
    no_desc = root / "no-desc"
    no_desc.mkdir()
    (no_desc / "SKILL.md").write_text("---\nname: no-desc\n---\nbody\n", encoding="utf-8")
    # Invalid directory name with skill md
    invalid_name = root / "Invalid_Name"
    invalid_name.mkdir()
    (invalid_name / "SKILL.md").write_text(
        "---\nname: invalid-name\ndescription: x\n---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "skills_dir", root)
    assert list_available_skills() == []


def test_custom_skill_shadows_same_name_only_when_not_builtin(settings_projects_dir):
    # Custom skills can exist alongside builtins with different names
    create_custom_skill(
        "p1",
        SkillCreate(name="house-style", description="Style guide", body="Be concise."),
    )
    available = list_available_skills("p1")
    custom = next(s for s in available if s["name"] == "house-style")
    assert custom["source"] == "custom"


def test_parse_skill_md_handles_read_errors_and_metadata_list(settings_projects_dir, monkeypatch):
    root = settings_projects_dir / "catalog2"
    root.mkdir()
    skill = root / "list-agents"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: list-agents\ndescription: Uses list agents\n"
        "metadata:\n  recommended_agents:\n    - engineer\n    - architect\n---\nBody here.\n",
        encoding="utf-8",
    )
    unreadable = root / "unreadable"
    unreadable.mkdir()
    md = unreadable / "SKILL.md"
    md.write_text(
        "---\nname: unreadable\ndescription: x\n---\nbody\n",
        encoding="utf-8",
    )
    not_dict_meta = root / "meta-not-dict"
    not_dict_meta.mkdir()
    (not_dict_meta / "SKILL.md").write_text(
        "---\n- just\n- a\n- list\n---\nbody\n",
        encoding="utf-8",
    )
    # metadata present but not a dict → skip recommended_agents parsing
    meta_scalar = root / "meta-scalar"
    meta_scalar.mkdir()
    (meta_scalar / "SKILL.md").write_text(
        "---\nname: meta-scalar\ndescription: scalar metadata\nmetadata: not-a-map\n---\nBody\n",
        encoding="utf-8",
    )
    # recommended_agents neither string nor list
    agents_int = root / "agents-int"
    agents_int.mkdir()
    (agents_int / "SKILL.md").write_text(
        "---\nname: agents-int\ndescription: odd agents type\nmetadata:\n  recommended_agents: 3\n---\nBody\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "skills_dir", root)
    names = {s["name"] for s in list_available_skills()}
    assert "list-agents" in names
    item = next(s for s in list_available_skills() if s["name"] == "list-agents")
    assert item["recommended_agents"] == ["engineer", "architect"]
    assert "meta-not-dict" not in names
    scalar = next(s for s in list_available_skills() if s["name"] == "meta-scalar")
    assert scalar["recommended_agents"] == []
    agents_item = next(s for s in list_available_skills() if s["name"] == "agents-int")
    assert agents_item["recommended_agents"] == []

    # Force read failure on one file after discovery would open it
    original_read = Path.read_text

    def flaky_read(self, *args, **kwargs):
        if self.name == "SKILL.md" and self.parent.name == "unreadable":
            raise OSError("locked")
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read)
    names_after = {s["name"] for s in list_available_skills()}
    assert "unreadable" not in names_after
    assert "list-agents" in names_after


def test_resolve_agent_skills_skips_missing_and_failed_loads(settings_projects_dir, monkeypatch):
    save_project_skill_settings(
        "p1",
        ProjectSkillSettings(
            skills=[
                SkillAssignment(name="mvp-scope-discipline", enabled=True, agents=["all"]),
                SkillAssignment(name="ghost-skill", enabled=True, agents=["all"]),
            ]
        ),
    )
    # agent_key None includes all enabled
    all_skills = resolve_agent_skills("p1", agent_key=None)
    assert {s.name for s in all_skills} == {"mvp-scope-discipline"}

    # Break load_skill_metadata for coverage of exception path
    from crewai.skills import loader as skill_loader

    def boom(_path):
        raise RuntimeError("parse fail")

    monkeypatch.setattr(skill_loader, "load_skill_metadata", boom)
    assert resolve_agent_skills("p1", agent_key="engineer") == []


def test_resolve_agent_skills_skips_duplicate_paths_and_missing_md(settings_projects_dir, monkeypatch):
    skill_path = settings.skills_dir / "mvp-scope-discipline"
    monkeypatch.setattr(
        "app.crew.skills_loader.list_available_skills",
        lambda project_id=None: [
            {
                "name": "mvp-scope-discipline",
                "path": skill_path,
                "description": "d",
                "source": "builtin",
            },
            {
                "name": "alias-skill",
                "path": skill_path,
                "description": "d",
                "source": "custom",
            },
            {
                "name": "missing-md",
                "path": settings_projects_dir / "no-skill-md",
                "description": "d",
                "source": "custom",
            },
        ],
    )
    (settings_projects_dir / "no-skill-md").mkdir(parents=True)
    save_project_skill_settings(
        "p1",
        ProjectSkillSettings(
            skills=[
                SkillAssignment(name="mvp-scope-discipline", enabled=True, agents=["all"]),
                SkillAssignment(name="alias-skill", enabled=True, agents=["all"]),
                SkillAssignment(name="missing-md", enabled=True, agents=["all"]),
            ]
        ),
    )
    resolved = resolve_agent_skills("p1", agent_key="engineer")
    assert len(resolved) == 1
    assert resolved[0].name == "mvp-scope-discipline"


def test_delete_custom_skill_removes_nonempty_directory(settings_projects_dir):
    create_custom_skill(
        "p1",
        SkillCreate(name="with-refs", description="Has extras", body="Body."),
    )
    skill_dir = settings_projects_dir / "p1" / "skills" / "with-refs"
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "notes.md").write_text("note", encoding="utf-8")
    delete_custom_skill("p1", "with-refs")
    assert not skill_dir.exists()


def test_delete_custom_skill_without_skill_md(settings_projects_dir):
    skill_dir = settings_projects_dir / "p1" / "skills" / "empty-pack"
    skill_dir.mkdir(parents=True)
    # No SKILL.md — still remove the directory via rmdir path
    from app.crew.skills_loader import delete_custom_skill as delete_fn

    # Manually register selection so delete doesn't need discovery
    save_project_skill_settings(
        "p1",
        ProjectSkillSettings(skills=[SkillAssignment(name="empty-pack", enabled=True)]),
    )
    # Force path exists as directory without SKILL.md
    result = delete_fn("p1", "empty-pack")
    assert "empty-pack" not in {s.name for s in result.skills}
    assert not skill_dir.exists()


def test_discover_skips_files_in_skills_root(settings_projects_dir, monkeypatch):
    root = settings_projects_dir / "with-file"
    root.mkdir()
    (root / "readme.txt").write_text("not a skill", encoding="utf-8")
    good = root / "ok-skill"
    good.mkdir()
    (good / "SKILL.md").write_text(
        "---\nname: ok-skill\ndescription: valid\n---\nBody\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "skills_dir", root)
    names = {s["name"] for s in list_available_skills()}
    assert names == {"ok-skill"}
