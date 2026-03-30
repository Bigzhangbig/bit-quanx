from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
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


def _body_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _build_backend_signature(
    api_key: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    payload: bytes,
) -> str:
    message = f"{timestamp}.{nonce}.{method.upper()}.{path}.{_body_sha256(payload)}"
    return hmac.new(api_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def backend_health_check(
    base_url: str,
    timeout: float = 8.0,
    insecure_tls: bool = False,
) -> tuple[bool, str]:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return False, "Backend URL is empty"

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(f"{root}/health")
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend request failed: {exc}"

    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"Backend HTTP {resp.status_code}"

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Backend response is not valid JSON"

    if body.get("ok") is True:
        return True, "Backend is reachable"
    return False, str(body.get("error") or body.get("message") or "Backend health check failed")


def backend_signed_post(
    base_url: str,
    path: str,
    api_key: str,
    body: dict[str, Any],
    timeout: float = 10.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return False, "Backend URL is empty", {}

    key = (api_key or "").strip()
    if not key:
        return False, "Backend API key is empty", {}

    req_path = path if path.startswith("/") else f"/{path}"
    url = f"{root}{req_path}"
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    ts = str(int(time.time()))
    nonce = f"gui-{ts}"
    signature = _build_backend_signature(
        api_key=key,
        timestamp=ts,
        nonce=nonce,
        method="POST",
        path=req_path,
        payload=payload,
    )
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.post(url, content=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend request failed: {exc}", {}

    try:
        data: dict[str, Any] = resp.json()
    except ValueError:
        return False, f"Backend HTTP {resp.status_code}", {}

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = data.get("error") or data.get("detail") or data.get("message") or f"HTTP {resp.status_code}"
        return False, str(detail), data

    if data.get("ok") is False:
        return False, str(data.get("error") or data.get("message") or "backend_error"), data
    return True, str(data.get("message") or "ok"), data


def backend_signed_get(
    base_url: str,
    path: str,
    api_key: str,
    timeout: float = 10.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return False, "Backend URL is empty", {}

    key = (api_key or "").strip()
    if not key:
        return False, "Backend API key is empty", {}

    req_path = path if path.startswith("/") else f"/{path}"
    url = f"{root}{req_path}"

    ts = str(int(time.time()))
    nonce = f"gui-{ts}"
    signature = _build_backend_signature(
        api_key=key,
        timestamp=ts,
        nonce=nonce,
        method="GET",
        path=req_path,
        payload=b"",
    )
    headers = {
        "X-API-Key": key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend request failed: {exc}", {}

    try:
        data: dict[str, Any] = resp.json()
    except ValueError:
        return False, f"Backend HTTP {resp.status_code}", {}

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = data.get("error") or data.get("detail") or data.get("message") or f"HTTP {resp.status_code}"
        return False, str(detail), data

    if data.get("ok") is False:
        return False, str(data.get("error") or data.get("message") or "backend_error"), data
    return True, str(data.get("message") or "ok"), data


def backend_signed_put(
    base_url: str,
    path: str,
    api_key: str,
    body: dict[str, Any],
    timeout: float = 10.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return False, "Backend URL is empty", {}

    key = (api_key or "").strip()
    if not key:
        return False, "Backend API key is empty", {}

    req_path = path if path.startswith("/") else f"/{path}"
    url = f"{root}{req_path}"
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    ts = str(int(time.time()))
    nonce = f"gui-{ts}"
    signature = _build_backend_signature(
        api_key=key,
        timestamp=ts,
        nonce=nonce,
        method="PUT",
        path=req_path,
        payload=payload,
    )
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.put(url, content=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend request failed: {exc}", {}

    try:
        data: dict[str, Any] = resp.json()
    except ValueError:
        return False, f"Backend HTTP {resp.status_code}", {}

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = data.get("error") or data.get("detail") or data.get("message") or f"HTTP {resp.status_code}"
        return False, str(detail), data

    if data.get("ok") is False:
        return False, str(data.get("error") or data.get("message") or "backend_error"), data
    return True, str(data.get("message") or "ok"), data


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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", []

    url = (
        f"{DEKT_HOST}/api/course/list?page=1&limit={int(limit)}"
        f"&sign_status={int(sign_status)}"
        f"&transcript_index_id={int(transcript_index_id)}"
        "&transcript_index_type_id=0"
    )
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}", []

    if resp.status_code == 401:
        return False, "Unauthorized (401)", []
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}", []

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response", []

    if body.get("code") != 200:
        msg = str(body.get("message") or body.get("msg") or "API error")
        return False, msg, []

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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", {}

    url = f"{DEKT_HOST}/api/course/info/{int(course_id)}"
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


def apply_course(
    token: str,
    course_id: int,
    template_id: str = DEFAULT_TEMPLATE_ID,
    timeout: float = 12.0,
    insecure_tls: bool = False,
) -> tuple[bool, str]:
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty"

    url = f"{DEKT_HOST}/api/course/apply"
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }
    body = {
        "course_id": int(course_id),
        "template_id": template_id,
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
    if data.get("code") == 200 or "成功" in msg or "已报名" in msg:
        return True, msg or "报名成功"
    return False, msg or "报名失败"


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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "", "Token is empty"

    headers = {"Authorization": auth}
    url = f"{DEKT_HOST}/api/user/info"

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, "", f"Request failed: {exc}"

    if resp.status_code == 401:
        return False, "", "Unauthorized (401)"
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, "", f"HTTP {resp.status_code}"

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "", "Invalid JSON response"

    if body.get("code") != 200 or not isinstance(body.get("data"), dict):
        msg = str(body.get("message") or body.get("msg") or "API error")
        return False, "", msg

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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", set()

    url = f"{DEKT_HOST}/api/course/list/my?page=1&limit={int(limit)}"
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}", set()

    if resp.status_code == 401:
        return False, "Unauthorized (401)", set()
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}", set()

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response", set()

    if body.get("code") != 200:
        msg = str(body.get("message") or body.get("msg") or "API error")
        return False, msg, set()

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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty"

    url = f"{DEKT_HOST}/api/course/cancelApply"
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }
    body = {
        "course_id": int(course_id),
        "user_id": int(user_id),
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
    if data.get("code") in (200, 0) or data.get("success") is True or "成功" in msg:
        return True, msg or "取消报名成功"
    return False, msg or "取消报名失败"


def list_my_courses(
    token: str,
    limit: int = 200,
    timeout: float = 15.0,
    insecure_tls: bool = False,
) -> tuple[bool, str, list[dict[str, Any]]]:
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", []

    url = f"{DEKT_HOST}/api/course/list/my?page=1&limit={int(limit)}"
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
    }

    try:
        with _create_client(timeout=timeout, insecure_tls=insecure_tls) as client:
            resp = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Request failed: {exc}", []

    if resp.status_code == 401:
        return False, "Unauthorized (401)", []
    if resp.status_code < 200 or resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}", []

    try:
        body: dict[str, Any] = resp.json()
    except ValueError:
        return False, "Invalid JSON response", []

    if body.get("code") != 200:
        msg = str(body.get("message") or body.get("msg") or "API error")
        return False, msg, []

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
    auth = normalize_bearer_token(token)
    if not auth:
        return False, "Token is empty", {}

    url = f"{DEKT_HOST}/api/transcript/checkIn/info?course_id={int(course_id)}"
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
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json;charset=utf-8",
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
