"""Single-agent consult tasks for post-build @kai / @nina / @theo / @zara mentions."""

from crewai import Task, Agent


def create_consult_task(agent: Agent, user_prompt: str, consult_request: str, agent_key: str) -> Task:
    role_focus = {
        "team_leader": (
            "Clarify scope, risks, priorities, and what the engineer should do next. "
            "Give a crisp decision brief, not full code."
        ),
        "product_manager": (
            "Advise on product scope, MVP tradeoffs, user flows, and feature prioritization. "
            "Do not write implementation code."
        ),
        "architect": (
            "Advise on structure, file layout, UI composition, accessibility, and technical tradeoffs "
            "for this static HTML/CSS/JS project. Do not dump full file contents."
        ),
        "data_scientist": (
            "Advise on data model shape, mock datasets, metrics, and analysis approach for this app. "
            "Suggest concrete seed-data shapes the engineer can implement."
        ),
    }.get(agent_key, "Give practical advice for this project.")

    return Task(
        description=(
            f"The user has an existing generated web project.\n\n"
            f"Original project brief:\n'{user_prompt}'\n\n"
            f"User question for you:\n'{consult_request}'\n\n"
            f"Your focus: {role_focus}\n\n"
            "Respond with a short headline-worthy answer: 3–8 concrete bullets or short paragraphs. "
            "If code is needed, outline what the engineer should change rather than rewriting whole files. "
            "Stay browser-native (static HTML/CSS/JS) and actionable."
        ),
        expected_output=(
            "A concise advisory response with clear recommendations the user can act on "
            "(or hand to @engineer)."
        ),
        agent=agent,
    )
