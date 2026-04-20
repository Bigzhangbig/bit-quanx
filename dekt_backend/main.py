from __future__ import annotations

import os
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from .runtime import runtime
from .settings import settings
from .storage import load_backend_config

dekt_gui_path = Path(__file__).parent.parent / "dekt_gui_app"
if str(dekt_gui_path) not in sys.path:
    sys.path.insert(0, str(dekt_gui_path))

try:
    from dekt_gui.api_client import list_courses, list_my_courses, normalize_bearer_token
    from dekt_gui.calendar_utils import parse_event_from_list_courses, parse_event_from_list_my_courses
    from dekt_gui.ics_exporter import export_events_to_ics

    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

WEB_KEY_COOKIE_NAME = "dekt_backend_web_key"


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
        .wrap {{ max-width: 980px; margin: 36px auto; padding: 0 16px; }}
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
        .nav {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); font-size: 12px; }}
        input, select {{ padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
        @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class=\"wrap\">{body}</div>
</body>
</html>"""


def _nav() -> str:
    return """
<section class=\"card\" style=\"padding: 14px;\">
    <div class=\"nav\">
        <a href=\"/\">首页</a>
        <a href=\"/runtime\">运行状态</a>
        <a href=\"/calendar\">日历</a>
        <a href=\"/health\">健康检查</a>
        <form method=\"post\" action=\"/auth/logout\" style=\"margin: 0;\">
            <button type=\"submit\">退出登录</button>
        </form>
    </div>
</section>
"""


def _get_web_access_key() -> str:
    return (os.getenv("DEKT_BACKEND_WEB_KEY") or settings.api_key or "").strip()


def _extract_access_key(request: Request) -> str:
    cookie_key = (request.cookies.get(WEB_KEY_COOKIE_NAME) or "").strip()
    if cookie_key:
        return cookie_key
    header_key = (request.headers.get("x-dekt-key") or "").strip()
    if header_key:
        return header_key
    return (request.query_params.get("key") or "").strip()


def _is_authorized(request: Request) -> bool:
    expected = _get_web_access_key()
    if not expected:
        return True
    provided = _extract_access_key(request)
    if not provided:
        return False
    return secrets.compare_digest(expected, provided)


def _unauthorized_page(message: str = "需要访问密钥") -> HTMLResponse:
    body = f"""
<section class=\"card\">
    <h1>访问受限</h1>
    <p>{message}</p>
    <div class=\"actions\" style=\"margin-top: 12px;\">
        <a href=\"/auth\">去登录</a>
    </div>
</section>
"""
    return HTMLResponse(_render_page("访问受限", body), status_code=401)


def _require_page_auth(request: Request) -> HTMLResponse | None:
    if _is_authorized(request):
        return None
    return _unauthorized_page()


def _require_api_auth(request: Request) -> JSONResponse | None:
    if _is_authorized(request):
        return None
    return JSONResponse({"error": "Unauthorized"}, status_code=401)


@app.get("/auth", response_class=HTMLResponse)
def auth_page() -> HTMLResponse:
    body = """
<section class=\"card\">
    <h1>DEKT 后端登录</h1>
    <p>请输入自定义访问密钥后进入网页。</p>
    <form method=\"post\" action=\"/auth/login\" style=\"margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap;\">
        <input name=\"key\" type=\"password\" placeholder=\"请输入访问密钥\" />
        <button type=\"submit\">登录</button>
    </form>
</section>
"""
    return HTMLResponse(_render_page("登录", body))


@app.post("/auth/login")
async def auth_login(request: Request) -> Response:
    form = await request.form()
    provided = str(form.get("key") or "").strip()
    expected = _get_web_access_key()
    if expected and not secrets.compare_digest(expected, provided):
        return _unauthorized_page("密钥不正确，请重试")

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=WEB_KEY_COOKIE_NAME,
        value=provided,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/auth/logout")
def auth_logout() -> RedirectResponse:
    response = RedirectResponse(url="/auth", status_code=303)
    response.delete_cookie(WEB_KEY_COOKIE_NAME)
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    unauthorized = _require_page_auth(request)
    if unauthorized:
        return unauthorized

    cfg = load_backend_config()
    token_state = "已配置" if (cfg.token or "").strip() else "未配置"
    snapshot = runtime.snapshot()

    body = f"""
{_nav()}
<section class=\"card\">
    <h1>DEKT 控制台</h1>
    <p>网页结构与桌面 app 对齐：概览、运行态、活动日历。</p>
    <div class=\"meta\">Runtime 开关：<code>{settings.runtime_enabled}</code> | Token：<code>{token_state}</code></div>
</section>
<section class=\"card\">
    <h2>概览</h2>
    <div class=\"grid\">
        <div><div class=\"tag\">运行线程</div><p style=\"margin-top:8px;\">当前状态：<code>{snapshot.get("running")}</code></p></div>
        <div><div class=\"tag\">最后执行</div><p style=\"margin-top:8px;\">{_fmt_ts(snapshot.get("last_finished_at"))}</p></div>
        <div><div class=\"tag\">已开始活动</div><p style=\"margin-top:8px;\">{(snapshot.get("last_run_summary") or {}).get("started_count", "-")}</p></div>
        <div><div class=\"tag\">我的活动</div><p style=\"margin-top:8px;\">{(snapshot.get("last_run_summary") or {}).get("my_courses_count", "-")}</p></div>
    </div>
    <div class=\"actions\" style=\"margin-top:12px;\"><a href=\"/runtime\">进入运行状态</a><a href=\"/calendar\">进入活动日历</a></div>
</section>
"""
    return HTMLResponse(_render_page("DEKT 后端网页服务", body))


@app.get("/health", response_class=HTMLResponse)
def health(request: Request) -> HTMLResponse:
    unauthorized = _require_page_auth(request)
    if unauthorized:
        return unauthorized
    body = f"""{_nav()}<section class=\"card\"><h1>服务健康状态</h1><p>服务正常运行。</p></section>"""
    return HTMLResponse(_render_page("健康检查", body))


@app.get("/runtime", response_class=HTMLResponse)
def runtime_status(request: Request) -> HTMLResponse:
    unauthorized = _require_page_auth(request)
    if unauthorized:
        return unauthorized

    snapshot = runtime.snapshot()
    summary = snapshot.get("last_run_summary") or {}
    err = str(snapshot.get("last_error") or "-")
    body = f"""
{_nav()}
<section class=\"card\">
    <h1>运行状态</h1>
    <p>查看后台轮询状态，并支持手动触发一次运行（与 app 运行面板一致）。</p>
    <ul>
        <li>enabled: <code>{snapshot.get("enabled")}</code></li>
        <li>running: <code>{snapshot.get("running")}</code></li>
        <li>last_started_at: <code>{_fmt_ts(snapshot.get("last_started_at"))}</code></li>
        <li>last_finished_at: <code>{_fmt_ts(snapshot.get("last_finished_at"))}</code></li>
        <li>last_duration_seconds: <code>{snapshot.get("last_duration_seconds")}</code></li>
        <li>last_error: <code>{err}</code></li>
        <li>last_run_summary: <code>{summary}</code></li>
    </ul>
    <div class=\"actions\" style=\"margin-top:12px;\"><form method=\"post\" action=\"/runtime/run-now\"><button type=\"submit\">手动触发一次轮询</button></form></div>
</section>
"""
    return HTMLResponse(_render_page("运行状态", body))


@app.post("/runtime/run-now")
def runtime_run_now(request: Request) -> Response:
    unauthorized = _require_page_auth(request)
    if unauthorized:
        return unauthorized
    runtime.run_once()
    return RedirectResponse(url="/runtime", status_code=303)


@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request) -> HTMLResponse:
    unauthorized = _require_page_auth(request)
    if unauthorized:
        return unauthorized

    if not CALENDAR_AVAILABLE:
        body = """<section class=\"card\"><h1>日历功能不可用</h1><p>日历模块加载失败，请检查依赖。</p><div class=\"actions\"><a href=\"/\">返回首页</a></div></section>"""
        return HTMLResponse(_render_page("日历", body))

    body = f"""
{_nav()}
<section class=\"card\"><h1>DEKT 日历</h1><p>读取后端配置的 Token，显示已报名或全部活动的日历视图。</p></section>
<section class=\"card\">
  <div style=\"margin-bottom:15px;display:flex;gap:10px;align-items:center;\">
    <label>筛选: <select id=\"filterMode\"><option value=\"mine\">已报名</option><option value=\"all\">全部</option></select></label>
    <button onclick=\"loadCalendar()\">加载日历</button>
    <button onclick=\"exportICS()\">导出 ICS</button>
  </div>
  <div id=\"calendar\" style=\"height:600px;\"></div>
</section>
<div id=\"eventDetail\" style=\"display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;border:1px solid #e5e7eb;border-radius:10px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2);z-index:1000;max-width:500px;max-height:70vh;overflow-y:auto;\"><h3 id=\"eventTitle\"></h3><div id=\"eventContent\"></div><button onclick=\"closeEventDetail()\" style=\"margin-top:15px;\">关闭</button></div>
<script src=\"https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js\"></script>
<link href=\"https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css\" rel=\"stylesheet\" />
<script>
let calendar = null;
let allEvents = [];
function loadCalendar() {{
  const filterMode = document.getElementById('filterMode').value;
  fetch('/calendar/events', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{filter_mode:filterMode}})}})
    .then(r => {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
    .then(data => {{ allEvents = data; initCalendar(data); }})
    .catch(err => alert('加载失败: ' + err.message));
}}
function initCalendar(events) {{
  const calendarEl = document.getElementById('calendar');
  if (calendar) calendar.remove();
  calendar = new FullCalendar.Calendar(calendarEl, {{
    initialView:'dayGridMonth',
    headerToolbar:{{left:'prev,next today',center:'title',right:'dayGridMonth,listMonth'}},
    locale:'zh-cn',
    events:events,
    eventClick:function(info){{ showEventDetail(info.event.extendedProps); }}
  }});
  calendar.render();
}}
function showEventDetail(event) {{
  document.getElementById('eventTitle').textContent = event.title;
  let content = '<table style=\"width:100%;\">';
  if (event.start) content += `<tr><td><b>开始:</b></td><td>${{event.start}}</td></tr>`;
  if (event.end) content += `<tr><td><b>结束:</b></td><td>${{event.end}}</td></tr>`;
  if (event.location) content += `<tr><td><b>地点:</b></td><td>${{event.location}}</td></tr>`;
  if (event.category) content += `<tr><td><b>类别:</b></td><td>${{event.category}}</td></tr>`;
  content += '</table>';
  document.getElementById('eventContent').innerHTML = content;
  document.getElementById('eventDetail').style.display = 'block';
}}
function closeEventDetail() {{ document.getElementById('eventDetail').style.display = 'none'; }}
function exportICS() {{
  if (!allEvents.length) {{ alert('没有活动可导出'); return; }}
  const eventIds = allEvents.map(e => e.id);
  fetch('/calendar/ics', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{event_ids:eventIds}})}})
    .then(r => {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); }})
    .then(blob => {{
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'calendar.ics'; a.click(); URL.revokeObjectURL(url);
    }})
    .catch(err => alert('导出失败: ' + err.message));
}}
</script>
"""
    return HTMLResponse(_render_page("日历", body))


@app.post("/calendar/events")
async def calendar_events(request: Request) -> JSONResponse:
    unauthorized = _require_api_auth(request)
    if unauthorized:
        return unauthorized
    if not CALENDAR_AVAILABLE:
        return JSONResponse({"error": "Calendar module not available"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    cfg = load_backend_config()
    token = normalize_bearer_token(cfg.token or "")
    if not token:
        return JSONResponse({"error": "Backend token not configured"}, status_code=400)

    filter_mode = body.get("filter_mode", "mine")
    try:
        ok1, msg1, my_courses = list_my_courses(token=token, limit=200, timeout=15.0, insecure_tls=cfg.tls_insecure)
        if not ok1:
            return JSONResponse({"error": f"Failed to load my courses: {msg1}"}, status_code=400)

        my_events = parse_event_from_list_my_courses(my_courses)
        all_events = my_events.copy()

        if filter_mode == "all":
            from dekt_gui.constants import CATEGORIES
            for cid, _ in CATEGORIES:
                ok2, _msg2, courses = list_courses(
                    token=token,
                    sign_status=2,
                    transcript_index_id=cid,
                    limit=20,
                    timeout=15.0,
                    insecure_tls=cfg.tls_insecure,
                )
                if ok2:
                    unrolled_events = parse_event_from_list_courses(courses)
                    my_ids = {e.id for e in my_events}
                    for event in unrolled_events:
                        if event.id not in my_ids:
                            all_events.append(event)

        payload: list[dict[str, Any]] = []
        for event in all_events:
            if not event.start_time:
                continue
            payload.append(
                {
                    "id": str(event.id),
                    "title": event.title,
                    "start": event.start_time.isoformat(),
                    "end": event.end_time.isoformat() if event.end_time else None,
                    "extendedProps": {
                        "id": event.id,
                        "title": event.title,
                        "location": event.location,
                        "category": event.category,
                        "start": event.start_time.strftime("%Y-%m-%d %H:%M") if event.start_time else "",
                        "end": event.end_time.strftime("%Y-%m-%d %H:%M") if event.end_time else "",
                        "is_enrolled": event.is_enrolled,
                    },
                }
            )
        return JSONResponse(payload)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/calendar/events")
async def calendar_events_legacy(request: Request) -> JSONResponse:
    return await calendar_events(request)


@app.post("/calendar/ics")
async def calendar_ics(request: Request) -> Response:
    unauthorized = _require_api_auth(request)
    if unauthorized:
        return unauthorized
    if not CALENDAR_AVAILABLE:
        return JSONResponse({"error": "Calendar module not available"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    cfg = load_backend_config()
    token = normalize_bearer_token(cfg.token or "")
    if not token:
        return JSONResponse({"error": "Backend token not configured"}, status_code=400)

    event_ids = body.get("event_ids", [])
    try:
        ok, msg, my_courses = list_my_courses(token=token, limit=200, timeout=15.0, insecure_tls=cfg.tls_insecure)
        if not ok:
            return JSONResponse({"error": f"Failed to load courses: {msg}"}, status_code=400)

        my_events = parse_event_from_list_my_courses(my_courses)
        selected_ids = {int(item) for item in event_ids if str(item).strip().isdigit()}
        filtered_events = [e for e in my_events if e.id in selected_ids]
        if not filtered_events:
            return JSONResponse({"error": "No events to export"}, status_code=400)

        ics_content = export_events_to_ics(filtered_events, "DEKT活动日历")
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ics", delete=False, encoding="utf-8") as temp:
            temp.write(ics_content)
            temp_path = temp.name

        return FileResponse(temp_path, media_type="text/calendar", filename="calendar.ics")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/calendar/ics")
async def calendar_ics_legacy(request: Request) -> Response:
    return await calendar_ics(request)
