from __future__ import annotations

from fastapi import APIRouter

from ..runtime import runtime

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


@router.get("/status")
def get_runtime_status() -> dict:
    snapshot = runtime.snapshot()
    return {"ok": True, "data": snapshot}


@router.post("/run-now")
def run_runtime_now() -> dict:
    result = runtime.run_once()
    return {"ok": True, "data": result}
