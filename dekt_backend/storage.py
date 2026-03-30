from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import threading

APP_DIR = Path.home() / ".dekt_backend"
CONFIG_FILE = APP_DIR / "config.json"


@dataclass
class BackendConfig:
    token: str = ""
    github_token: str = ""
    gist_id: str = ""
    gist_filename: str = "bit_cookies.json"
    tencent_map_key: str = ""
    tls_insecure: bool = True
    whitelist_category_ids: list[int] | None = None
    whitelist_grade: list[str] | None = None
    whitelist_academy: list[str] | None = None


_LOCK = threading.Lock()


def _normalize_int_list(raw: list[int] | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value not in out:
            out.append(value)
    return out


def _normalize_str_list(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        if text not in out:
            out.append(text)
    return out


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_backend_config() -> BackendConfig:
    ensure_app_dir()
    if not CONFIG_FILE.exists():
        return BackendConfig()

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return BackendConfig()

    cfg = BackendConfig(
        token=str(raw.get("token", "")),
        github_token=str(raw.get("github_token", "")),
        gist_id=str(raw.get("gist_id", "")),
        gist_filename=str(raw.get("gist_filename", "bit_cookies.json")) or "bit_cookies.json",
        tencent_map_key=str(raw.get("tencent_map_key", "")),
        tls_insecure=bool(raw.get("tls_insecure", True)),
        whitelist_category_ids=_normalize_int_list(raw.get("whitelist_category_ids")),
        whitelist_grade=_normalize_str_list(raw.get("whitelist_grade")),
        whitelist_academy=_normalize_str_list(raw.get("whitelist_academy")),
    )
    return cfg


def save_backend_config(cfg: BackendConfig) -> None:
    ensure_app_dir()
    payload = asdict(cfg)
    payload["whitelist_category_ids"] = _normalize_int_list(cfg.whitelist_category_ids)
    payload["whitelist_grade"] = _normalize_str_list(cfg.whitelist_grade)
    payload["whitelist_academy"] = _normalize_str_list(cfg.whitelist_academy)

    with _LOCK:
        CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
