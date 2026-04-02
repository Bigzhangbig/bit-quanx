#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import uuid
import urllib.error
import urllib.request
from urllib.parse import urlparse


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_signature(api_key: str, timestamp: str, nonce: str, method: str, path: str, body_bytes: bytes) -> str:
    message = f"{timestamp}.{nonce}.{method.upper()}.{path}.{sha256_hex(body_bytes)}"
    return hmac.new(api_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def signed_request(base_url: str, api_key: str, method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    payload = b""
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    ts = str(int(time.time()))
    # 每次请求使用随机后缀，避免被误判为重放请求。
    nonce = f"smoke-{ts}-{uuid.uuid4().hex[:8]}"
    signature = build_signature(api_key, ts, nonce, method, path, payload)

    url = f"{base_url.rstrip('/')}{path}"
    headers = {
        "X-API-Key": api_key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url=url, data=payload if payload else None, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def plain_get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="DEKT 后端本地冒烟检查")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端基础地址")
    parser.add_argument("--api-key", required=True, help="后端 API key")
    parser.add_argument("--token", default="", help="可选 token，用于 /api/v1/auth/verify")
    args = parser.parse_args()

    health_status, health_body = plain_get(f"{args.base_url.rstrip('/')}/health")
    print(f"[健康检查] 状态={health_status} 响应={health_body}")
    if health_status != 200:
        return 1

    config_status, config_body = signed_request(args.base_url, args.api_key, "GET", "/api/v1/config")
    print(f"[配置读取] 状态={config_status} 响应={config_body}")
    if config_status != 200:
        return 1

    host = (urlparse(args.base_url).hostname or "").lower()
    if host in {"127.0.0.1", "localhost"}:
        print("[鉴权验证] 本地地址已跳过")
        return 0

    verify_payload = {"token": args.token, "use_stored": not bool(args.token)}
    verify_status, verify_body = signed_request(
        args.base_url,
        args.api_key,
        "POST",
        "/api/v1/auth/verify",
        verify_payload,
    )
    print(f"[鉴权验证] 状态={verify_status} 响应={verify_body}")

    if verify_status not in (200, 400):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())