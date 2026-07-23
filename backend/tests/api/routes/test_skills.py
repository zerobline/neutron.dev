import pytest


@pytest.fixture(autouse=True)
def authenticated_client(client):
    client.post("/api/auth/register", json={"email": "skills@example.com", "password": "password123"})


def test_list_builtin_skills(client):
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    names = {item["name"] for item in data}
    assert "mvp-scope-discipline" in names
    assert all(item["source"] == "builtin" for item in data)
    assert all(item["enabled"] is False for item in data)


def test_get_project_skills_defaults(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    response = client.get(f"/api/projects/{project['id']}/skills")
    assert response.status_code == 200
    assert "skills" in response.json()
    assert all(not item["enabled"] for item in response.json()["skills"])


def test_put_project_skills(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    payload = {
        "skills": [
            {
                "name": "browser-native-spa",
                "enabled": True,
                "agents": ["engineer"],
            }
        ]
    }
    put_response = client.put(f"/api/projects/{project['id']}/skills", json=payload)
    get_response = client.get(f"/api/projects/{project['id']}/skills")

    assert put_response.status_code == 200
    enabled = [s for s in put_response.json()["skills"] if s["enabled"]]
    assert len(enabled) == 1
    assert enabled[0]["name"] == "browser-native-spa"
    assert enabled[0]["agents"] == ["engineer"]
    assert get_response.json() == put_response.json()


def test_create_and_delete_custom_skill_api(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    create = client.post(
        f"/api/projects/{project['id']}/skills",
        json={
            "name": "brand-voice",
            "description": "Friendly tone",
            "body": "Use short sentences.",
            "agents": ["product_manager"],
            "enabled": True,
        },
    )
    assert create.status_code == 200
    assert any(s["name"] == "brand-voice" and s["source"] == "custom" for s in create.json()["skills"])

    delete = client.delete(f"/api/projects/{project['id']}/skills/brand-voice")
    assert delete.status_code == 200
    assert all(s["name"] != "brand-voice" for s in delete.json()["skills"])


def test_create_custom_skill_validation_error(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/skills",
        json={
            "name": "mvp-scope-discipline",
            "description": "override",
            "body": "body",
        },
    )
    assert response.status_code == 400
    assert "built-in" in response.json()["detail"].lower()


def test_delete_custom_skill_not_found(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    response = client.delete(f"/api/projects/{project['id']}/skills/missing")
    assert response.status_code == 404


def test_project_skills_unknown_project(client):
    assert client.get("/api/projects/missing/skills").status_code == 404
    assert client.put("/api/projects/missing/skills", json={"skills": []}).status_code == 404
    assert client.post(
        "/api/projects/missing/skills",
        json={"name": "x", "description": "d", "body": "b"},
    ).status_code == 404
    assert client.delete("/api/projects/missing/skills/x").status_code == 404


def test_delete_invalid_skill_name(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    response = client.delete(f"/api/projects/{project['id']}/skills/Not Valid")
    assert response.status_code == 400
