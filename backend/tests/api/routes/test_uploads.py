import io

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def authenticated_client(client):
    client.post("/api/auth/register", json={"email": "uploads@example.com", "password": "password123"})

from app.api.routes.uploads import resolve_upload_path


def test_upload_file(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "Upload", "description": "D"}).json()
    project_id = project["id"]

    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "hello.txt"
    assert data["size"] == 11
    assert data["type"] == "text/plain"
    assert data["path"] == "uploads/hello.txt"

    saved = settings_projects_dir / project_id / "uploads" / "hello.txt"
    assert saved.read_bytes() == b"hello world"


def test_upload_file_project_not_found(client):
    response = client.post(
        "/api/projects/nonexistent/uploads",
        files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert response.status_code == 404


def test_resolve_upload_path_rejects_escape(tmp_path):
    with pytest.raises(HTTPException) as exc_info:
        resolve_upload_path(tmp_path / "uploads", "../evil.txt")
    assert exc_info.value.status_code == 400


def test_upload_file_too_large(client, monkeypatch, settings_projects_dir):
    from app.api.routes import uploads

    project = client.post("/api/projects", json={"name": "Big", "description": "D"}).json()
    project_id = project["id"]

    monkeypatch.setattr(uploads, "MAX_FILE_SIZE", 3)
    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("big.txt", io.BytesIO(b"xxxx"), "text/plain")},
    )
    assert response.status_code == 413
    assert not (settings_projects_dir / project_id / "uploads" / "big.txt").exists()


def test_upload_file_rejects_duplicate_name(client):
    project = client.post("/api/projects", json={"name": "Duplicate", "description": "D"}).json()
    url = f"/api/projects/{project['id']}/uploads"
    assert client.post(url, files={"file": ("same.txt", io.BytesIO(b"one"), "text/plain")}).status_code == 200
    response = client.post(url, files={"file": ("same.txt", io.BytesIO(b"two"), "text/plain")})
    assert response.status_code == 409


def test_upload_file_enforces_project_file_count(client, monkeypatch):
    from app.api.routes import uploads

    project = client.post("/api/projects", json={"name": "Count", "description": "D"}).json()
    monkeypatch.setattr(uploads, "MAX_FILES_PER_PROJECT", 1)
    url = f"/api/projects/{project['id']}/uploads"
    assert client.post(url, files={"file": ("one.txt", io.BytesIO(b"1"), "text/plain")}).status_code == 200
    assert client.post(url, files={"file": ("two.txt", io.BytesIO(b"2"), "text/plain")}).status_code == 413


def test_upload_file_enforces_project_byte_limit(client, monkeypatch, settings_projects_dir):
    from app.api.routes import uploads

    project = client.post("/api/projects", json={"name": "Quota", "description": "D"}).json()
    monkeypatch.setattr(uploads, "MAX_PROJECT_SIZE", 3)
    response = client.post(
        f"/api/projects/{project['id']}/uploads",
        files={"file": ("quota.txt", io.BytesIO(b"four"), "text/plain")},
    )
    assert response.status_code == 413
    assert not (settings_projects_dir / project["id"] / "uploads" / "quota.txt").exists()


def test_upload_file_sanitizes_filename(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "Sanitize", "description": "D"}).json()
    project_id = project["id"]

    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("../../../evil file.txt", io.BytesIO(b"bad"), "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "evil_file.txt"
    assert "/" not in response.json()["name"]
    assert "\\" not in response.json()["name"]


def test_upload_file_disallows_binary_type(client):
    project = client.post("/api/projects", json={"name": "Binary", "description": "D"}).json()
    project_id = project["id"]

    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("test.bin", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_upload_file_no_content_type_with_safe_extension(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "NoCT", "description": "D"}).json()
    project_id = project["id"]

    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("test.txt", io.BytesIO(b"data"))},
    )
    assert response.status_code == 200


def test_list_uploads_empty(client):
    project = client.post("/api/projects", json={"name": "Empty", "description": "D"}).json()
    project_id = project["id"]

    response = client.get(f"/api/projects/{project_id}/uploads")
    assert response.status_code == 200
    assert response.json() == []


def test_list_uploads_with_files(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "Listed", "description": "D"}).json()
    project_id = project["id"]

    client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("a.txt", io.BytesIO(b"aaa"), "text/plain")},
    )
    client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("b.txt", io.BytesIO(b"bbb"), "text/plain")},
    )

    response = client.get(f"/api/projects/{project_id}/uploads")
    assert response.status_code == 200
    data = response.json()
    names = {f["name"] for f in data}
    assert names == {"a.txt", "b.txt"}


def test_list_uploads_skips_subdirectories(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "SubDir", "description": "D"}).json()
    project_id = project["id"]

    upload_dir = settings_projects_dir / project_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "file.txt").write_text("data")
    (upload_dir / "subdir").mkdir()

    response = client.get(f"/api/projects/{project_id}/uploads")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "file.txt"


def test_list_uploads_project_not_found(client):
    response = client.get("/api/projects/nonexistent/uploads")
    assert response.status_code == 404


def test_upload_file_empty_filename(client, settings_projects_dir):
    project = client.post("/api/projects", json={"name": "EmptyName", "description": "D"}).json()
    project_id = project["id"]

    response = client.post(
        f"/api/projects/{project_id}/uploads",
        files={"file": ("", io.BytesIO(b"data"), "text/plain")},
    )
    # Empty filename may be treated as no filename by FastAPI
    assert response.status_code in (200, 422)
