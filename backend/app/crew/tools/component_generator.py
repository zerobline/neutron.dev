from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from app.config import settings


class ComponentInput(BaseModel):
    component_name: str = Field(description="Name of the React component (PascalCase)")
    html_content: str = Field(description="The HTML/JSX content for the component")
    css_content: str = Field(description="The CSS styles for the component")
    file_path: str = Field(description="Relative path where to save (e.g., 'src/components/Header.tsx')")


class ComponentGeneratorTool(BaseTool):
    name: str = "generate_component"
    description: str = (
        "Generate a React component file with its styles. Creates a TSX file "
        "with the component and an accompanying CSS module."
    )
    args_schema: Type[BaseModel] = ComponentInput
    project_id: str = ""

    def _run(self, component_name: str, html_content: str, css_content: str, file_path: str) -> str:
        project_dir = settings.projects_dir / self.project_id
        full_path = project_dir / file_path
        try:
            full_path.resolve().relative_to(project_dir.resolve())
        except ValueError:
            return f"Error: Path '{file_path}' escapes the project directory"
        full_path.parent.mkdir(parents=True, exist_ok=True)

        tsx_content = f'''import React from 'react';
import './{component_name}.css';

export default function {component_name}() {{
  return (
    {html_content}
  );
}}
'''
        full_path.write_text(tsx_content, encoding="utf-8")

        css_path = full_path.parent / f"{component_name}.css"
        css_path.write_text(css_content, encoding="utf-8")

        return f"Created component {component_name} at {file_path} with styles"
