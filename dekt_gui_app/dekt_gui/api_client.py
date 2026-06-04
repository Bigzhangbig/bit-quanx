from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import os
import io
import json
import time
from typing import Any

import httpx


DEKT_HOST = "https://qcbldekt.bit.edu.cn"
GITHUB_API = "https://api.github.com"


@dataclass
class VerifyResult:
    ok: bool
    message: str
    user_id: str = ""


DEFAULT_TEMPLATE_ID = "2GNFjVv2S7xYnoWeIxGsJGP1Fu2zSs28R6mZI7Fc2kU"


def _create_client(timeout: float, insecure_tls: bool = False) -> httpx.Client:
    verify: bool | str = False if insecure_tls else True
    return httpx.Client(timeout=timeout, follow_redirects=True, verify=verify)


def normalize_bearer_token(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw
    return f"Bearer {raw}"


def _api_request(
    method: str,
    path: str,
    token: str = "",
    *,
    timeout: float = 12.0,
    insecure_tls: bool = False,
    json_body: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """通用 DEKT API 请求。返回 (ok, message, response_body)。

    response_body 是完整的 JSON 响应（包含 code, data, message 等字段）。
    调用方负责从 data 中提取具体数据。错误时 response_body 为空 dict。
    """
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", {}

    url = f"{DEKT_HOST}{path}"
    if query_params:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items() if v is not None)
        if qs:
            url += ("&" if "?" in url else "?") + qs

    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.request(method, url, headers=headers, json=json_body)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}", {}

    if resp.status_code == 401:
        return False, "Unauthorized (401)", {}
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}", {}

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response", {}

    return True, "OK", body


def verify_token(token: str, timeout: float = 12.0, insecure_tls: bool = False) -> VerifyResult:
    auth = normalize_bearer_token(token)
    if not auth:
        return VerifyResult(ok=False, message="Token is empty")

    headers = {"Authorization": auth}
    url = f"{DEKT_HOST}/api/user/info"

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(ok=False, message=f"Request failed: {exc}")

    if resp.status_code == 401:
        return VerifyResult(ok=False, message="Unauthorized (401)")

    if resp.status_code < 200 or resp.status_code >= 300:
        return VerifyResult(ok=False, message=f"HTTP {resp.status_code}")

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return VerifyResult(ok=False, message="Invalid JSON response")

    if body.get("code") == 200 and isinstance(body.get("data"), dict):
        user_id = str(body["data"].get("id", ""))
        return VerifyResult(ok=True, message="Token is valid", user_id=user_id)

    msg = str(body.get("message") or body.get("msg") or "Unknown API response")
    return VerifyResult(ok=False, message=msg)


def fetch_token_from_gist(
    github_token: str,
    gist_id: str,
    gist_filename: str,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, str]:
    """Return (ok, token_or_empty, message)."""
    gt = (github_token or "").strip()
    gid = (gist_id or "").strip()
    gfile = (gist_filename or "bit_cookies.json").strip() or "bit_cookies.json"

    if not gt or not gid:
        return False, "", "Missing GitHub token or Gist ID"

    headers = {
        "Authorization": f"token {gt}",
        "User-Agent": "DEKT-GUI",
        "Accept": "application/vnd.github+json",
    }

    url = f"{GITHUB_API}/gists/{gid}"

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, "", f"Gist request failed: {exc}"

    if resp.status_code < 200 or resp.status_code >= 300:
        return False, "", f"Gist HTTP {resp.status_code}"

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "", "Gist response is not valid JSON"

    files = body.get("files")
    if not isinstance(files, dict) or gfile not in files:
        return False, "", f"Gist file not found: {gfile}"

    file_obj = files[gfile]
    if not isinstance(file_obj, dict):
        return False, "", "Invalid Gist file structure"

    content = file_obj.get("content")
    if not isinstance(content, str):
        return False, "", "Gist file has no textual content"

    try:
        inner: dict[str, Any] = json.loads(content)
    except ValueError:
        return False, "", "Gist file content is not JSON"

    token = str(inner.get("token", "")).strip()
    if not token:
        return False, "", "Token field is missing in Gist file"

    return True, normalize_bearer_token(token), "Loaded token from Gist"


def list_courses(
    token: str,
    sign_status: int,
    transcript_index_id: int,
    limit: int = 20,
    timeout: float = 15.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, list[dict[str, Any]]]:
    path = (
        f"/api/course/list?page=1&limit={int(limit)}"
        f"&sign_status={int(sign_status)}"
        f"&transcript_index_id={int(transcript_index_id)}"
        "&transcript_index_type_id=0"
    )
    ok, msg, body = _api_request(
        "GET", path, token=token, timeout=timeout, insecure_tls=insecure_tls,
    )
    if not ok:
        return False, msg, []

    if body.get("code") != 200:
        return False, str(body.get("message") or body.get("msg") or "API error"), []

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", []

    items = data.get("items")
    if not isinstance(items, list):
        return True, "No items", []

    return True, "OK", [i for i in items if isinstance(i, dict)]


def get_course_detail(
    token: str,
    course_id: int,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    ok, msg, body = _api_request(
        "GET",
        f"/api/course/info/{int(course_id)}",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
    )
    if not ok:
        return False, msg, {}

    if body.get("code") != 200:
        return False, str(body.get("message") or body.get("msg") or "API error"), {}

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", {}

    return True, "OK", data


def apply_course(
    token: str,
    course_id: int,
    template_id: str = DEFAULT_TEMPLATE_ID,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str]:
    ok, msg, body = _api_request(
        "POST",
        "/api/course/apply",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
        json_body={
            "course_id": int(course_id),
            "template_id": template_id,
        },
    )
    if not ok:
        return False, msg

    resp_msg = str(body.get("message") or body.get("msg") or "")
    if body.get("code") == 200 or "成功" in resp_msg or "已报名" in resp_msg:
        return True, resp_msg or "报名成功"
    return False, resp_msg or "报名失败"


def run_signup_queue(
    token: str,
    course_ids: list[int],
    template_id: str = DEFAULT_TEMPLATE_ID,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, list[dict[str, str]]]:
    if not course_ids:
        return False, "Queue is empty", []

    results: list[dict[str, str]] = []
    for cid in course_ids:
        ok, msg = apply_course(
            token=token,
            course_id=cid,
            template_id=template_id,
            timeout=timeout,
            insecure_tls=insecure_tls,
        )
        results.append(
            {
                "course_id": str(cid),
                "ok": "true" if ok else "false",
                "message": msg,
            }
        )

    success_count = sum(1 for item in results if item["ok"] == "true")
    return True, f"Signup done: {success_count}/{len(results)} success", results


def get_user_id(
    token: str,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, str]:
    ok, msg, body = _api_request(
        "GET", "/api/user/info", token=token, timeout=timeout, insecure_tls=insecure_tls,
    )
    if not ok:
        return False, "", msg

    if body.get("code") != 200 or not isinstance(body.get("data"), dict):
        err_msg = str(body.get("message") or body.get("msg") or "API error")
        return False, "", err_msg

    user_id = str(body["data"].get("id", "")).strip()
    if not user_id:
        return False, "", "user_id not found"
    return True, user_id, "OK"


def list_my_course_ids(
    token: str,
    limit: int = 200,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, set[int]]:
    ok, msg, body = _api_request(
        "GET",
        f"/api/course/list/my?page=1&limit={int(limit)}",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
    )
    if not ok:
        return False, msg, set()

    if body.get("code") != 200:
        return False, str(body.get("message") or body.get("msg") or "API error"), set()

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", set()

    items = data.get("items")
    if not isinstance(items, list):
        return True, "No items", set()

    ids: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("course_id", item.get("id"))
        try:
            if raw_id is not None:
                ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return True, "OK", ids


def cancel_course(
    token: str,
    course_id: int,
    user_id: int,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str]:
    ok, msg, body = _api_request(
        "POST",
        "/api/course/cancelApply",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
        json_body={
            "course_id": int(course_id),
            "user_id": int(user_id),
        },
    )
    if not ok:
        return False, msg

    resp_msg = str(body.get("message") or body.get("msg") or "")
    if body.get("code") in (200, 0) or body.get("success") is True or "成功" in resp_msg:
        return True, resp_msg or "取消报名成功"
    return False, resp_msg or "取消报名失败"


def list_my_courses(
    token: str,
    limit: int = 200,
    timeout: float = 15.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, list[dict[str, Any]]]:
    ok, msg, body = _api_request(
        "GET",
        f"/api/course/list/my?page=1&limit={int(limit)}",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
    )
    if not ok:
        return False, msg, []

    if body.get("code") != 200:
        return False, str(body.get("message") or body.get("msg") or "API error"), []

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", []

    items = data.get("items")
    if not isinstance(items, list):
        return True, "No items", []
    return True, "OK", [i for i in items if isinstance(i, dict)]


def get_checkin_info(
    token: str,
    course_id: int,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    ok, msg, body = _api_request(
        "GET",
        f"/api/transcript/checkIn/info?course_id={int(course_id)}",
        token=token,
        timeout=timeout,
        insecure_tls=insecure_tls,
    )
    if not ok:
        return False, msg, {}

    if body.get("code") != 200:
        return False, str(body.get("message") or body.get("msg") or "API error"), {}

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", {}

    return True, "OK", data


def _generate_sign(timestamp_ms: int) -> str:
    """Generate sign header for DEKT API requests."""
    app_secret = os.environ.get("DEKT_APP_SECRET", "2GNFjVv2S7xYnoWe")
    sign_str = f"appCode=qcbldekt&timestamp={timestamp_ms}&appSecret={app_secret}&origin=wechat"
    return hashlib.md5(sign_str.encode()).hexdigest()


def submit_sign_action(
    token: str,
    course_id: int,
    address: str,
    latitude: float,
    longitude: float,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str]:
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty"

    url = f"{DEKT_HOST}/api/transcript/signIn"
    timestamp_ms = int(time.time() * 1000)
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
        "appCode": "qcbldekt",
        "timestamp": str(timestamp_ms),
        "sign": _generate_sign(timestamp_ms),
    }
    body = {
        "course_id": int(course_id),
        "sign_address": {
            "address": str(address or ""),
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.post(url, headers=headers, json=body)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}"

    if resp.status_code == 401:
        return False, "Unauthorized (401)"
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}"

    try:
        data: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response"

    msg = str(data.get("message") or data.get("msg") or "")
    if data.get("code") == 200 or "成功" in msg:
        return True, msg or "打卡成功"
    return False, msg or "打卡失败"


def get_qrcode_url(course_id: int) -> str:
    timestamp_ms = int(time.time() * 1000)
    return f"{DEKT_HOST}/qrcode/event/?course_id={int(course_id)}&timestamp={timestamp_ms}"


def get_qrcode_image(course_id: int) -> tuple[bool, str, bytes]:
    """Get QR image bytes.

    The QR code is generated locally from the QR event URL.
    """
    qr_url = get_qrcode_url(course_id)

    try:
        qrcode_module = importlib.import_module("qrcode")
    except Exception:
        qrcode_module = None

    if qrcode_module is not None:
        try:
            qr = qrcode_module.QRCode(
                version=1,
                error_correction=qrcode_module.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            image_obj: Any = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            image_obj.save(buffer)
            data = buffer.getvalue()
            if data:
                return True, "OK", data
        except Exception:
            pass

    return False, "QR generation unavailable (local dependency missing)", b""


def get_transcript_score(
    token: str,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", {}

    url = f"{DEKT_HOST}/api/transcript/score"
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}", {}

    if resp.status_code == 401:
        return False, "Unauthorized (401)", {}
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}", {}

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response", {}

    if body.get("code") != 200:
        msg = str(body.get("message") or body.get("msg") or "API error")
        return False, msg, {}

    data = body.get("data")
    if not isinstance(data, dict):
        return False, "Unexpected API response structure", {}

    return True, "OK", data
