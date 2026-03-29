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

- The app uses the `certifi` CA bundle for TLS verification by default.
- If your local network/proxy rewrites certificates, you can temporarily enable:
	`Ignore TLS certificate verification (debug only)` in the Credentials tab.

## Run

```bash
cd dekt_gui_app
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

If `dekt_gui_app/.env` exists, the app will auto-read default values:

- `bit_sc_token`
- `bit_sc_github_token`
- `bit_sc_gist_id`
- `bit_sc_gist_filename`
- `bit_sc_tencent_map_key`
- `bit_sc_tls_insecure` (optional, `true/false`)

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

## Next milestones

- Monitor page
- Signup queue page
- Sign-in/sign-out page
- Scheduler + background jobs
