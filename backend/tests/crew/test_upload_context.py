from app.crew.uploads import get_upload_context


def test_get_upload_context_no_uploads_dir(settings_projects_dir):
    result = get_upload_context("nonexistent")
    assert result == ""


def test_get_upload_context_empty_dir(settings_projects_dir):
    upload_dir = settings_projects_dir / "proj1" / "uploads"
    upload_dir.mkdir(parents=True)
    result = get_upload_context("proj1")
    assert result == ""


def test_get_upload_context_text_files(settings_projects_dir):
    upload_dir = settings_projects_dir / "proj2" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "notes.txt").write_text("hello world", encoding="utf-8")
    (upload_dir / "spec.md").write_text("# Spec", encoding="utf-8")

    result = get_upload_context("proj2")
    assert '<uploaded_file name="notes.txt">' in result
    assert "hello world" in result
    assert '<uploaded_file name="spec.md">' in result
    assert "# Spec" in result


def test_get_upload_context_binary_file(settings_projects_dir):
    upload_dir = settings_projects_dir / "proj3" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "image.png").write_bytes(b"\x89PNG\x00\x01\xff")

    result = get_upload_context("proj3")
    assert "[binary file: image.png" in result


def test_get_upload_context_skips_subdirs(settings_projects_dir):
    upload_dir = settings_projects_dir / "proj4" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "subdir").mkdir()
    (upload_dir / "file.txt").write_text("data", encoding="utf-8")

    result = get_upload_context("proj4")
    assert "file.txt" in result
    assert "subdir" not in result


def test_get_upload_context_truncates_large_file(settings_projects_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_file_context_chars", 5)
    upload_dir = settings_projects_dir / "proj5" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "big.txt").write_text("0123456789", encoding="utf-8")

    result = get_upload_context("proj5")
    assert "01234" in result
    assert "0123456789" not in result
    assert "truncated" in result


def test_get_upload_context_no_truncation_when_limit_disabled(settings_projects_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_file_context_chars", 0)
    upload_dir = settings_projects_dir / "proj6" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "big.txt").write_text("0123456789", encoding="utf-8")

    result = get_upload_context("proj6")
    assert "0123456789" in result
    assert "truncated" not in result


def test_get_upload_context_total_cap_omits_overflow_files(settings_projects_dir, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_context_chars", 8)
    upload_dir = settings_projects_dir / "proj7" / "uploads"
    upload_dir.mkdir(parents=True)
    (upload_dir / "a.txt").write_text("12345678", encoding="utf-8")
    (upload_dir / "b.txt").write_text("overflow", encoding="utf-8")

    result = get_upload_context("proj7")
    assert "12345678" in result
    assert "overflow" not in result
    assert "additional uploaded files omitted" in result
    assert "b.txt" in result
