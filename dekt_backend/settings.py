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
    runtime_enabled: bool = os.getenv("DEKT_BACKEND_RUNTIME_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    runtime_interval_seconds: int = int(os.getenv("DEKT_BACKEND_RUNTIME_INTERVAL_SECONDS", "300"))
    runtime_initial_delay_seconds: int = int(os.getenv("DEKT_BACKEND_RUNTIME_INITIAL_DELAY_SECONDS", "0"))
    runtime_fetch_delay_max_seconds: int = int(os.getenv("DEKT_BACKEND_RUNTIME_FETCH_DELAY_MAX_SECONDS", "3"))


settings = Settings()
