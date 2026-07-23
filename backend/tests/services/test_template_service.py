from app.services import template_service


def test_get_templates_returns_all():
    templates = template_service.get_templates()
    assert isinstance(templates, list)
    assert len(templates) == 27
    assert all("id" in t and "name" in t and "stack" in t for t in templates)
    assert any(t["id"] == "kanban-board" for t in templates)
    assert any(t["id"] == "next-saas-dashboard" and t["stack"] == "nextjs" for t in templates)
    assert any(t["id"] == "next-marketing-site" and t["stack"] == "nextjs" for t in templates)


def test_get_template_found():
    template = template_service.get_template("saas")
    assert template is not None
    assert template["id"] == "saas"
    assert "prompt" in template


def test_get_kanban_board_template():
    template = template_service.get_template("kanban-board")
    assert template is not None
    assert template["name"] == "Kanban Board"
    assert template["category"] == "Productivity"
    assert template["icon"] == "columns-3"
    assert "drag-and-drop" in template["prompt"].lower() or "drag" in template["prompt"].lower()
    assert "localStorage" in template["prompt"] or "localstorage" in template["prompt"].lower()


def test_get_template_not_found():
    assert template_service.get_template("does-not-exist") is None


def test_nextjs_templates_have_stack():
    for template_id in ("next-saas-dashboard", "next-marketing-site"):
        template = template_service.get_template(template_id)
        assert template is not None
        assert template["stack"] == "nextjs"
        assert "Next.js" in template["prompt"] or "next" in template["prompt"].lower()
