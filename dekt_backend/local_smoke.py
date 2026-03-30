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
    # Use a per-request random suffix to avoid replay false positives.
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
    parser = argparse.ArgumentParser(description="DEKT backend local smoke check")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--api-key", required=True, help="Backend API key")
    parser.add_argument("--token", default="", help="Optional token for /api/v1/auth/verify")
    args = parser.parse_args()

    health_status, health_body = plain_get(f"{args.base_url.rstrip('/')}/health")
    print(f"[health] status={health_status} body={health_body}")
    if health_status != 200:
        return 1

    config_status, config_body = signed_request(args.base_url, args.api_key, "GET", "/api/v1/config")
    print(f"[config] status={config_status} body={config_body}")
    if config_status != 200:
        return 1

    host = (urlparse(args.base_url).hostname or "").lower()
    if host in {"127.0.0.1", "localhost"}:
        print("[verify] skipped for localhost target")
        return 0

    verify_payload = {"token": args.token, "use_stored": not bool(args.token)}
    verify_status, verify_body = signed_request(
        args.base_url,
        args.api_key,
        "POST",
        "/api/v1/auth/verify",
        verify_payload,
    )
    print(f"[verify] status={verify_status} body={verify_body}")

    if verify_status not in (200, 400):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())