from app.services.template_service import TEMPLATES


def test_list_templates(client):
    response = client.get("/api/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(TEMPLATES)
    assert {t["id"] for t in data} == {t["id"] for t in TEMPLATES}


def test_get_template(client):
    response = client.get("/api/templates/saas")
    assert response.status_code == 200
    assert response.json()["id"] == "saas"
    assert "prompt" in response.json()


def test_get_template_not_found(client):
    response = client.get("/api/templates/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"
