# Deployment

## Goal

The repo includes a deployment script for producing a testable handoff bundle in:

```text
/media/sf_DEL_ME
```

The preferred outcome is:

- a Windows `open-collar.exe`
- a packaged worker `worker/open-collar-worker.exe`
- a matching `RUN_OPEN_COLLAR.bat`
- logs and data folders beside the app

## Script

Run:

```bash
npm run deploy:shared
```

Or directly:

```bash
bash scripts/deploy_shared_folder.sh
```

Optional custom target:

```bash
bash scripts/deploy_shared_folder.sh /some/other/path
```

## Default behavior

1. Runs frontend tests
2. Builds the frontend with `npm run build`
3. Packages `worker/open-collar-worker.exe` with PyInstaller on Windows
4. Builds `open-collar.exe` with `npm run tauri:build`
5. Creates a timestamped portable release under `open-collar-deploy/releases/`
6. Copies the app exe, worker exe, docs, logs folder, and launcher into that release
7. Writes `RUN_OPEN_COLLAR.bat`
8. Writes a `DEPLOYMENT_MANIFEST.txt`
9. Refreshes `open-collar-deploy/current/`

Portable output layout:

```text
current/
  open-collar.exe
  worker/open-collar-worker.exe
  logs/
  data/
  RUN_OPEN_COLLAR.bat
  README.md
  docs/
```

## Running from Linux

The script cannot produce a native Windows `.exe` from this Linux environment unless you provide a full Windows-capable Rust/Tauri cross-build setup, which this repo does not assume.

If you still want a source-only transfer bundle from Linux, use:

```bash
BUILD_WINDOWS_EXE=0 bash scripts/deploy_shared_folder.sh
```

That keeps the handoff flow available without pretending a Windows binary was created.

## What is excluded

The staged bundle intentionally excludes:

- `.git/`
- `node_modules/`
- `.venv/`
- `.portable-build-venv/`
- `dist/` before rebuild
- `.pytest_cache/`
- `.tmp-artifacts/`
- Python bytecode
- Rust `target/`
- PyInstaller build output before assembly

## Windows requirements for the executable

To build the portable Windows bundle, the machine running the script needs:

- Node.js
- Rust / Cargo
- Python
- Tauri prerequisites for Windows

The produced portable build should be launched via `RUN_OPEN_COLLAR.bat`, which:

- points the app at the packaged worker executable
- sets deterministic `logs/` and `data/` directories
- keeps startup attached so early failures are visible
