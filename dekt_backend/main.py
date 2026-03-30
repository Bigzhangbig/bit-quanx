from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routes import auth, config, courses
from .security import verify_signed_request

app = FastAPI(title="DEKT Backend", version="0.1.0")


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    try:
        await verify_signed_request(request)
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "status_code") and hasattr(exc, "detail"):
            return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
        return JSONResponse(status_code=500, content={"ok": False, "error": "internal_auth_error"})
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "message": "alive"}


app.include_router(auth.router)
app.include_router(config.router)
app.include_router(courses.router)
