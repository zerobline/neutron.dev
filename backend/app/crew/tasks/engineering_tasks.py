from crewai import Task, Agent

from app.crew.schemas import REQUIRED_PROJECT_FILES
from app.crew.stacks import normalize_stack, required_files_for_stack
from app.crew.static_navigation import NAVIGATION_CONTRACT

PROJECT_FILE_PURPOSES = {
    "index.html": "Main semantic HTML entry point with all pages or sections",
    "styles.css": "Complete responsive stylesheet implementing the architecture",
    "app.js": "Browser-native JavaScript for interactions and state",
    "package.json": "Next.js dependencies and npm scripts",
    "tsconfig.json": "TypeScript configuration for the Next.js app",
    "next.config.mjs": "Next.js configuration",
    "app/layout.tsx": "Root App Router layout with fonts and metadata",
    "app/page.tsx": "Home page route with the primary UI",
    "app/globals.css": "Global styles and CSS variables",
}


def create_engineering_task(engineer: Agent, user_prompt: str, stack: str = "static") -> Task:
    stack_name = normalize_stack(stack)
    if stack_name == "nextjs":
        required = required_files_for_stack("nextjs")
        listed = "\n".join(f"- {name}" for name in required)
        return Task(
            description=(
                f"Build a complete Next.js App Router (TypeScript) project for:\n\n"
                f"'{user_prompt}'\n\n"
                "CRITICAL: You MUST call write_code_file with complete contents for every file you create. "
                "A text-only answer or fenced code is rejected.\n\n"
                "Write at least these files:\n"
                f"{listed}\n\n"
                "Also add any additional app routes/components needed for a polished MVP "
                "(e.g. app/components/*.tsx).\n\n"
                "Requirements:\n"
                "- Next.js 15 App Router + React + TypeScript\n"
                "- package.json with next, react, react-dom, typescript, @types/react, @types/node, "
                "and scripts: dev, build, start, lint\n"
                "- Use 'use client' where interactivity is needed\n"
                "- next/link for navigation between pages/sections\n"
                "- Seed realistic demo data so lists/tables/cards are filled on first load (6–12 items)\n"
                "- Polished, accessible UI with responsive layout and a coherent color system\n"
                "- No placeholder TODOs; no empty stub pages\n"
                "- Do not require a database, Docker, or external API keys for the demo to run\n"
            ),
            expected_output=(
                "All required Next.js files written via write_code_file with seeded demo data and a concise "
                "summary of routes and behaviors. User can run: npm install && npm run dev"
            ),
            agent=engineer,
        )

    return Task(
        description=(
            f"Build the project based on the accepted plan and architecture:\n\n"
            f"'{user_prompt}'\n\n"
            "The project is served directly from disk with no compilation step or application server.\n\n"
            "CRITICAL: You MUST call write_code_file with complete contents for every file you create. "
            "A text-only answer or fenced code is rejected.\n\n"
            "Create these root files at minimum:\n"
            "1. index.html — semantic entry point that references ./styles.css and ./app.js\n"
            "2. styles.css — complete responsive styles\n"
            "3. app.js — browser-native interactions, navigation, validation, and state\n\n"
            f"{NAVIGATION_CONTRACT}\n\n"
            "DEMO DATA (required for a first-impression preview):\n"
            "- Seed realistic in-memory data in app.js so tables, cards, lists, boards, and charts are NOT empty "
            "on first load.\n"
            "- Prefer 6–12 demo rows for primary collections (tasks, products, alerts, messages, etc.).\n"
            "- Render seed data immediately on DOMContentLoaded / script load — not only after user clicks.\n"
            "- Empty states are fine as fallbacks, but the default view must look filled and demo-ready.\n\n"
            "Use relative asset paths. Do not generate React, Next.js, JSX/TSX, package manifests, npm scripts, "
            "bundler configuration, server-only imports, placeholder TODOs, or dev-server assumptions. Implement "
            "accessible controls, working navigation and interactions, valid DOM references, responsive behavior, "
            "and the approved visual specification. Additional static assets are allowed when referenced correctly."
        ),
        expected_output=(
            "All required project files written successfully with write_code_file, including seeded demo data so "
            "the UI looks populated on first load, followed by a concise summary of files and behavior."
        ),
        agent=engineer,
    )


def create_iteration_task(
    engineer: Agent,
    user_prompt: str,
    iteration_request: str,
    stack: str = "static",
) -> Task:
    stack_name = normalize_stack(stack)
    if stack_name == "nextjs":
        return Task(
            description=(
                f"The user wants to modify an existing Next.js App Router project.\n\n"
                f"Original project description: '{user_prompt}'\n\n"
                f"User's change request: '{iteration_request}'\n\n"
                "STEPS:\n"
                "1. Use read_project_file to inspect existing files before editing.\n"
                "2. Make only the needed changes; preserve project structure and TypeScript correctness.\n"
                "3. Keep Next.js App Router patterns (app/, client components, next/link).\n"
                "4. If adding mock/seed data, put it in client modules and render on first load.\n"
                "5. Call write_code_file with complete file contents for every file you change.\n"
            ),
            expected_output=(
                "Changed Next.js files written with write_code_file and a concise summary of the UI impact."
            ),
            agent=engineer,
        )

    return Task(
        description=(
            f"The user wants to modify an existing directly served static project.\n\n"
            f"Original project description: '{user_prompt}'\n\n"
            f"User's change request: '{iteration_request}'\n\n"
            "STEPS:\n"
            "1. Use read_project_file to read ALL existing project files before editing.\n"
            "2. Make only the changes needed while preserving existing structure, styling, and functionality.\n"
            "3. Keep the project browser-native and directly servable without a build step.\n"
            "4. Preserve relative asset references and accessibility.\n"
            f"5. {NAVIGATION_CONTRACT}\n"
            "6. For tabs, nav items, pages, or sections: update index.html with the markup AND app.js with the "
            "matching show/hide, routing, event listeners, render, and data logic. Verify every new control has a "
            "real handler and every new panel/section exists in the DOM with matching ids or data attributes.\n\n"
            "MOCK / SAMPLE / SEED DATA (when the user asks to fill, populate, demo, or show the UI with data):\n"
            "- Add realistic in-memory seed arrays in app.js (not empty [] placeholders).\n"
            "- On initial page load, render those arrays into tables, cards, lists, metrics, and charts so the "
            "UI is visibly filled without user interaction.\n"
            "- Prefer editing app.js data + render functions; update index.html only if empty-state markup must change.\n"
            "- Include enough rows for a believable demo (typically 6–12 items for primary lists/tables).\n"
            "- Do NOT claim the work is done unless write_code_file was called with the updated file contents.\n"
            "- After writing, the preview must show populated content, not blank tables or zeroed KPIs.\n\n"
            "CRITICAL: You MUST call write_code_file with complete contents for every file you change or create. "
            "A text-only answer or fenced code is rejected. Put interaction logic in app.js, not inline <script> tags."
        ),
        expected_output=(
            "All changed and new project files written with write_code_file (including app.js seed data when "
            "requested), followed by a concise change summary of what is now visible in the UI."
        ),
        agent=engineer,
    )


def create_engineering_recovery_tasks(
    engineer: Agent,
    user_prompt: str,
    missing_files: list[str] | tuple[str, ...] | None = None,
    stack: str = "static",
) -> list[Task]:
    stack_name = normalize_stack(stack)
    required = missing_files if missing_files is not None else required_files_for_stack(stack_name)
    stack_hint = (
        "Next.js App Router TypeScript project"
        if stack_name == "nextjs"
        else "browser-native static HTML/CSS/JS project"
    )
    return [
        Task(
            description=(
                f"The previous build did not write required file '{file_path}' "
                f"({PROJECT_FILE_PURPOSES.get(file_path, 'required project file')}). Create it for this "
                f"{stack_hint}:\n\n"
                f"'{user_prompt}'\n\n"
                "Use the accepted plan and architecture context. "
                "Call write_code_file with the complete file contents before finishing."
            ),
            expected_output=f"{file_path} written via write_code_file.",
            agent=engineer,
        )
        for file_path in required
    ]


def create_navigation_recovery_task(engineer: Agent, user_prompt: str, violations: list[str]) -> Task:
    joined = "\n".join(f"- {item}" for item in violations)
    return Task(
        description=(
            f"The generated static project violated the navigation contract:\n{joined}\n\n"
            f"Rebuild index.html and app.js for this project so every tab/page works without server routes:\n\n"
            f"'{user_prompt}'\n\n"
            f"{NAVIGATION_CONTRACT}\n\n"
            "Read the current files, then call write_code_file with complete corrected contents for index.html "
            "and app.js. Preserve styles.css unless it also needs changes."
        ),
        expected_output="index.html and app.js rewritten with compliant client-side navigation.",
        agent=engineer,
    )
