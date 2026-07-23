import pytest

from app.crew.tools.code_writer import CodeWriterTool
from app.crew.tools.component_generator import ComponentGeneratorTool
from app.crew.tools.file_reader import FileReaderTool


@pytest.fixture
def tool_project(settings_projects_dir):
    project_id = "toolproj"
    (settings_projects_dir / project_id).mkdir(parents=True, exist_ok=True)
    return project_id


def test_code_writer_creates_file(tool_project, settings_projects_dir):
    tool = CodeWriterTool(project_id=tool_project)
    result = tool._run("src/app.js", "console.log('hi');")
    assert "Successfully wrote" in result
    assert (settings_projects_dir / tool_project / "src/app.js").read_text() == "console.log('hi');"


def test_code_writer_accepts_kwargs_and_strips_leaked_thought(tool_project, settings_projects_dir):
    tool = CodeWriterTool(project_id=tool_project)
    result = tool._run(
        file_path="app/page.tsx",
        content="export default function Page(){return <main>Hi</main>}\nThought: done\nAction: other",
    )
    assert "Successfully wrote" in result
    text = (settings_projects_dir / tool_project / "app/page.tsx").read_text()
    assert "export default function Page" in text
    assert "Thought:" not in text


def test_code_writer_accepts_dict_arg(tool_project, settings_projects_dir):
    tool = CodeWriterTool(project_id=tool_project)
    result = tool._run(
        {
            "file_path": "next.config.mjs",
            "content": "export default { reactStrictMode: true };\n",
        }
    )
    assert "Successfully wrote" in result
    assert "reactStrictMode" in (settings_projects_dir / tool_project / "next.config.mjs").read_text()


def test_code_writer_blocks_path_traversal(tool_project):
    tool = CodeWriterTool(project_id=tool_project)
    result = tool._run("../../outside.txt", "bad")
    assert "escapes the project directory" in result


def test_file_reader_reads_file(tool_project, settings_projects_dir):
    (settings_projects_dir / tool_project / "readme.md").write_text("# Hello")
    tool = FileReaderTool(project_id=tool_project)
    result = tool._run("readme.md")
    assert result == "# Hello"


def test_file_reader_missing_file(tool_project):
    tool = FileReaderTool(project_id=tool_project)
    result = tool._run("missing.txt")
    assert "not found" in result


def test_file_reader_blocks_path_traversal(tool_project):
    tool = FileReaderTool(project_id=tool_project)
    result = tool._run("../../etc/passwd")
    assert "escapes the project directory" in result


def test_component_generator_writes_tsx_and_css(tool_project, settings_projects_dir):
    tool = ComponentGeneratorTool(project_id=tool_project)
    result = tool._run(
        component_name="Header",
        html_content="<header>Title</header>",
        css_content="header { color: red; }",
        file_path="src/components/Header.tsx",
    )
    assert "Created component Header" in result

    tsx = (settings_projects_dir / tool_project / "src/components/Header.tsx").read_text()
    css = (settings_projects_dir / tool_project / "src/components/Header.css").read_text()
    assert "export default function Header()" in tsx
    assert "header { color: red; }" in css


def test_component_generator_blocks_path_traversal(tool_project):
    tool = ComponentGeneratorTool(project_id=tool_project)
    result = tool._run(
        component_name="Bad",
        html_content="x",
        css_content="y",
        file_path="../../Bad.tsx",
    )
    assert "escapes the project directory" in result
