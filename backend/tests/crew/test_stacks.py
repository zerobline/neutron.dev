from app.crew.schemas import ArchitectureSpec, ColorPalette, TypographySpec
from app.crew.stacks import normalize_stack, required_files_for_stack, stack_accepts_required_files
from app.crew.tasks.architecture_tasks import create_architecture_task
from app.crew.tasks.engineering_tasks import create_engineering_task
from app.crew.agents.architect import create_architect_agent
from app.crew.agents.engineer import create_engineer_agent


def test_normalize_and_required_files():
    assert normalize_stack("NEXTJS") == "nextjs"
    assert normalize_stack(None) == "static"
    assert "app/page.tsx" in required_files_for_stack("nextjs")
    assert "index.html" in required_files_for_stack("static")


def test_architecture_spec_accepts_nextjs_files():
    palette = ColorPalette(
        primary="#111111",
        secondary="#222222",
        accent="#333333",
        background="#FFFFFF",
        text="#000000",
    )
    type_spec = TypographySpec(
        heading_font="Inter",
        body_font="Inter",
        heading_sizes=["2rem"],
        body_size="1rem",
    )
    spec = ArchitectureSpec(
        summary="Next app architecture for a dashboard MVP with client-side data.",
        system_overview="App Router layout with sidebar and overview page components.",
        components=["Sidebar", "KpiCard"],
        color_palette=palette,
        typography=type_spec,
        layouts=["Dashboard shell"],
        component_specs=["KPI card with delta"],
        responsive_notes="Mobile sidebar collapses.",
        required_files=list(required_files_for_stack("nextjs")),
    )
    assert "package.json" in spec.required_files


def test_engineering_task_switches_by_stack():
    engineer = create_engineer_agent()
    static_task = create_engineering_task(engineer, "Landing page")
    assert "index.html" in static_task.description
    assert "Next.js" not in static_task.description or "Do not generate React, Next.js" in static_task.description

    next_task = create_engineering_task(engineer, "SaaS dashboard", stack="nextjs")
    assert "package.json" in next_task.description
    assert "app/page.tsx" in next_task.description
    assert "npm run dev" in next_task.expected_output


def test_architecture_task_nextjs_allows_react_terms():
    architect = create_architect_agent()
    task = create_architecture_task(architect, "Build a SaaS dashboard", stack="nextjs")
    assert "App Router" in task.description
    assert "package.json" in task.description
