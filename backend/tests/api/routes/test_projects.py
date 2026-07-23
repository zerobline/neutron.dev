from io import BytesIO
from zipfile import ZipFile

import pytest

from app.services import project_service


@pytest.fixture(autouse=True)
def authenticated_client(client):
    client.post("/api/auth/register", json={"email": "route@example.com", "password": "password123"})


def test_create_project(client):
    payload = {"name": "Test Project", "description": "A test project", "template": "saas"}
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["template"] == "saas"
    assert data["status"] == "created"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_without_template(client):
    payload = {"name": "No Template", "description": "No template"}
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 200
    assert response.json()["template"] is None


def test_list_projects(client):
    client.post("/api/projects", json={"name": "P1", "description": "D1"})
    client.post("/api/projects", json={"name": "P2", "description": "D2"})

    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {p["name"] for p in data}
    assert names == {"P1", "P2"}


def test_get_project(client):
    created = client.post("/api/projects", json={"name": "Get Me", "description": "D"}).json()
    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_project_not_found(client):
    response = client.get("/api/projects/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_delete_project(client, settings_projects_dir):
    created = client.post("/api/projects", json={"name": "Delete Me", "description": "D"}).json()
    project_dir = settings_projects_dir / created["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "dummy.txt").write_text("data")

    response = client.delete(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert not project_dir.exists()

    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 404


def test_delete_project_not_found(client):
    response = client.delete("/api/projects/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_get_project_files(client, settings_projects_dir):
    created = client.post("/api/projects", json={"name": "Files", "description": "D"}).json()
    project_dir = settings_projects_dir / created["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    subdir = project_dir / "src"
    subdir.mkdir()
    (subdir / "app.js").write_text("console.log('hi');", encoding="utf-8")

    response = client.get(f"/api/projects/{created['id']}/files")
    assert response.status_code == 200
    files = response.json()
    paths = {f["file_path"] for f in files}
    assert "index.html" in paths
    assert "src/app.js" in paths


def test_get_project_files_binary(client, settings_projects_dir):
    created = client.post("/api/projects", json={"name": "Binary", "description": "D"}).json()
    project_dir = settings_projects_dir / created["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "image.bin").write_bytes(b"\x00\x01\x02\xff")

    response = client.get(f"/api/projects/{created['id']}/files")
    files = {f["file_path"]: f["content"] for f in response.json()}
    assert files["image.bin"] == "[binary file]"


def test_get_project_files_project_not_found(client):
    response = client.get("/api/projects/nonexistent/files")
    assert response.status_code == 404


def test_download_project_zip(client, settings_projects_dir):
    created = client.post("/api/projects", json={"name": "Download", "description": "D"}).json()
    project_dir = settings_projects_dir / created["id"]
    (project_dir / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    nested = project_dir / "src"
    nested.mkdir()
    (nested / "app.js").write_text("console.log('hi');", encoding="utf-8")

    response = client.get(f"/api/projects/{created['id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == f'attachment; filename="{created["id"]}.zip"'
    with ZipFile(BytesIO(response.content)) as zf:
        assert set(zf.namelist()) == {"index.html", "src/app.js"}
        assert zf.read("index.html") == b"<h1>Hello</h1>"


def test_download_project_empty_zip(client):
    created = client.post("/api/projects", json={"name": "Empty Download", "description": "D"}).json()
    response = client.get(f"/api/projects/{created['id']}/download")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as zf:
        assert zf.namelist() == []


def test_download_project_not_found(client):
    response = client.get("/api/projects/nonexistent/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_get_project_messages(client):
    created = client.post("/api/projects", json={"name": "Messages", "description": "D"}).json()
    project_service.save_message(created["id"], "user", "hello")
    project_service.save_message(created["id"], "agent", "hi", agent="researcher")

    response = client.get(f"/api/projects/{created['id']}/messages")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["agent"] == "researcher"


def test_get_project_messages_not_found(client):
    response = client.get("/api/projects/nonexistent/messages")
    assert response.status_code == 404


def test_get_project_checkpoints_empty(client):
    created = client.post("/api/projects", json={"name": "Checkpoints", "description": "D"}).json()
    response = client.get(f"/api/projects/{created['id']}/checkpoints")
    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoints"] == []
    assert payload["latest"] is None


def test_get_project_checkpoints_not_found(client):
    response = client.get("/api/projects/nonexistent/checkpoints")
    assert response.status_code == 404


def test_create_project_with_nextjs_stack(client):
    response = client.post(
        "/api/projects",
        json={"name": "Next App", "description": "App Router", "stack": "nextjs"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stack"] == "nextjs"


def test_create_project_inherits_template_stack(client):
    response = client.post(
        "/api/projects",
        json={
            "name": "From Template",
            "description": "Next template",
            "template": "next-saas-dashboard",
        },
    )
    assert response.status_code == 200
    assert response.json()["stack"] == "nextjs"


def test_runtime_status_idle(client):
    created = client.post(
        "/api/projects",
        json={"name": "Runtime", "description": "D", "stack": "nextjs"},
    ).json()
    response = client.get(f"/api/projects/{created['id']}/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["project_id"] == created["id"]


def test_runtime_start_rejects_static_stack(client):
    created = client.post(
        "/api/projects",
        json={"name": "Static", "description": "D", "stack": "static"},
    ).json()
    response = client.post(f"/api/projects/{created['id']}/runtime/start")
    assert response.status_code == 400
    assert "Next.js" in response.json()["detail"]


def test_runtime_start_requires_package_json(client, settings_projects_dir):
    created = client.post(
        "/api/projects",
        json={"name": "Next Missing Pkg", "description": "D", "stack": "nextjs"},
    ).json()
    project_dir = settings_projects_dir / created["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    response = client.post(f"/api/projects/{created['id']}/runtime/start")
    assert response.status_code == 400
    assert "package.json" in response.json()["detail"]


def test_runtime_start_and_stop(client, settings_projects_dir, monkeypatch):
    created = client.post(
        "/api/projects",
        json={"name": "Next Runtime", "description": "D", "stack": "nextjs"},
    ).json()
    project_dir = settings_projects_dir / created["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

    from app.services.project_runtime import runtime_manager

    def fake_start(project_id: str):
        return {
            "project_id": project_id,
            "status": "installing",
            "port": 3123,
            "url": "http://127.0.0.1:3123",
            "message": "Installing npm dependencies…",
            "logs": [],
            "updated_at": 1.0,
        }

    def fake_stop(project_id: str):
        return {
            "project_id": project_id,
            "status": "stopped",
            "port": None,
            "url": None,
            "message": "Preview stopped.",
            "logs": [],
            "updated_at": 2.0,
        }

    monkeypatch.setattr(runtime_manager, "start", fake_start)
    monkeypatch.setattr(runtime_manager, "stop", fake_stop)

    start = client.post(f"/api/projects/{created['id']}/runtime/start")
    assert start.status_code == 200
    assert start.json()["status"] == "installing"
    assert start.json()["port"] == 3123

    stop = client.post(f"/api/projects/{created['id']}/runtime/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"


def test_runtime_not_found(client):
    assert client.get("/api/projects/missing/runtime").status_code == 404
    assert client.post("/api/projects/missing/runtime/start").status_code == 404
    assert client.post("/api/projects/missing/runtime/stop").status_code == 404
