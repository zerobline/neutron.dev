from app.config import settings

TRUNCATION_NOTICE = "\n[...truncated to limit prompt size...]"


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_NOTICE


def get_upload_context(project_id: str) -> str:
    upload_dir = settings.projects_dir / project_id / "uploads"
    if not upload_dir.exists():
        return ""

    per_file_limit = settings.max_upload_file_context_chars
    total_limit = settings.max_upload_context_chars
    parts: list[str] = []
    total = 0
    for f in sorted(upload_dir.iterdir()):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = f"[binary file: {f.name}, {f.stat().st_size} bytes]"
        text = _truncate(text, per_file_limit)
        if total_limit > 0 and total + len(text) > total_limit:
            parts.append(f"[additional uploaded files omitted to limit prompt size: {f.name}]")
            break
        total += len(text)
        parts.append(f"<uploaded_file name=\"{f.name}\">\n{text}\n</uploaded_file>")

    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)
