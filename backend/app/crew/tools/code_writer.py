from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings
from app.crew.tool_input_repair import (
    _normalize_rel_path,
    _strip_react_leak,
    coerce_tool_arguments,
)


class CodeWriterInput(BaseModel):
    file_path: str = Field(description="Relative file path within the project (e.g., 'src/App.tsx', 'index.html')")
    content: str = Field(description="The complete file content to write")


class CodeWriterTool(BaseTool):
    name: str = "write_code_file"
    description: str = (
        "Write code content to a file in the project directory. "
        "Use this to create HTML, CSS, JavaScript, TypeScript, React components, and any other code files. "
        "The file_path should be relative to the project root. "
        "Action Input MUST be a single JSON object: "
        '{"file_path": "relative/path.ext", "content": "full file contents"} '
        "(not an array)."
    )
    args_schema: Type[BaseModel] = CodeWriterInput
    project_id: str = ""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        # Accept flexible call shapes from CrewAI / repaired tool args.
        file_path: str | None = None
        content: str | None = None

        if len(args) >= 2 and isinstance(args[0], str):
            file_path = args[0]
            content = args[1] if isinstance(args[1], str) else str(args[1])
        elif len(args) == 1 and isinstance(args[0], dict):
            coerced = coerce_tool_arguments(args[0], tool_name=self.name) or {}
            file_path = coerced.get("file_path")
            content = coerced.get("content")
        elif kwargs:
            coerced = coerce_tool_arguments(kwargs, tool_name=self.name) or kwargs
            file_path = coerced.get("file_path") or coerced.get("path")
            content = coerced.get("content")

        if not file_path:
            return (
                "Error: write_code_file requires file_path and content as a single JSON object, "
                'e.g. {"file_path": "app/page.tsx", "content": "..."}'
            )
        if content is None:
            return f"Error: missing content for file_path '{file_path}'"

        file_path = _normalize_rel_path(str(file_path))
        content = _strip_react_leak(str(content))
        if not content.strip():
            return f"Error: empty content for file_path '{file_path}'"

        project_dir = settings.projects_dir / self.project_id
        full_path = project_dir / file_path
        # Security: ensure path stays within project directory before creating anything.
        try:
            full_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            return f"Error: Path '{file_path}' escapes the project directory"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {file_path}"
