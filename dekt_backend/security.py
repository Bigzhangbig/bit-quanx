from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request

from .settings import settings

_NONCE_CACHE: dict[str, int] = {}


def _purge_expired_nonce(now: int) -> None:
    expired = [key for key, exp in _NONCE_CACHE.items() if exp < now]
    for key in expired:
        _NONCE_CACHE.pop(key, None)


def hash_body_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def build_sign_message(
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    body_sha256: str,
) -> str:
    return f"{timestamp}.{nonce}.{method.upper()}.{path}.{body_sha256}"


def compute_signature(api_key: str, message: str) -> str:
    return hmac.new(api_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def build_signed_headers(
    api_key: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    now_ts: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    ts = int(now_ts or time.time())
    n = nonce or f"{ts}-local"
    payload = b""
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    message = build_sign_message(str(ts), n, method, path, hash_body_bytes(payload))
    sig = compute_signature(api_key, message)
    return {
        "X-API-Key": api_key,
        "X-Timestamp": str(ts),
        "X-Nonce": n,
        "X-Signature": sig,
    }


async def verify_signed_request(request: Request) -> None:
    path = request.url.path
    if path == "/health":
        return

    api_key = request.headers.get("X-API-Key", "")
    timestamp = request.headers.get("X-Timestamp", "")
    nonce = request.headers.get("X-Nonce", "")
    signature = request.headers.get("X-Signature", "")

    if not api_key or not timestamp or not nonce or not signature:
        raise HTTPException(status_code=401, detail="missing_auth_headers")

    if settings.api_key == "change-me":
        raise HTTPException(status_code=500, detail="server_api_key_not_configured")

    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid_api_key")

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid_timestamp") from exc

    now_ts = int(time.time())
    if abs(now_ts - ts) > settings.request_ttl_seconds:
        raise HTTPException(status_code=401, detail="timestamp_expired")

    _purge_expired_nonce(now_ts)
    if nonce in _NONCE_CACHE:
        raise HTTPException(status_code=401, detail="replay_detected")

    body = await request.body()
    body_sha256 = hash_body_bytes(body)
    message = build_sign_message(timestamp, nonce, request.method, path, body_sha256)
    expected = compute_signature(settings.api_key, message)

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid_signature")

    _NONCE_CACHE[nonce] = now_ts + settings.nonce_ttl_seconds
