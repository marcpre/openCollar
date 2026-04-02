# Run on Windows

This guide is for the source-transfer bundle copied into `DEL_ME` with:

```bash
bash scripts/transfer_to_del_me.sh
```

After the transfer, open the copied project on Windows from:

```text
/media/sf_DEL_ME/open-collar-transfer/current
```

## Option 1: Run the app in development mode

Use this when you want to verify the app starts and test changes quickly.

### Prerequisites

- Node.js 22+
- Rust + Cargo
- Python 3.11+
- Microsoft WebView2 Runtime
- Notepad++ installed and available on `PATH`

### Setup

Open PowerShell in the project folder and run:

```powershell
npm install
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r worker\requirements.txt
python -m playwright install
```

### Start the desktop app

```powershell
$env:OPEN_COLLAR_PYTHON = "$PWD\.venv\Scripts\python.exe"
npm run tauri:dev
```

## Option 2: Build a portable Windows test app

Use this when you want a shared-folder build you can launch directly.

From Windows, in the same project folder:

```powershell
bash scripts/deploy_shared_folder.sh
```

That script is intended to produce:

```text
/media/sf_DEL_ME/open-collar-deploy/current/
  open-collar.exe
  worker/open-collar-worker.exe
  logs/
  data/
  RUN_OPEN_COLLAR.bat
```

Launch it with:

```text
/media/sf_DEL_ME/open-collar-deploy/current/RUN_OPEN_COLLAR.bat
```

## If startup fails

Check:

```text
/media/sf_DEL_ME/open-collar-deploy/current/logs/open-collar.log
```

Common causes:

- Rust toolchain not installed
- Python missing on the Windows machine
- worker dependencies not installed for dev mode
- WebView2 missing
- Notepad++ missing from `PATH`

## Gemini usage

Gemini API keys are entered in the app UI by the user per run.

Do not hardcode them into the repo or `.env` files that get transferred.
