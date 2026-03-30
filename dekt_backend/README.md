# DEKT Backend (MVP)

This service is the backend side of the DEKT split architecture.
It stores runtime config locally and exposes signed HTTP APIs for the GUI.

## Security Model (MVP)

- All non-health endpoints require HMAC headers:
  - `X-API-Key`
  - `X-Timestamp`
  - `X-Nonce`
  - `X-Signature`
- Signature algorithm: `HMAC-SHA256`
- Message format:
  - `{timestamp}.{nonce}.{METHOD}.{PATH}.{sha256(body_bytes)}`

## Environment

```bash
export DEKT_BACKEND_API_KEY="replace-with-strong-secret"
export DEKT_BACKEND_HOST="0.0.0.0"
export DEKT_BACKEND_PORT="8000"
```

## Run

```bash
cd dekt_backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

Quick start script (same behavior as above):

```bash
cd dekt_backend
DEKT_BACKEND_API_KEY="replace-with-strong-secret" \
.venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
```

## Local Smoke Check

Run minimal connectivity/auth checks against local backend:

```bash
cd dekt_backend
python local_smoke.py --base-url http://127.0.0.1:8000 --api-key "replace-with-strong-secret"
```

This script validates:

- `GET /health` (no signature)
- `GET /api/v1/config` (signed)
- `POST /api/v1/auth/verify` (signed)

Optional token verify:

```bash
cd dekt_backend
python local_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "replace-with-strong-secret" \
  --token "Bearer your-token"
```

## Config Storage

Backend config is stored in:

- `~/.dekt_backend/config.json`

This file includes DEKT token and whitelist settings for monitor filtering.
