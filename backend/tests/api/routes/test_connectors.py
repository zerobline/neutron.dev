import pytest


@pytest.fixture(autouse=True)
def authenticated_client(client):
    client.post("/api/auth/register", json={"email": "connectors@example.com", "password": "password123"})


def test_get_project_connectors_defaults_empty(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()

    response = client.get(f"/api/projects/{project['id']}/connectors")

    assert response.status_code == 200
    assert response.json() == {
        "default_mcps": [
            {"key": "github", "enabled": True},
            {"key": "linear", "enabled": True},
        ],
        "custom_mcp_servers": [],
    }


def test_put_and_get_project_connectors(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    payload = {
        "custom_mcp_servers": [
            {
                "id": "remote",
                "name": " Remote MCP ",
                "transport": "http",
                "command_or_url": " https://example.com/mcp ",
                "notes": " notes ",
            }
        ]
    }

    put_response = client.put(f"/api/projects/{project['id']}/connectors", json=payload)
    get_response = client.get(f"/api/projects/{project['id']}/connectors")

    assert put_response.status_code == 200
    assert put_response.json()["custom_mcp_servers"][0] == {
        "id": "remote",
        "name": "Remote MCP",
        "transport": "http",
        "command_or_url": "https://example.com/mcp",
        "notes": "notes",
    }
    assert get_response.json() == put_response.json()


def test_project_connectors_accepts_frontend_command_or_url_alias(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    payload = {
        "custom_mcp_servers": [
            {
                "id": "stdio",
                "name": "Filesystem",
                "transport": "stdio",
                "commandOrUrl": "npx server",
                "notes": "local",
            }
        ]
    }

    response = client.put(f"/api/projects/{project['id']}/connectors", json=payload)

    assert response.status_code == 200
    assert response.json()["custom_mcp_servers"][0]["command_or_url"] == "npx server"


def test_project_connectors_unknown_project(client):
    assert client.get("/api/projects/missing/connectors").status_code == 404
    assert client.put("/api/projects/missing/connectors", json={"custom_mcp_servers": []}).status_code == 404


def test_project_connectors_rejects_invalid_remote_url(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    payload = {
        "custom_mcp_servers": [
            {
                "id": "bad",
                "name": "Bad",
                "transport": "sse",
                "command_or_url": "example.com/mcp",
                "notes": "",
            }
        ]
    }

    response = client.put(f"/api/projects/{project['id']}/connectors", json=payload)

    assert response.status_code == 422


def test_project_connectors_rejects_invalid_transport(client):
    project = client.post("/api/projects", json={"name": "P", "description": "D"}).json()
    payload = {
        "custom_mcp_servers": [
            {
                "id": "bad",
                "name": "Bad",
                "transport": "ftp",
                "command_or_url": "ftp://example.com",
                "notes": "",
            }
        ]
    }

    response = client.put(f"/api/projects/{project['id']}/connectors", json=payload)

    assert response.status_code == 422
