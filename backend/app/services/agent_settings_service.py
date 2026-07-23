"""Per-agent model overrides stored on user_settings.agent_models JSON."""

from __future__ import annotations

import json
from typing import Any

from app.database import db_connection
from app.services import provider_settings_service

AGENT_IDS = (
    "team_leader",
    "data_scientist",
    "product_manager",
    "architect",
    "engineer",
)

AGENT_LABELS = {
    "team_leader": "Kai — Team Leader",
    "data_scientist": "Zara — Data Scientist",
    "product_manager": "Nina — Product Manager",
    "architect": "Theo — System Architect",
    "engineer": "Ravi — Software Engineer",
}


def _parse_agent_models(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if key in AGENT_IDS and isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def get_agent_models(user_id: str) -> dict[str, Any]:
    active = provider_settings_service.get_active_provider_settings(user_id)
    with db_connection() as conn:
        row = conn.execute(
            "SELECT agent_models FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    overrides = _parse_agent_models(row["agent_models"] if row else None)
    agents = []
    for agent_id in AGENT_IDS:
        model = overrides.get(agent_id) or active.model
        agents.append(
            {
                "id": agent_id,
                "label": AGENT_LABELS[agent_id],
                "model": model,
                "is_override": agent_id in overrides,
            }
        )
    return {
        "provider": active.provider,
        "default_model": active.model,
        "agents": agents,
    }


def update_agent_models(user_id: str, models: dict[str, str | None]) -> dict[str, Any]:
    cleaned: dict[str, str] = {}
    for agent_id, model in (models or {}).items():
        if agent_id not in AGENT_IDS:
            continue
        if model is None:
            continue
        text = str(model).strip()
        if text:
            cleaned[agent_id] = text

    with db_connection() as conn:
        # Ensure user_settings row exists
        provider_settings_service._active_provider(conn, user_id)  # noqa: SLF001
        conn.execute(
            """
            UPDATE user_settings
            SET agent_models = ?, updated_at = datetime('now')
            WHERE user_id = ?
            """,
            (json.dumps(cleaned), user_id),
        )
        conn.commit()
    return get_agent_models(user_id)


def resolve_model_for_agent(user_id: str | None, agent_id: str | None) -> str | None:
    """Return unprefixed model override for an agent, or None to use active provider default."""
    if not user_id or not agent_id or agent_id not in AGENT_IDS:
        return None
    with db_connection() as conn:
        row = conn.execute(
            "SELECT agent_models FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    overrides = _parse_agent_models(row["agent_models"] if row else None)
    return overrides.get(agent_id)
