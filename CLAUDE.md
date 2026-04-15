# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a hybrid JavaScript/Python repository for automating BIT (Beijing Institute of Technology) second-classroom (DEKT) and campus card workflows. It contains three layers:

1. **Quantumult X scripts** (`dekt_*.js`, `card_*.js`) that run inside the QX app.
2. **Local Node.js debug tools** (`local_*.js`) that wrap the QX scripts for local development.
3. **Python backend + desktop GUI** (`dekt_backend/` and `dekt_gui_app/`) that provide a standalone alternative to the JS toolchain.

All JavaScript files are stored under `scripts/`.

## Common Commands

### JavaScript / Node.js

- Install the only runtime dependency: `npm install` (or `bun install`)
- Run a local debug script: `node scripts/local_dekt_monitor.js` or `node scripts/local_card_probe.js`

### Python Backend (`dekt_backend/`)

- Install and run (from repo root):
  ```bash
  cd dekt_backend
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/uvicorn dekt_backend.main:app --host 0.0.0.0 --port 8000
  ```
- Run tests: `pytest -q dekt_backend/tests`
- Web mode quick check:
  ```bash
  curl -i http://127.0.0.1:8000/
  curl -i http://127.0.0.1:8000/health
  curl -i http://127.0.0.1:8000/runtime
  ```

### Python GUI (`dekt_gui_app/`)

- Install and run:
  ```bash
  cd dekt_gui_app
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python main.py
  ```
- Build macOS app (requires `pyinstaller`):
  ```bash
  .venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name DEKT-GUI --paths . main.py
  ```

### CI / Lint

- Syntax check for both Python packages: `python -m compileall dekt_backend dekt_gui_app`
- Tests are run via `pytest -q dekt_backend/tests` (see `.github/workflows/ci-python.yml`)

## High-Level Architecture

### JS Side: QX / Local Dual Environment

- All production scripts use the QX global `Env` class (instantiated as `const $ = new Env(...)`).
- `scripts/local_env.js` provides a Node.js-compatible shim of the `Env` class so the same scripts can run locally without QX.
- Local wrappers (`scripts/local_*.js`) require `./local_env` and then load the original logic.
- Scripts read configuration from the repo-root `.env` file when running locally, and from BoxJS when running in QX.
- Naming convention:
  - `scripts/dekt_*.js` — QX scripts for DEKT (second classroom)
  - `scripts/card_*.js` — QX scripts for campus card
  - `scripts/local_*.js` — local Node.js wrappers / utilities
  - `scripts/*_cookie.js` — rewrite scripts that capture auth tokens from requests

### Python Side: Backend + GUI

- **`dekt_backend/`** is a FastAPI-based web service for status pages.
  - It serves web pages only (`/`, `/health`, `/runtime`) and no longer exposes `/api/v1/*` APIs.
  - `runtime.py` runs a background thread that periodically polls DEKT APIs when `DEKT_BACKEND_RUNTIME_ENABLED=true`.
  - Config is persisted at `~/.dekt_backend/config.json`.

- **`dekt_gui_app/`** is a PySide6 desktop application.
  - It now works in direct mode only, talking to DEKT APIs via `dekt_gui/api_client.py`.
  - Config is persisted at `~/.dekt_gui/config.json`.
  - Defaults can be seeded from `dekt_gui_app/.env`.

- **Shared client layer**: `dekt_gui_app/dekt_gui/api_client.py` contains the core HTTP client for DEKT and GitHub Gist. It is imported by GUI and backend runtime. Because the backend imports from `dekt_gui_app`, `dekt_gui_app` must be on `PYTHONPATH` when the backend runs.

### Configuration Files

- `.env` at repo root: shared by JS local tools and Python apps.
- `dekt_backend/.env`: backend-specific overrides (loaded after repo-root `.env`).
- `dekt_gui_app/.env`: GUI default values.

## Code Style Notes (from existing conventions)

- JavaScript: CommonJS (`require` / `module.exports`), ES2020+, prefer `async/await`.
- Python: type hints (`from __future__ import annotations`), dataclasses for settings, `httpx` for HTTP.
- Logging: QX scripts use `$.msg` / `$.log`; local scripts use `console.log`; Python uses plain logging or returns `(ok, message, data)` tuples.
- Do not log or commit real tokens, cookies, or OpenIDs.
