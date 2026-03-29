from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

APP_DIR = Path.home() / ".dekt_gui"
CONFIG_FILE = APP_DIR / "config.json"
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass
class AppConfig:
    token: str = ""
    github_token: str = ""
    gist_id: str = ""
    gist_filename: str = "bit_cookies.json"
    tencent_map_key: str = ""
    tls_insecure: bool = False
    signup_queue_text: str = ""


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _bool_from_str(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_signup_queue_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""

    if text.startswith("["):
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                ids: list[str] = []
                for item in obj:
                    if isinstance(item, dict):
                        cid = item.get("id")
                    else:
                        cid = item
                    if cid is None:
                        continue
                    s = str(cid).strip()
                    if s.isdigit():
                        ids.append(s)
                return "\n".join(ids)
        except (ValueError, TypeError):
            return text
    return text


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    ensure_app_dir()
    env = _parse_dotenv_file(PROJECT_ENV_FILE)

    cfg = AppConfig(
        token=str(env.get("bit_sc_token", "")),
        github_token=str(env.get("bit_sc_github_token", "")),
        gist_id=str(env.get("bit_sc_gist_id", "")),
        gist_filename=str(env.get("bit_sc_gist_filename", "bit_cookies.json")) or "bit_cookies.json",
        tencent_map_key=str(env.get("bit_sc_tencent_map_key", "")),
        tls_insecure=_bool_from_str(env.get("bit_sc_tls_insecure", "false")),
        signup_queue_text=_normalize_signup_queue_text(env.get("bit_sc_signup_list", "")),
    )

    if not CONFIG_FILE.exists():
        return cfg

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cfg

    # Stored GUI config overrides .env defaults when present.
    cfg.token = str(data.get("token", cfg.token))
    cfg.github_token = str(data.get("github_token", cfg.github_token))
    cfg.gist_id = str(data.get("gist_id", cfg.gist_id))
    cfg.gist_filename = str(data.get("gist_filename", cfg.gist_filename)) or "bit_cookies.json"
    cfg.tencent_map_key = str(data.get("tencent_map_key", cfg.tencent_map_key))
    cfg.tls_insecure = bool(data.get("tls_insecure", cfg.tls_insecure))
    cfg.signup_queue_text = str(data.get("signup_queue_text", cfg.signup_queue_text))
    return cfg


def save_config(cfg: AppConfig) -> None:
    ensure_app_dir()
    CONFIG_FILE.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
