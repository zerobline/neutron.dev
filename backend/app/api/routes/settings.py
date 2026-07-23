from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_optional_user
from app.config import settings
from app.models import (
    AgentModelsResponse,
    AgentModelsUpdate,
    AvailableModelsResponse,
    DefaultMcpKey,
    McpConnectorListResponse,
    McpConnectorSettingsUpdate,
    McpConnectorSummary,
    ProviderListResponse,
    ProviderModelsResponse,
    ProviderName,
    ProviderSettingsResponse,
    ProviderSettingsUpdate,
    SearchProviderListResponse,
    SearchProviderName,
    SearchProviderSettingsUpdate,
    SearchProviderSummary,
    UserResponse,
)
from app.services import (
    agent_settings_service,
    mcp_connector_settings_service,
    model_catalog_service,
    provider_settings_service,
    search_provider_settings_service,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/models", response_model=AvailableModelsResponse)
def get_available_models():
    return settings.available_models_response()


@router.get("/agent-models", response_model=AgentModelsResponse)
def get_agent_models(current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return agent_settings_service.get_agent_models(current_user.id)


@router.put("/agent-models", response_model=AgentModelsResponse)
def put_agent_models(
    data: AgentModelsUpdate,
    current_user: UserResponse | None = Depends(get_optional_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return agent_settings_service.update_agent_models(current_user.id, data.models)


@router.get("/providers", response_model=ProviderListResponse)
def get_provider_settings_list(current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return provider_settings_service.list_provider_settings(current_user.id)


@router.get("/providers/{provider}/models", response_model=ProviderModelsResponse)
def get_provider_models(provider: ProviderName, current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return model_catalog_service.list_provider_models(current_user.id, provider)


@router.get("/provider", response_model=ProviderSettingsResponse)
def get_provider_settings(current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return provider_settings_service.get_active_provider_settings(current_user.id)


@router.put("/provider", response_model=ProviderSettingsResponse)
def update_provider_settings(data: ProviderSettingsUpdate, current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        return provider_settings_service.update_provider_settings(current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/provider/{provider}/activate", response_model=ProviderSettingsResponse)
def activate_provider(provider: ProviderName, current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return provider_settings_service.activate_provider(current_user.id, provider)


@router.delete("/provider/{provider}/key", response_model=ProviderSettingsResponse)
def clear_provider_key(provider: ProviderName, current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return provider_settings_service.clear_provider_key(current_user.id, provider)


@router.get("/search-providers", response_model=SearchProviderListResponse)
def get_search_provider_settings(current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return search_provider_settings_service.list_search_provider_settings(current_user.id)


@router.put("/search-provider", response_model=SearchProviderSummary)
def update_search_provider_settings(
    data: SearchProviderSettingsUpdate,
    current_user: UserResponse | None = Depends(get_optional_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return search_provider_settings_service.update_search_provider_settings(current_user.id, data)


@router.delete("/search-provider/{provider}/key", response_model=SearchProviderSummary)
def clear_search_provider_key(
    provider: SearchProviderName,
    current_user: UserResponse | None = Depends(get_optional_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return search_provider_settings_service.clear_search_provider_key(current_user.id, provider)


@router.get("/mcp-connectors", response_model=McpConnectorListResponse)
def get_mcp_connector_settings(current_user: UserResponse | None = Depends(get_optional_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return mcp_connector_settings_service.list_mcp_connector_settings(current_user.id)


@router.put("/mcp-connector", response_model=McpConnectorSummary)
def update_mcp_connector_settings(
    data: McpConnectorSettingsUpdate,
    current_user: UserResponse | None = Depends(get_optional_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return mcp_connector_settings_service.update_mcp_connector_settings(current_user.id, data)


@router.delete("/mcp-connector/{key}/key", response_model=McpConnectorSummary)
def clear_mcp_connector_key(
    key: DefaultMcpKey,
    current_user: UserResponse | None = Depends(get_optional_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return mcp_connector_settings_service.clear_mcp_connector_key(current_user.id, key)
