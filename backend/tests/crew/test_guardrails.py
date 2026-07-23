from unittest.mock import MagicMock

from app.crew.guardrails import (
    validate_analysis_report,
    validate_architecture_spec,
    validate_project_brief,
    validate_project_plan,
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


def test_validate_project_brief_accepts_structured_output():
    spec = ProjectBriefSpec(
        user_intent="Build a SaaS dashboard for freelancers tracking invoices.",
        target_users=["Freelancers"],
        functional_requirements=["Invoice list"],
        mvp_inclusions=["Dashboard home"],
        success_criteria=["Users can review invoices"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, result = validate_project_brief(output)
    assert ok is True
    assert result is output


def test_validate_project_brief_rejects_short_text():
    output = MagicMock(pydantic=None, raw="too short")
    ok, message = validate_project_brief(output)
    assert ok is False
    assert "too short" in message.lower()


def test_validate_analysis_report_accepts_structured_output():
    spec = AnalysisReportSpec(
        workflows=["Review dashboard metrics"],
        recommendations=["Ship a static MVP first"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, result = validate_analysis_report(output)
    assert ok is True
    assert result is output


def test_validate_analysis_report_rejects_short_text():
    output = MagicMock(pydantic=None, raw="too short")
    ok, message = validate_analysis_report(output)
    assert ok is False
    assert "too short" in message.lower()


def test_validate_project_plan_accepts_structured_output():
    spec = ProjectPlanSpec(
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, result = validate_project_plan(output)
    assert ok is True
    assert result is output


def test_validate_project_plan_rejects_short_text():
    output = MagicMock(pydantic=None, raw="too short")
    ok, message = validate_project_plan(output)
    assert ok is False
    assert "too short" in message.lower()


def test_validate_architecture_spec_requires_core_files():
    spec = ArchitectureSpec(
        system_overview="A portfolio site with responsive layout and polished UI.",
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
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, result = validate_architecture_spec(output)
    assert ok is True
    assert result is output


def test_validate_architecture_spec_rejects_missing_file_mentions():
    output = MagicMock(pydantic=None, raw="layout only")
    ok, message = validate_architecture_spec(output)
    assert ok is False
    assert "index.html" in message


def test_validate_project_plan_rejects_empty_pages_in_spec():
    spec = ProjectPlanSpec.model_construct(
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, message = validate_project_plan(output)
    assert ok is False
    assert "page" in message.lower()


def test_validate_project_plan_accepts_long_text_fallback():
    output = MagicMock(pydantic=None, raw=" ".join(["word"] * 90))
    ok, result = validate_project_plan(output)
    assert ok is True
    assert result is output


def test_validate_project_plan_rejects_empty_mvp_features_in_spec():
    spec = ProjectPlanSpec.model_construct(
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=[],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, message = validate_project_plan(output)
    assert ok is False
    assert "mvp" in message.lower()


def test_validate_project_plan_coerces_non_string_raw():
    output = MagicMock(pydantic=None, raw=12345)
    ok, message = validate_project_plan(output)
    assert ok is False
    assert "too short" in message.lower()


def test_validate_architecture_spec_rejects_missing_files_in_structured_output():
    spec = ArchitectureSpec.model_construct(
        system_overview="A portfolio site with responsive layout and polished UI.",
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
        required_files=["index.html"],
    )
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, message = validate_architecture_spec(output)
    assert ok is False
    assert "styles.css" in message


def test_validate_architecture_spec_rejects_unsupported_runtime_in_structured_output():
    spec = ArchitectureSpec(
        system_overview="A React SPA with client-side routing and npm run build.",
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
    output = MagicMock(pydantic=spec, raw="ignored")
    ok, message = validate_architecture_spec(output)
    assert ok is False
    assert "react" in message.lower()


def test_validate_architecture_spec_rejects_unsupported_runtime_in_text_fallback():
    output = MagicMock(
        pydantic=None,
        raw="required_files: index.html, styles.css, app.js using next.js rendering",
    )
    ok, message = validate_architecture_spec(output)
    assert ok is False
    assert "next.js" in message.lower()


def test_validate_architecture_spec_accepts_text_with_required_files():
    output = MagicMock(
        pydantic=None,
        raw="required_files: index.html, styles.css, app.js with full architecture details",
    )
    ok, result = validate_architecture_spec(output)
    assert ok is True
    assert result is output


def test_validate_architecture_spec_accepts_negated_runtime_terms_in_structured_output():
    spec = ArchitectureSpec(
        system_overview="A static dashboard with no React and no server routes.",
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
        external_dependencies=["No npm run step, Next.js, or server-side rendering is required."],
    )
    output = MagicMock(pydantic=spec, raw="ignored")

    ok, result = validate_architecture_spec(output)

    assert ok is True
    assert result is output


def test_validate_architecture_spec_accepts_runtime_term_negated_after_mention():
    output = MagicMock(
        pydantic=None,
        raw="required_files: index.html, styles.css, app.js. Server routes are not required.",
    )

    ok, result = validate_architecture_spec(output)

    assert ok is True
    assert result is output


def test_validate_architecture_spec_still_rejects_positive_server_route_requirement():
    output = MagicMock(
        pydantic=None,
        raw="required_files: index.html, styles.css, app.js. Add a server route for form submission.",
    )

    ok, message = validate_architecture_spec(output)

    assert ok is False
    assert "server route" in message.lower()
