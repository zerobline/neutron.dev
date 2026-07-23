from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from app.config import settings


class FileReaderInput(BaseModel):
    file_path: str = Field(description="Relative file path within the project to read")


class FileReaderTool(BaseTool):
    name: str = "read_project_file"
    description: str = "Read the contents of a file in the project directory."
    args_schema: Type[BaseModel] = FileReaderInput
    project_id: str = ""

    def _run(self, file_path: str) -> str:
        project_dir = settings.projects_dir / self.project_id
        full_path = project_dir / file_path
        try:
            full_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            return f"Error: Path '{file_path}' escapes the project directory"
        if not full_path.exists():
            return f"Error: File '{file_path}' not found"
        return full_path.read_text(encoding="utf-8")
