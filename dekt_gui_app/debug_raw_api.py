from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.parse import urljoin

import httpx

from dekt_gui.api_client import DEKT_HOST, normalize_bearer_token
from dekt_gui.config import load_config


def _mask_auth(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return text
    parts = text.split(" ", 1)
    token = parts[-1]
    if len(token) <= 10:
        masked = "*" * len(token)
    else:
        masked = f"{token[:6]}...{token[-4:]}"
    if len(parts) == 2:
        return f"{parts[0]} {masked}"
    return masked


def _parse_headers(header_args: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in header_args:
        if ":" not in raw:
            raise ValueError(f"Invalid header format: {raw}")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid header key: {raw}")
        result[key] = value
    return result


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _print_request(method: str, url: str, headers: dict[str, str], body_text: str) -> None:
    print("=== Request ===")
    print(f"{method} {url}")
    print("Headers:")
    for key, value in headers.items():
        if key.lower() == "authorization":
            print(f"  {key}: {_mask_auth(value)}")
        else:
            print(f"  {key}: {value}")

    if body_text:
        print("Body:")
        parsed = _maybe_json(body_text)
        if parsed is not None:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        else:
            print(body_text)
    else:
        print("Body: <empty>")


def _print_response(resp: httpx.Response, body_limit: int) -> None:
    print("\n=== Response ===")
    print(f"Status: {resp.status_code}")
    print("Headers:")
    for key, value in resp.headers.items():
        print(f"  {key}: {value}")

    body = resp.text
    if body_limit > 0 and len(body) > body_limit:
        body = body[:body_limit] + "\n...<truncated>"

    print("Body (raw):")
    print(body)

    parsed = _maybe_json(resp.text)
    if parsed is not None:
        print("\nBody (json pretty):")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Debug DEKT API request/response with full raw output.",
    )
    parser.add_argument("--method", default="GET", help="HTTP method, e.g. GET/POST")
    parser.add_argument(
        "--path",
        default="/api/course/list/my?page=1&limit=20",
        help="Request path based on DEKT host, e.g. /api/course/info/1134",
    )
    parser.add_argument("--url", default="", help="Full request URL (overrides --path)")
    parser.add_argument("--data", default="", help="Raw JSON body text")
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Extra headers, repeatable: --header 'Key: Value'",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout seconds")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification for debugging",
    )
    parser.add_argument(
        "--body-limit",
        type=int,
        default=12000,
        help="Max response body chars to print in raw section (0 means unlimited)",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Bearer token or raw token. If omitted, read from GUI config/.env",
    )

    args = parser.parse_args()
    cfg = load_config()

    method = str(args.method or "GET").upper().strip()
    if not method:
        raise ValueError("Method is empty")

    token = normalize_bearer_token(args.token or cfg.token)
    if not token:
        print("Token is empty. Provide --token or configure in GUI config/.env.")
        return 1

    url = args.url.strip() if args.url else urljoin(DEKT_HOST, args.path.strip())
    headers = {
        "Authorization": token,
        "Content-Type": "application/json;charset=utf-8",
    }
    headers.update(_parse_headers(args.header))

    body_text = (args.data or "").strip()
    _print_request(method, url, headers, body_text)

    verify: bool = not (args.insecure or cfg.tls_insecure)
    with httpx.Client(timeout=args.timeout, follow_redirects=True, verify=verify) as client:
        request = client.build_request(
            method=method,
            url=url,
            headers=headers,
            content=body_text.encode("utf-8") if body_text else None,
        )
        response = client.send(request)

    _print_response(response, args.body_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
