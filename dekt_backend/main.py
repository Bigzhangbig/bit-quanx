from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from .runtime import runtime
from .settings import settings
from .storage import load_backend_config



@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(title="DEKT 后端服务", version="0.1.0", lifespan=lifespan)


def _fmt_ts(value: float | None) -> str:
        if value is None:
                return "-"
        try:
                return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError):
                return "-"


def _render_page(title: str, body: str) -> str:
        return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title}</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f6f8fb;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --accent: #0f766e;
            --border: #e5e7eb;
        }}
        body {{
            margin: 0;
            background: radial-gradient(circle at 20% 0%, #e0f2fe, var(--bg));
            font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            color: var(--text);
        }}
        .wrap {{
            max-width: 880px;
            margin: 36px auto;
            padding: 0 16px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            margin-bottom: 14px;
        }}
        h1 {{ margin: 0 0 8px; font-size: 24px; }}
        h2 {{ margin: 0 0 12px; font-size: 18px; }}
        p {{ margin: 0; color: var(--muted); }}
        ul {{ margin: 8px 0 0; padding-left: 18px; }}
        li {{ margin: 6px 0; }}
        a, button {{
            color: #fff;
            background: var(--accent);
            border: 0;
            border-radius: 10px;
            padding: 8px 12px;
            text-decoration: none;
            cursor: pointer;
            font-size: 14px;
        }}
        .actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .meta {{ color: var(--muted); font-size: 13px; margin-top: 10px; }}
        code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
    </style>
</head>
<body>
    <div class=\"wrap\">{body}</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
        cfg = load_backend_config()
        token_state = "已配置" if (cfg.token or "").strip() else "未配置"
        body = f"""
<section class=\"card\">
    <h1>DEKT 后端网页服务</h1>
    <p>当前后端仅提供网页页面，不再提供 API 接口。</p>
    <div class=\"meta\">Runtime 开关：<code>{settings.runtime_enabled}</code> | Token：<code>{token_state}</code></div>
</section>
<section class=\"card\">
    <h2>功能入口</h2>
    <div class=\"actions\">
        <a href=\"/health\">健康检查页面</a>
        <a href=\"/runtime\">运行状态页面</a>
    </div>
    <ul>
        <li>保留后台轮询能力（当 <code>DEKT_BACKEND_RUNTIME_ENABLED=true</code> 时）。</li>
        <li>移除签名鉴权 API 与 <code>/api/v1/*</code> 路由。</li>
    </ul>
</section>
"""
        return HTMLResponse(_render_page("DEKT 后端网页服务", body))


@app.get("/health", response_class=HTMLResponse)
def health() -> HTMLResponse:
        body = """
<section class=\"card\">
    <h1>服务健康状态</h1>
    <p>服务正常运行。</p>
    <div class=\"actions\" style=\"margin-top:12px;\">
        <a href=\"/\">返回首页</a>
        <a href=\"/runtime\">查看运行状态</a>
    </div>
</section>
"""
        return HTMLResponse(_render_page("健康检查", body))


@app.get("/runtime", response_class=HTMLResponse)
def runtime_status() -> HTMLResponse:
        snapshot = runtime.snapshot()
        summary = snapshot.get("last_run_summary") or {}
        err = str(snapshot.get("last_error") or "-")
        body = f"""
<section class=\"card\">
    <h1>运行状态</h1>
    <p>查看后台轮询状态，并支持手动触发一次运行。</p>
    <ul>
        <li>enabled: <code>{snapshot.get("enabled")}</code></li>
        <li>running: <code>{snapshot.get("running")}</code></li>
        <li>last_started_at: <code>{_fmt_ts(snapshot.get("last_started_at"))}</code></li>
        <li>last_finished_at: <code>{_fmt_ts(snapshot.get("last_finished_at"))}</code></li>
        <li>last_duration_seconds: <code>{snapshot.get("last_duration_seconds")}</code></li>
        <li>last_error: <code>{err}</code></li>
        <li>last_run_summary: <code>{summary}</code></li>
    </ul>
    <div class=\"actions\" style=\"margin-top:12px;\">
        <form method=\"post\" action=\"/runtime/run-now\">
            <button type=\"submit\">手动触发一次轮询</button>
        </form>
        <a href=\"/\">返回首页</a>
    </div>
</section>
"""
        return HTMLResponse(_render_page("运行状态", body))


@app.post("/runtime/run-now")
def runtime_run_now() -> RedirectResponse:
        runtime.run_once()
        return RedirectResponse(url="/runtime", status_code=303)
