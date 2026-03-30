from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("DEKT_BACKEND_HOST", "0.0.0.0")
    port: int = int(os.getenv("DEKT_BACKEND_PORT", "8000"))
    api_key: str = os.getenv("DEKT_BACKEND_API_KEY", "change-me")
    request_ttl_seconds: int = int(os.getenv("DEKT_BACKEND_REQUEST_TTL", "300"))
    nonce_ttl_seconds: int = int(os.getenv("DEKT_BACKEND_NONCE_TTL", "600"))


settings = Settings()
