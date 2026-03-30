from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dekt_gui_app.dekt_gui.api_client import normalize_bearer_token, verify_token

from ..models import ApiResponse, SetTokenRequest, VerifyTokenRequest
from ..storage import load_backend_config, save_backend_config

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/verify")
def verify_auth(payload: VerifyTokenRequest) -> dict:
    cfg = load_backend_config()
    token = payload.token.strip()
    if payload.use_stored:
        token = cfg.token

    if not token:
        raise HTTPException(status_code=400, detail="token_empty")

    result = verify_token(token=token, timeout=12.0, insecure_tls=cfg.tls_insecure)
    return {
        "ok": result.ok,
        "message": result.message,
        "user_id": result.user_id,
    }


@router.post("/set-token", response_model=ApiResponse)
def set_token(payload: SetTokenRequest) -> ApiResponse:
    cfg = load_backend_config()
    cfg.token = normalize_bearer_token(payload.token)
    save_backend_config(cfg)
    return ApiResponse(ok=True, message="token_saved")
