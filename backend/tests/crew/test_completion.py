from app.crew.completion import (
    build_quality_checklist,
    follow_up_suggestions,
    has_seeded_demo_data,
)


def test_build_quality_checklist_missing_project(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.completion.settings.projects_dir", tmp_path)
    checklist = build_quality_checklist("missing-id", files=[])
    assert checklist["required_files"] is False
    assert checklist["entry_point"] is False
    assert checklist["seeded_demo_data"] is False
    assert any(item["id"] == "seeded_demo_data" for item in checklist["items"])


def test_has_seeded_demo_data_detects_arrays(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.completion.settings.projects_dir", tmp_path)
    proj = tmp_path / "p1"
    proj.mkdir()
    (proj / "app.js").write_text(
        "const alerts = [\n"
        "  { id: 1, name: 'A' },\n"
        "  { id: 2, name: 'B' },\n"
        "  { id: 3, name: 'C' },\n"
        "];\n",
        encoding="utf-8",
    )
    assert has_seeded_demo_data("p1") is True
    checklist = build_quality_checklist("p1", files=["index.html", "styles.css", "app.js"])
    assert checklist["seeded_demo_data"] is True
    assert checklist["required_files"] is True


def test_follow_up_suggestions_reorder_when_seeded():
    seeded = follow_up_suggestions(checklist={"seeded_demo_data": True}, mode="team")
    assert seeded[0]["id"] != "mock_data"
    assert len(seeded) == 4

    empty = follow_up_suggestions(checklist={"seeded_demo_data": False}, mode="team")
    assert empty[0]["id"] == "mock_data"

    iterate = follow_up_suggestions(checklist={"seeded_demo_data": True}, mode="iterate")
    assert iterate[0]["id"] in {"polish", "mobile", "dark_mode", "export"}
