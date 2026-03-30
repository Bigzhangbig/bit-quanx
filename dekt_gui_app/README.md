# DEKT Desktop GUI (alpha)

A standalone Python desktop app for DEKT workflows.
This app is independent from the existing JS scripts.

## Current alpha scope

- Manual token input
- Load token from GitHub Gist
- Verify token via `GET /api/user/info`
- Manual monitor query page (one-click query for all 6 categories, tab switching)
- Monitor table right-click actions (signup/cancel with enrollment pre-check)
- Monitor table column width auto-fit by content
- Sign page (load my activities + manual sign-in/sign-out)
- Activities page (list my activities + double-click detail)
- Unenroll tab removed from GUI
- Local credential persistence under `~/.dekt_gui/config.json`
- Auto-load defaults from `.env` in `dekt_gui_app/`

## Constraints

- Native desktop GUI using PySide6 Qt Widgets
- No embedded browser/WebView stack

## TLS notes

- The app allows insecure TLS (self-signed certificates) by default.
- You can disable `Ignore TLS certificate verification (debug only)` in the Credentials tab to re-enable strict verification.

## Run

```bash
cd dekt_gui_app
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Backend Mode (Front/Back Split)

Use this mode when GUI should only act as a client and keep runtime config on backend.

1. Start backend service first (see `../dekt_backend/README.md`).
2. Open GUI `Credentials` tab.
3. Enable `Use backend mode (recommended for split architecture)`.
4. Fill backend connection:
	- `Backend base URL` (example: `http://127.0.0.1:8000`)
	- `Backend API key` (must match backend `DEKT_BACKEND_API_KEY`)
5. Click `Test backend connection` to verify `/health` and signed config read.
6. Set or paste token in GUI, then click `Sync token to backend`.
7. Fill whitelist fields (`category ids`, `grade`, `academy/college`) and click `Sync whitelist to backend`.
8. Optional: click `Load whitelist from backend` to pull current server-side values.

After backend mode is enabled:

- `Verify token` uses backend `/api/v1/auth/verify`.
- `Monitor` list and right-click `Signup/Cancel` use backend course APIs.
- `Sign in/out` uses backend `checkin-info` and sign APIs.

If `dekt_gui_app/.env` exists, the app will auto-read default values:

- `bit_sc_token`
- `bit_sc_github_token`
- `bit_sc_gist_id`
- `bit_sc_gist_filename`
- `bit_sc_tencent_map_key`
- `bit_sc_tls_insecure` (optional, `true/false`)
- `dekt_backend_mode` (optional, `true/false`)
- `dekt_backend_base_url` (optional)
- `dekt_backend_api_key` (optional)

## Package (macOS)

Build a desktop app bundle with PyInstaller:

```bash
cd dekt_gui_app
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name DEKT-GUI --paths . main.py
```

Build output:

- App bundle: `dekt_gui_app/dist/DEKT-GUI.app`
- Executable: `dekt_gui_app/dist/DEKT-GUI.app/Contents/MacOS/DEKT-GUI`

## Package (Windows)

Use GitHub Actions to build on a real Windows runner (recommended when your local machine is macOS):

1. Push current changes to your GitHub repository.
2. Open Actions and run workflow `Build DEKT GUI (Windows)` manually.
3. Download artifact `DEKT-GUI-windows` from the workflow run result.
4. Unzip `DEKT-GUI-windows.zip`, then run `DEKT-GUI/DEKT-GUI.exe`.

Workflow file:

- `.github/workflows/build-dekt-gui-windows.yml`

If you want local Windows build (without GitHub):

```bat
cd dekt_gui_app
build_windows.bat
```

Local build output on Windows:

- Folder: `dekt_gui_app\\dist\\DEKT-GUI`
- Executable: `dekt_gui_app\\dist\\DEKT-GUI\\DEKT-GUI.exe`

Note:

- PyInstaller does not support building Windows `.exe` directly on macOS/Linux.
- To package Windows version locally, run `build_windows.bat` on a Windows machine (or Windows VM).

## Project status

Current stage: **Alpha (manual workflow usable)**

### Stage checklist

- ✅ Credentials page (manual token / Gist / verify / local persistence)
- ✅ Monitor page (manual refresh for all 6 categories, table actions)
- ✅ Sign page (manual sign-in/sign-out with time-window checks)
- ✅ Activities page (my activities list + detail dialog)
- ✅ Course detail enhancements (cover, map preview, sectioned detail view)
- ⏳ Signup queue page (UI not wired yet)
- ⏳ Scheduler / background jobs (not started)

### Next milestones

- Signup queue page
- Scheduler + background jobs
- Better release process (artifact naming/versioning)
