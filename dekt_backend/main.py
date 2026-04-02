from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .runtime import runtime
from .routes import auth, config, courses, runtime as runtime_routes
from .security import verify_signed_request



@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(title="DEKT 后端服务", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    try:
        await verify_signed_request(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": str(exc.detail)})
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"ok": False, "error": "internal_auth_error"})
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "message": "服务正常"}


app.include_router(auth.router)
app.include_router(config.router)
app.include_router(courses.router)
app.include_router(runtime_routes.router)
