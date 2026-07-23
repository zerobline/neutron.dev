import pytest
from pydantic import ValidationError

from app.crew.schemas import (
    AnalysisReportSpec,
    ArchitectureSpec,
    BuildSummarySpec,
    ColorPalette,
    PageSpec,
    ProjectBriefSpec,
    ProjectPlanSpec,
    TypographySpec,
)


def test_project_brief_and_analysis_specs_valid():
    brief = ProjectBriefSpec(
        headline="SaaS brief",
        summary="Clarify a freelancing dashboard MVP.",
        user_intent="Build a SaaS dashboard for freelancers tracking invoices.",
        target_users=["Freelancers"],
        functional_requirements=["Invoice list"],
        mvp_inclusions=["Dashboard home"],
        success_criteria=["Users can review invoices"],
    )
    analysis = AnalysisReportSpec(
        headline="Market notes",
        summary="Static MVP is enough for the first release.",
        workflows=["Review dashboard metrics"],
        recommendations=["Ship a static MVP first"],
    )
    build = BuildSummarySpec(
        headline="Files ready",
        summary="Wrote the three root project files.",
        files_written=["index.html", "styles.css", "app.js"],
        behaviors_implemented=["Client-side navigation"],
    )
    assert brief.target_users == ["Freelancers"]
    assert analysis.recommendations[0].startswith("Ship")
    assert build.files_written[0] == "index.html"


def test_project_plan_spec_valid():
    spec = ProjectPlanSpec(
        headline="Portfolio plan",
        summary="A focused portfolio MVP.",
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero", "CTA"])],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    assert spec.pages[0].name == "Home"
    assert spec.summary.startswith("A focused")


def test_architecture_spec_requires_core_files():
    with pytest.raises(ValidationError, match="required_files must include"):
        ArchitectureSpec(
            system_overview="A portfolio site with responsive layout and polished UI.",
            components=["Header", "Hero"],
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
            layouts=["Single column landing page"],
            component_specs=["Primary button"],
            responsive_notes="Mobile-first layout with stacked sections.",
            required_files=["index.html", "styles.css", "foo.js"],
        )


def test_architecture_spec_normalizes_dot_slash_prefix():
    spec = ArchitectureSpec(
        system_overview="A portfolio site with responsive layout and polished UI.",
        components=["Header", "Hero"],
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
        layouts=["Single column landing page"],
        component_specs=["Primary button"],
        responsive_notes="Mobile-first layout with stacked sections.",
        required_files=["./index.html", "./styles.css", "./app.js"],
    )
    assert spec.required_files == ["index.html", "styles.css", "app.js"]


def test_color_palette_rejects_invalid_hex():
    with pytest.raises(ValidationError):
        ColorPalette(
            primary="blue",
            secondary="#222222",
            accent="#333333",
            background="#FFFFFF",
            text="#000000",
        )