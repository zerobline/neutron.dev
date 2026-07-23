from types import SimpleNamespace

from app.crew.presentation import (
    build_phase_result_event,
    headline_for_result,
    human_summary_for_result,
    humanize_text,
    looks_like_inventory,
    looks_like_json_blob,
)
from app.crew.schemas import (
    AnalysisReportSpec,
    ArchitectureSpec,
    ColorPalette,
    PageSpec,
    ProjectBriefSpec,
    ProjectPlanSpec,
    TypographySpec,
)


def test_build_phase_result_event_for_plan_spec():
    spec = ProjectPlanSpec(
        headline="Portfolio MVP plan",
        summary="A focused portfolio plan with one landing page and a contact flow.",
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section", "Project grid"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        milestones=["Ship landing page"],
    )
    result = SimpleNamespace(pydantic=spec, raw="ignored")

    event = build_phase_result_event(
        phase="planning",
        agent="product_manager",
        result=result,
        output_text="ignored",
        task_label="Planning",
    )

    assert event["type"] == "phase_result"
    assert event["kind"] == "plan"
    assert event["headline"] == "Portfolio MVP plan"
    assert "focused portfolio plan" in event["summary"]
    assert event["has_structured_spec"] is True
    assert event["spec"]["mvp_features"] == ["Hero section", "Project grid"]


def test_human_summary_falls_back_to_prose():
    result = SimpleNamespace(pydantic=None, raw="# Title\n\nFirst paragraph for readers.\n\nSecond.")
    summary = human_summary_for_result(result, result.raw, "leading")
    assert summary == "First paragraph for readers."
    assert headline_for_result(result, result.raw, "leading", "Fallback") == "Title"


def test_brief_and_architecture_summaries():
    brief = ProjectBriefSpec(
        summary="Clarify a SaaS dashboard request.",
        user_intent="Build a SaaS dashboard for freelancers",
        target_users=["Freelancers"],
        functional_requirements=["Auth"],
        mvp_inclusions=["Dashboard"],
        success_criteria=["Users can sign in"],
    )
    architecture = ArchitectureSpec(
        summary="Static architecture with three root files.",
        system_overview="A static portfolio architecture with semantic HTML and client-side tabs.",
        components=["Header"],
        color_palette=ColorPalette(
            primary="#111111",
            secondary="#222222",
            accent="#333333",
            background="#FFFFFF",
            text="#000000",
        ),
        typography=TypographySpec(
            heading_font="Inter",
            body_font="Inter",
            heading_sizes=["2rem"],
            body_size="1rem",
        ),
        layouts=["Landing page"],
        component_specs=["Primary button"],
        responsive_notes="Mobile-first layout with stacked sections.",
        required_files=["index.html", "styles.css", "app.js"],
    )
    analysis = AnalysisReportSpec(
        summary="Research favors a static dashboard MVP.",
        workflows=["Sign in and review metrics"],
        recommendations=["Start with localStorage-backed state"],
    )

    assert human_summary_for_result(SimpleNamespace(pydantic=brief), "", "leading") == brief.summary
    assert human_summary_for_result(SimpleNamespace(pydantic=architecture), "", "architecting") == architecture.summary
    assert human_summary_for_result(SimpleNamespace(pydantic=analysis), "", "analyzing") == analysis.summary


def test_recovers_structured_fields_from_raw_json_blob():
    raw = (
        '{"headline":"Admin Dashboard with Analytics & User Management",'
        '"summary":"Build a complete admin dashboard with sidebar navigation and analytics.",'
        '"user_intent":"Build an admin dashboard",'
        '"target_users":["Operators"],'
        '"functional_requirements":["Sidebar navigation"],'
        '"mvp_inclusions":["Stats cards"],'
        '"success_criteria":["Operators can review metrics"]}'
    )
    result = SimpleNamespace(pydantic=None, raw=raw)
    event = build_phase_result_event(
        phase="leading",
        agent="team_leader",
        result=result,
        output_text=raw,
        task_label="Reviewing your brief",
    )

    assert event["headline"] == "Admin Dashboard with Analytics & User Management"
    assert event["summary"].startswith("Build a complete admin dashboard")
    assert event["has_structured_spec"] is True
    assert looks_like_json_blob(event["summary"]) is False
    assert looks_like_json_blob(event["headline"]) is False


def test_humanize_text_never_returns_json():
    raw = '{"headline":"Plan","summary":"A clear product plan for the MVP."}'
    assert humanize_text(raw) == "A clear product plan for the MVP."
    assert humanize_text("{not-json", fallback="Working") == "Working"


def test_skips_markdown_file_inventory_as_summary():
    inventory = (
        "## Files written\n\n"
        "- index.html\n"
        "- styles.css\n"
        "- app.js\n\n"
        "## Behaviors implemented\n\n"
        "- Tabs\n"
        "- Responsive layout\n"
    )
    assert looks_like_inventory(inventory) is True
    assert looks_like_inventory("") is False
    assert looks_like_inventory("A normal paragraph about the product.") is False
    assert looks_like_inventory("index.html\nstyles.css\napp.js") is True
    assert looks_like_inventory("## Files written\n\n") is True
    assert human_summary_for_result(
        type("obj", (object,), {"pydantic": None, "raw": inventory})(),
        inventory,
        "building",
    ) == ""
    event = build_phase_result_event(
        phase="building",
        agent="engineer",
        result=type("obj", (object,), {"pydantic": None, "raw": inventory})(),
        output_text=inventory,
        task_label="Building and validating files",
    )
    assert event["summary"] == "Building and validating files"
    assert event["headline"] == "Building and validating files"
    assert looks_like_inventory(event["summary"]) is False

    prose_first = (
        "Built a fraud operations console with alert triage and case notes.\n\n"
        "## Files written\n\n"
        "- index.html\n"
        "- styles.css\n"
    )
    assert human_summary_for_result(
        type("obj", (object,), {"pydantic": None, "raw": prose_first})(),
        prose_first,
        "building",
    ).startswith("Built a fraud operations console")
    assert humanize_text(inventory, fallback="Project files ready") == "Project files ready"
    assert humanize_text(prose_first).startswith("Built a fraud operations console")

    # Heading / bullet-only blocks are skipped when hunting for prose.
    mixed = (
        "# Build report\n\n"
        "- only.html\n\n"
        "Ship-ready console for operators.\n\n"
        "## Files written\n\n"
        "- styles.css\n"
    )
    assert human_summary_for_result(
        type("obj", (object,), {"pydantic": None, "raw": mixed})(),
        mixed,
        "building",
    ) == "Ship-ready console for operators."
