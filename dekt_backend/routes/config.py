from __future__ import annotations

from fastapi import APIRouter

from ..models import ApiResponse, ConfigUpdateRequest
from ..storage import load_backend_config, save_backend_config

router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _public_config(cfg) -> dict:
    return {
        "has_token": bool(cfg.token),
        "gist_id": cfg.gist_id,
        "gist_filename": cfg.gist_filename,
        "tls_insecure": cfg.tls_insecure,
        "whitelist_category_ids": cfg.whitelist_category_ids or [],
        "whitelist_grade": cfg.whitelist_grade or [],
        "whitelist_academy": cfg.whitelist_academy or [],
    }


@router.get("")
def get_config() -> dict:
    cfg = load_backend_config()
    return {"ok": True, "data": _public_config(cfg)}


@router.put("", response_model=ApiResponse)
def update_config(payload: ConfigUpdateRequest) -> ApiResponse:
    cfg = load_backend_config()

    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(cfg, key, value)

    save_backend_config(cfg)
    return ApiResponse(ok=True, message="config_saved")
