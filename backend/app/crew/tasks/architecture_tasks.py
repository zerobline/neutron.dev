from crewai import Task, Agent

from app.config import settings
from app.crew.guardrails import make_architecture_guardrail
from app.crew.schemas import ArchitectureSpec
from app.crew.stacks import normalize_stack, required_files_for_stack


def create_architecture_task(architect: Agent, user_prompt: str, stack: str = "static") -> Task:
    stack_name = normalize_stack(stack)
    required = ", ".join(required_files_for_stack(stack_name))

    if stack_name == "nextjs":
        description = (
            f"Create an implementation-ready Next.js App Router architecture for:\n\n"
            f"'{user_prompt}'\n\n"
            "Use the accepted product plan from context. Target a modern Next.js (App Router) + TypeScript + "
            "React project that the engineer can write fully with write_code_file. Populate every field:\n"
            "1. headline and summary for the chat card\n"
            "2. system_overview and components (React components / app routes)\n"
            "3. color_palette with hex values for primary, secondary, accent, background, and text\n"
            "4. typography with heading/body fonts and sizes\n"
            "5. layouts and app router page/route structure (app/page.tsx, nested routes as needed)\n"
            "6. component_specs including states, interactions, empty/loading/error behavior, and accessibility\n"
            "7. responsive_notes with breakpoints and mobile behavior\n"
            f"8. required_files MUST include: {required}\n"
            "9. client_side_behavior describing client components, localStorage, and App Router navigation "
            "(next/link) — no fake server APIs unless mocked in-process\n"
            "10. accessibility_notes and external_dependencies (prefer zero external runtime deps beyond Next)\n"
            "Do not require a separate Express server, database, or Docker. Client-only demo data is expected."
        )
        expected = (
            "A complete ArchitectureSpec for a Next.js App Router TypeScript app, with headline, summary, "
            f"required files ({required}), visual specs, and client-side behavior."
        )
    else:
        description = (
            f"Create an implementation-ready static web architecture for the following project:\n\n"
            f"'{user_prompt}'\n\n"
            "Use the accepted product plan from context and resolve conflicts explicitly. The generated project is "
            "served directly from its files with no compilation or application server. Populate every field:\n"
            "1. headline and summary for the chat card\n"
            "2. system_overview and components\n"
            "3. color_palette with hex values for primary, secondary, accent, background, and text\n"
            "4. typography with heading/body fonts and sizes\n"
            "5. layouts and semantic page/section structure\n"
            "6. component_specs including states, interactions, empty/loading/error behavior, and accessibility\n"
            "7. responsive_notes with breakpoints and mobile behavior\n"
            f"8. required_files including {required} with relative references\n"
            "9. client_side_behavior describing hash/data-tab panel navigation (never root-relative routes or "
            "iframe-based page loading), state, validation, and browser-compatible persistence\n"
            "10. accessibility_notes and external_dependencies\n"
            "Do not require React, Next.js, JSX/TSX, npm, a bundler, server routes, server-side rendering, or a "
            "database unless compatible infrastructure is explicitly supplied."
        )
        expected = (
            "A complete ArchitectureSpec for a directly served browser-native application, with headline, summary, "
            "required root files, visual specifications, component behavior, responsive rules, accessibility, "
            "and client-side state."
        )

    return Task(
        description=description,
        expected_output=expected,
        agent=architect,
        output_pydantic=ArchitectureSpec,
        guardrails=[make_architecture_guardrail(stack_name)],
        guardrail_max_retries=settings.task_guardrail_max_retries,
    )
