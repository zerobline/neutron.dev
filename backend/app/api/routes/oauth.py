from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.models import (
    OAuthDevicePollRequest,
    OAuthDevicePollResponse,
    OAuthDeviceStartResponse,
    ProviderSettingsResponse,
    UserResponse,
)
from app.services import provider_settings_service, xai_oauth_service

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


@router.post("/xai/device", response_model=OAuthDeviceStartResponse)
def start_xai_oauth(current_user: UserResponse = Depends(get_current_user)):
    try:
        result = xai_oauth_service.start_device_flow(current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OAuthDeviceStartResponse(**result)


@router.post("/xai/poll", response_model=OAuthDevicePollResponse)
def poll_xai_oauth(data: OAuthDevicePollRequest, current_user: UserResponse = Depends(get_current_user)):
    try:
        result = xai_oauth_service.poll_device_flow(current_user.id, data.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OAuthDevicePollResponse(**result)


@router.delete("/xai", response_model=ProviderSettingsResponse)
def disconnect_xai_oauth(current_user: UserResponse = Depends(get_current_user)):
    xai_oauth_service.clear_oauth_tokens(current_user.id)
    return provider_settings_service.get_provider_settings(current_user.id, "xai-oauth")