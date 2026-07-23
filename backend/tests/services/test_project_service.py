import uuid
from zipfile import ZipFile

from app.models import ProjectCreate, UserCreate
from app.services import auth_service, project_service


def test_create_project(temp_db, settings_projects_dir):
    data = ProjectCreate(name="Svc", description="Service test", template="portfolio")
    project = project_service.create_project(data)
    assert uuid.UUID(project.id)
    assert project.name == "Svc"
    assert project.description == "Service test"
    assert project.template == "portfolio"
    assert (settings_projects_dir / project.id).is_dir()


def test_get_project_returns_project(temp_db):
    created = project_service.create_project(ProjectCreate(name="A", description="B"))
    fetched = project_service.get_project(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_project_not_found(temp_db):
    assert project_service.get_project("missing") is None


def test_list_projects_returns_all(temp_db):
    project_service.create_project(ProjectCreate(name="First", description="1"))
    project_service.create_project(ProjectCreate(name="Second", description="2"))
    projects = project_service.list_projects()
    assert len(projects) == 2
    assert {p.name for p in projects} == {"First", "Second"}


def test_owner_scoped_project_operations(temp_db):
    first_user = auth_service.create_user(UserCreate(email="first@example.com", password="password123"))
    second_user = auth_service.create_user(UserCreate(email="second@example.com", password="password123"))
    first = project_service.create_project(ProjectCreate(name="First", description="1"), owner_user_id=first_user.id)
    second = project_service.create_project(ProjectCreate(name="Second", description="2"), owner_user_id=second_user.id)

    assert [project.id for project in project_service.list_projects(first_user.id)] == [first.id]
    assert project_service.get_project(first.id, first_user.id) is not None
    assert project_service.get_project(second.id, first_user.id) is None
    assert project_service.get_project_owner_user_id(first.id) == first_user.id
    assert project_service.get_project_owner_user_id("missing") is None
    assert project_service.delete_project(second.id, first_user.id) is False
    assert project_service.delete_project(first.id, first_user.id) is True


def test_delete_project_removes_dir(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Del", description="D"))
    project_dir = settings_projects_dir / created.id
    (project_dir / "file.txt").write_text("x")

    result = project_service.delete_project(created.id)
    assert result is True
    assert not project_dir.exists()
    assert project_service.get_project(created.id) is None


def test_delete_project_without_dir(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Del2", description="D"))
    project_dir = settings_projects_dir / created.id
    if project_dir.exists():
        import shutil
        shutil.rmtree(project_dir)

    result = project_service.delete_project(created.id)
    assert result is True
    assert project_service.get_project(created.id) is None


def test_delete_project_wrong_owner_preserves_dir(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Del", description="D"), owner_user_id=None)
    project_dir = settings_projects_dir / created.id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "file.txt").write_text("x")

    result = project_service.delete_project(created.id, owner_user_id="user-b")
    assert result is False
    assert project_dir.exists()
    assert project_service.get_project(created.id) is not None


def test_delete_project_not_found(temp_db):
    assert project_service.delete_project("missing") is False


def test_update_project_status(temp_db):
    created = project_service.create_project(ProjectCreate(name="Status", description="S"))
    project_service.update_project_status(created.id, "complete")
    updated = project_service.get_project(created.id)
    assert updated.status == "complete"


def test_update_project_token_usage_persists_nested_summary(temp_db):
    created = project_service.create_project(ProjectCreate(name="Usage", description="Track it"))

    project_service.update_project_token_usage(
        created.id,
        total_tokens=250,
        prompt_tokens=175,
        completion_tokens=75,
        successful_requests=3,
        token_budget=1000,
    )

    updated = project_service.get_project(created.id)
    assert updated.token_usage.total_tokens == 250
    assert updated.token_usage.prompt_tokens == 175
    assert updated.token_usage.completion_tokens == 75
    assert updated.token_usage.successful_requests == 3
    assert updated.token_budget == 1000
    assert updated.token_budget_percent == 25.0


def test_update_project_token_usage_clamps_negative_values_and_ignores_missing(temp_db):
    created = project_service.create_project(ProjectCreate(name="Usage", description="Track it"))

    project_service.update_project_token_usage(
        created.id,
        total_tokens=-1,
        prompt_tokens=-2,
        completion_tokens=-3,
        successful_requests=-4,
        token_budget=-5,
    )
    project_service.update_project_token_usage(
        "missing",
        total_tokens=1,
        prompt_tokens=1,
        completion_tokens=1,
        successful_requests=1,
        token_budget=1,
    )

    updated = project_service.get_project(created.id)
    assert updated.token_usage.total_tokens == 0
    assert updated.token_budget == 0
    assert updated.token_budget_percent is None


def test_get_project_status(temp_db):
    created = project_service.create_project(ProjectCreate(name="Status", description="S"))
    assert project_service.get_project_status(created.id) == "created"
    project_service.update_project_status(created.id, "building")
    assert project_service.get_project_status(created.id) == "building"


def test_get_project_status_missing(temp_db):
    assert project_service.get_project_status("nonexistent") is None


def test_get_project_files_text(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Files", description="F"))
    project_dir = settings_projects_dir / created.id
    (project_dir / "index.html").write_text("<h1>Hi</h1>")
    files = project_service.get_project_files(created.id)
    assert len(files) == 1
    assert files[0]["file_path"] == "index.html"
    assert files[0]["content"] == "<h1>Hi</h1>"


def test_get_project_files_binary(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Binary", description="B"))
    project_dir = settings_projects_dir / created.id
    (project_dir / "img.bin").write_bytes(b"\x00\xff")
    files = project_service.get_project_files(created.id)
    assert files[0]["content"] == "[binary file]"


def test_get_project_files_hides_internal_metadata(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="HideMeta", description="H"))
    project_dir = settings_projects_dir / created.id
    (project_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (project_dir / "connectors.json").write_text("{}", encoding="utf-8")
    neutron = project_dir / ".neutron"
    neutron.mkdir()
    (neutron / "last_edit.json").write_text("{}", encoding="utf-8")

    files = project_service.get_project_files(created.id)
    paths = {f["file_path"] for f in files}
    assert paths == {"index.html"}
    assert "connectors.json" not in paths
    assert not any(p.startswith(".neutron/") for p in paths)


def test_get_project_files_too_large(temp_db, settings_projects_dir, monkeypatch):
    created = project_service.create_project(ProjectCreate(name="Large", description="L"))
    project_dir = settings_projects_dir / created.id
    big_file = project_dir / "large.txt"
    big_file.write_text("too big")

    monkeypatch.setattr(project_service, "MAX_INLINE_FILE_SIZE", 1)

    files = project_service.get_project_files(created.id)
    assert files[0]["content"] == "[file too large to display]"


def test_get_project_files_missing_dir(temp_db):
    created = project_service.create_project(ProjectCreate(name="NoDir", description="ND"))
    # Directory exists because create_project made it; remove it manually
    from app.config import settings

    (settings.projects_dir / created.id).rmdir()
    files = project_service.get_project_files(created.id)
    assert files == []


def test_save_and_get_messages(temp_db):
    created = project_service.create_project(ProjectCreate(name="Msg", description="M"))
    project_service.save_message(created.id, "user", "hi")
    project_service.save_message(created.id, "agent", "hello", agent="pm")
    project_service.save_message(
        created.id,
        "agent",
        "A focused portfolio plan.",
        agent="product_manager",
        kind="phase_result",
        metadata={
            "phase": "planning",
            "kind": "plan",
            "headline": "Portfolio plan",
            "summary": "A focused portfolio plan.",
            "spec": {"mvp_features": ["Hero"]},
            "has_structured_spec": True,
        },
    )
    messages = project_service.get_messages(created.id)
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["agent"] == "pm"
    assert messages[1].get("kind") is None
    assert messages[2]["kind"] == "phase_result"
    assert messages[2]["metadata"]["headline"] == "Portfolio plan"
    assert messages[2]["metadata"]["spec"]["mvp_features"] == ["Hero"]


def test_get_messages_empty(temp_db):
    created = project_service.create_project(ProjectCreate(name="Empty", description="E"))
    assert project_service.get_messages(created.id) == []


def test_build_project_zip_includes_nested_text_and_binary_files(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="Zip", description="Z"))
    project_dir = settings_projects_dir / created.id
    (project_dir / "index.html").write_text("<h1>Hi</h1>", encoding="utf-8")
    nested = project_dir / "assets"
    nested.mkdir()
    (nested / "image.bin").write_bytes(b"\x00\xff")

    archive = project_service.build_project_zip(created.id)

    with ZipFile(archive) as zf:
        assert set(zf.namelist()) == {"index.html", "assets/image.bin"}
        assert zf.read("index.html") == b"<h1>Hi</h1>"
        assert zf.read("assets/image.bin") == b"\x00\xff"


def test_build_project_zip_for_project_without_files(temp_db):
    created = project_service.create_project(ProjectCreate(name="EmptyZip", description="Z"))
    archive = project_service.build_project_zip(created.id)

    with ZipFile(archive) as zf:
        assert zf.namelist() == []


def test_build_project_zip_for_missing_directory(temp_db, settings_projects_dir):
    created = project_service.create_project(ProjectCreate(name="MissingZip", description="Z"))
    (settings_projects_dir / created.id).rmdir()
    archive = project_service.build_project_zip(created.id)

    with ZipFile(archive) as zf:
        assert zf.namelist() == []
