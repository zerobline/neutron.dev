import re

from pydantic import BaseModel, Field, field_validator

from app.crew.stacks import (
    REQUIRED_NEXTJS_FILES,
    REQUIRED_STATIC_FILES,
    stack_accepts_required_files,
)

HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Back-compat alias used across the codebase for the default static stack.
REQUIRED_PROJECT_FILES = REQUIRED_STATIC_FILES


class PageSpec(BaseModel):
    name: str = Field(min_length=1, description="Short page or section name shown in navigation")
    purpose: str = Field(min_length=1, description="Why this page exists for the user")
    key_elements: list[str] = Field(min_length=1, description="Primary UI blocks or interactions on the page")


class ProjectBriefSpec(BaseModel):
    """Structured leadership brief for review cards and downstream handoff."""

    headline: str = Field(default="", description="Short card title for the brief")
    summary: str = Field(default="", description="2-4 sentence human summary of the clarified request")
    user_intent: str = Field(min_length=10, description="What the user is trying to achieve")
    target_users: list[str] = Field(min_length=1, description="Primary audiences for the product")
    functional_requirements: list[str] = Field(min_length=1, description="Must-have functional capabilities")
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Quality attributes such as accessibility, performance, or responsiveness",
    )
    assumptions: list[str] = Field(default_factory=list, description="Conservative assumptions that resolve ambiguity")
    mvp_inclusions: list[str] = Field(min_length=1, description="What belongs in the MVP")
    mvp_exclusions: list[str] = Field(default_factory=list, description="Explicitly out-of-scope items")
    constraints: list[str] = Field(default_factory=list, description="Hard constraints the team must preserve")
    success_criteria: list[str] = Field(min_length=1, description="Measurable conditions for success")
    handoff_notes: list[str] = Field(
        default_factory=list,
        description="Instructions analysis, planning, architecture, and engineering must preserve",
    )


class AnalysisReportSpec(BaseModel):
    """Structured analysis report separating evidence, assumptions, and recommendations."""

    headline: str = Field(default="", description="Short card title for the analysis")
    summary: str = Field(default="", description="2-4 sentence human summary of the analysis")
    workflows: list[str] = Field(min_length=1, description="Likely user workflows")
    comparable_patterns: list[str] = Field(
        default_factory=list,
        description="Comparable product patterns; label general-knowledge items clearly",
    )
    data_needs: list[str] = Field(default_factory=list, description="Product-level data or content needs")
    technology_options: list[str] = Field(
        default_factory=list,
        description="Suitable options for a directly served static web app",
    )
    risks: list[str] = Field(default_factory=list, description="Key risks and constraints")
    recommendations: list[str] = Field(min_length=1, description="Actionable recommendations for planning")
    assumptions: list[str] = Field(default_factory=list, description="Assumptions used in the analysis")
    evidence_gaps: list[str] = Field(
        default_factory=list,
        description="Facts that still need external validation",
    )


class ProjectPlanSpec(BaseModel):
    headline: str = Field(default="", description="Short card title for the product plan")
    summary: str = Field(default="", description="2-4 sentence human summary of product scope")
    overview: str = Field(min_length=20, description="Product objectives, users, and scope")
    mvp_features: list[str] = Field(min_length=1, description="Prioritized MVP capabilities")
    future_features: list[str] = Field(default_factory=list, description="Post-MVP capabilities")
    pages: list[PageSpec] = Field(min_length=1, description="Pages or major sections in the product")
    data_model_summary: str = Field(min_length=10, description="Product-level entities and information needs")
    technical_architecture: str = Field(
        default="",
        description="Leave empty; architecture owns implementation technology",
    )
    milestones: list[str] = Field(min_length=1, description="Ordered delivery outcomes")
    acceptance_criteria: list[str] = Field(default_factory=list, description="Measurable MVP completion conditions")
    user_flows: list[str] = Field(default_factory=list, description="Key journeys across pages and features")
    handoff_constraints: list[str] = Field(
        default_factory=list,
        description="Product decisions the architect and engineer must preserve",
    )


class ColorPalette(BaseModel):
    primary: str = Field(description="Primary brand color as #RRGGBB")
    secondary: str = Field(description="Secondary brand color as #RRGGBB")
    accent: str = Field(description="Accent color as #RRGGBB")
    background: str = Field(description="Page background color as #RRGGBB")
    text: str = Field(description="Default body text color as #RRGGBB")

    @field_validator("primary", "secondary", "accent", "background", "text")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        normalized = value.strip()
        if not HEX_COLOR_PATTERN.match(normalized):
            raise ValueError(f"Color '{value}' must be a hex value like #1A2B3C")
        return normalized


class TypographySpec(BaseModel):
    heading_font: str = Field(min_length=1, description="Heading font family")
    body_font: str = Field(min_length=1, description="Body font family")
    heading_sizes: list[str] = Field(min_length=1, description="Heading size scale values")
    body_size: str = Field(min_length=1, description="Default body text size")


class ArchitectureSpec(BaseModel):
    headline: str = Field(default="", description="Short card title for the architecture")
    summary: str = Field(default="", description="2-4 sentence human summary of the architecture")
    system_overview: str = Field(min_length=20, description="How the static system is organized")
    components: list[str] = Field(min_length=1, description="Major UI or behavioral components")
    color_palette: ColorPalette
    typography: TypographySpec
    layouts: list[str] = Field(min_length=1, description="Page and section layout patterns")
    component_specs: list[str] = Field(
        min_length=1,
        description="Component behavior, states, and accessibility notes",
    )
    responsive_notes: str = Field(min_length=10, description="Breakpoints and mobile behavior")
    required_files: list[str] = Field(
        min_length=3,
        description=(
            "Files that must exist for the chosen stack. Static: index.html, styles.css, app.js. "
            "Next.js: package.json, tsconfig.json, next.config.mjs, app/layout.tsx, app/page.tsx, app/globals.css."
        ),
    )
    database_schema: str | None = Field(default=None, description="Optional data shape notes")
    client_side_behavior: list[str] = Field(
        default_factory=list,
        description="Navigation, state, validation, and browser-compatible persistence rules",
    )
    accessibility_notes: list[str] = Field(default_factory=list, description="Accessibility requirements")
    external_dependencies: list[str] = Field(
        default_factory=list,
        description="Allowed external assets or APIs, if any",
    )

    @field_validator("required_files")
    @classmethod
    def validate_required_files(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lstrip("./") for item in value if item.strip()]
        if not stack_accepts_required_files(normalized):
            static = ", ".join(REQUIRED_STATIC_FILES)
            nxt = ", ".join(REQUIRED_NEXTJS_FILES)
            raise ValueError(
                f"required_files must include either static set ({static}) "
                f"or Next.js set ({nxt})"
            )
        return normalized


class BuildSummarySpec(BaseModel):
    """Structured engineering wrap-up for the chat card after files are written."""

    headline: str = Field(default="", description="Short card title for the build summary")
    summary: str = Field(default="", description="2-4 sentence human summary of what was built")
    files_written: list[str] = Field(default_factory=list, description="Project files created or updated")
    behaviors_implemented: list[str] = Field(
        default_factory=list,
        description="User-facing behaviors that now work in the browser",
    )
    known_gaps: list[str] = Field(default_factory=list, description="Known limitations or follow-ups")
