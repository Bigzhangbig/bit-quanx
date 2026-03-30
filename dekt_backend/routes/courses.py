from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dekt_gui_app.dekt_gui.api_client import (
    DEFAULT_TEMPLATE_ID,
    apply_course,
    cancel_course,
    get_checkin_info,
    get_course_detail,
    get_user_id,
    list_courses,
    list_my_courses,
    submit_sign_action,
)

from ..filtering import matches_whitelist
from ..models import SignActionRequest
from ..storage import load_backend_config

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])

CATEGORY_IDS = [1, 2, 3, 4, 5, 6]


def _parse_category_ids(raw: str | None) -> list[int]:
    if not raw:
        return list(CATEGORY_IDS)
    out: list[int] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            cid = int(text)
        except ValueError:
            continue
        if cid in CATEGORY_IDS and cid not in out:
            out.append(cid)
    return out or list(CATEGORY_IDS)


def _get_runtime_token() -> tuple[str, bool]:
    cfg = load_backend_config()
    return cfg.token, cfg.tls_insecure


@router.get("/list")
def list_courses_endpoint(
    sign_status: int = Query(default=1, ge=1, le=3),
    limit: int = Query(default=20, ge=1, le=100),
    category_ids: str | None = Query(default=None),
) -> dict[str, Any]:
    cfg = load_backend_config()
    if not cfg.token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    requested_ids = _parse_category_ids(category_ids)
    if cfg.whitelist_category_ids:
        allowed = {int(x) for x in cfg.whitelist_category_ids}
        requested_ids = [cid for cid in requested_ids if cid in allowed]

    aggregated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for cid in requested_ids:
        ok, msg, items = list_courses(
            token=cfg.token,
            sign_status=sign_status,
            transcript_index_id=cid,
            limit=limit,
            timeout=15.0,
            insecure_tls=cfg.tls_insecure,
        )
        if not ok:
            errors.append({"category_id": cid, "message": msg})
            continue

        for course in items:
            if not matches_whitelist(
                course=course,
                grade_whitelist=cfg.whitelist_grade or [],
                academy_whitelist=cfg.whitelist_academy or [],
            ):
                continue
            merged = dict(course)
            merged["__category_id"] = cid
            aggregated.append(merged)

    return {
        "ok": True,
        "message": "ok",
        "data": aggregated,
        "meta": {
            "count": len(aggregated),
            "requested_categories": requested_ids,
            "errors": errors,
        },
    }


@router.get("/my")
def list_my_courses_endpoint(
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok, msg, items = list_my_courses(
        token=token,
        limit=limit,
        timeout=15.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "ok": True,
        "message": "ok",
        "data": items,
        "meta": {
            "count": len(items),
            "limit": limit,
        },
    }


@router.get("/{course_id}/detail")
def get_course_detail_endpoint(course_id: int) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok, msg, data = get_course_detail(
        token=token,
        course_id=course_id,
        timeout=12.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": "ok", "data": data}


@router.post("/{course_id}/apply")
def apply_course_endpoint(course_id: int) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok, msg = apply_course(
        token=token,
        course_id=course_id,
        template_id=DEFAULT_TEMPLATE_ID,
        timeout=12.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg}


@router.post("/{course_id}/cancel")
def cancel_course_endpoint(course_id: int) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok_uid, user_id, uid_msg = get_user_id(token=token, timeout=12.0, insecure_tls=insecure_tls)
    if not ok_uid:
        raise HTTPException(status_code=400, detail=uid_msg)

    ok, msg = cancel_course(
        token=token,
        course_id=course_id,
        user_id=int(user_id),
        timeout=12.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg}


@router.get("/{course_id}/checkin-info")
def get_checkin_info_endpoint(course_id: int) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok, msg, info = get_checkin_info(
        token=token,
        course_id=course_id,
        timeout=12.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg, "data": info}


@router.post("/{course_id}/sign-in")
def sign_in_endpoint(course_id: int, payload: SignActionRequest) -> dict[str, Any]:
    token, insecure_tls = _get_runtime_token()
    if not token:
        raise HTTPException(status_code=400, detail="backend_token_not_configured")

    ok, msg = submit_sign_action(
        token=token,
        course_id=course_id,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timeout=12.0,
        insecure_tls=insecure_tls,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg}


@router.post("/{course_id}/sign-out")
def sign_out_endpoint(course_id: int, payload: SignActionRequest) -> dict[str, Any]:
    # The DEKT endpoint identifies sign-out by path and payload content.
    return sign_in_endpoint(course_id, payload)
