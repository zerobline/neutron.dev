from app.crew.edit_history import (
    finalize_edit_snapshot,
    snapshot_before_edit,
    undo_last_edit,
)


def test_snapshot_diff_and_undo(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.edit_history.settings.projects_dir", tmp_path)
    project_id = "p-edit"
    root = tmp_path / project_id
    root.mkdir()
    (root / "index.html").write_text("<h1>A</h1>", encoding="utf-8")
    (root / "app.js").write_text("const x = 1;", encoding="utf-8")

    before = snapshot_before_edit(project_id, "make heading B")
    assert before["index.html"] == "<h1>A</h1>"

    (root / "index.html").write_text("<h1>B</h1>", encoding="utf-8")
    (root / "styles.css").write_text("body{}", encoding="utf-8")

    payload = finalize_edit_snapshot(project_id, ["index.html", "styles.css"])
    assert payload["can_undo"] is True
    assert "index.html" in payload["files_changed"]
    assert any(d["path"] == "index.html" for d in payload["diffs"])

    result = undo_last_edit(project_id)
    assert "index.html" in result["restored"]
    assert (root / "index.html").read_text(encoding="utf-8") == "<h1>A</h1>"
    # New file from the edit should be removed
    assert not (root / "styles.css").exists()
