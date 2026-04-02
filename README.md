# open collar

**A Windows-first desktop computer-use agent that can actually touch the machine.**

`open collar` turns a natural-language task into a plan, executes real desktop actions through a safe tool layer, shows its work live, and only finishes when the result is verified.

It is built around a simple idea:

- The model is the brain.
- The automation runtime is the hands.
- The app is the visible control center.

## Why this project is interesting

Most agent demos stop at browser tabs or CLI toys. `open collar` is aimed at the harder, messier layer: real Windows applications, real dialogs, real file saves, and a human sitting in the loop with visibility instead of blind trust.

This MVP already includes:

- A Tauri desktop shell
- A React + TypeScript operator UI
- A Python worker that plans, executes, verifies, and logs
- SQLite persistence for runs, steps, events, observations, and artifacts
- A strict JSONL bridge between app and worker
- A whitelisted Windows tool surface built around `pywinauto`
- A deterministic Notepad++ end-to-end scenario

## What it feels like

The UI is split into a codex-style control center:

- Left: run history
- Center: current run, grouped steps, approvals, live logs
- Right: screenshots, active window details, observations, artifacts
- Bottom: prompt input, mode selector, start/pause/stop controls

Three execution modes are built in:

- `observe`: plan and inspect only, no mutating desktop actions
- `assist`: default mode, pauses for human approval at each step group
- `auto`: runs continuously until it needs to stop for failure or final verification

## MVP scenario

The first full flow is deliberately concrete:

> Open Notepad++, write a poem, and save it to `Desktop/agent_test/gedicht.txt`

That path includes:

1. Creating the target folder
2. Launching Notepad++
3. Waiting for the window
4. Focusing it
5. Typing the poem
6. Triggering save
7. Handling the save dialog
8. Verifying the file exists
9. Capturing a screenshot
10. Marking the run completed

## Architecture

```text
prompt -> Tauri shell -> Python worker -> whitelisted tools -> Windows desktop
              |               |
              |               -> planner / executor / verifier
              |
              -> SQLite persistence + live UI updates
```

Core layers:

- `src/`: React UI and Tauri-facing client code
- `src-tauri/`: Rust app shell, SQLite persistence, worker bridge
- `worker/`: Python agent runtime, planner, model client, tool registry, tests

## Tech stack

- Desktop shell: Tauri
- UI: React + TypeScript
- Worker: Python
- IPC: JSON lines over stdin/stdout
- Persistence: SQLite
- Windows automation: `pywinauto`
- Browser automation scaffold: Playwright
- Model integration: Gemini model selection in the app, with user-supplied API keys entered per run

## Safety model

`open collar` is intentionally narrow and inspectable.

- No arbitrary shell execution from model output
- Only whitelisted tools can execute
- Tool arguments are validated before execution
- Tool calls, results, and errors are logged
- Runs are not marked complete without verification
- `assist` mode defaults to approval gates

## Quick start

### Windows prerequisites

- Node.js 22+
- Rust toolchain with Cargo
- Python 3.11+
- Notepad++ installed and available as `notepad++` on `PATH`

### Install the app

```bash
npm install
python -m venv .venv
.venv\Scripts\activate
pip install -r worker/requirements.txt
python -m playwright install
```

### Gemini model selection

The composer now lets the user choose:

- `deterministic MVP`
- `gemini-2.5-flash`
- `gemini-2.5-pro`

When `Google Gemini` is selected, the user must manually paste an API key into the app before starting the run.

The key is intended to be transient:

- entered by the user in the UI
- sent to the worker for that run
- not committed to the repo
- not persisted as part of the saved run record

Without a Gemini selection, the deterministic Notepad++ MVP path still works.

### Run the desktop app

```bash
npm run tauri:dev
```

## Development commands

```bash
npm test
npm run lint
npm run build
npm run tauri:dev
npm run deploy:shared
```

Python tests:

```bash
set PYTHONPATH=worker
.venv\Scripts\python -m pytest worker/tests
```

## Deployment to the shared folder

This repo includes a deployment script that is intended to produce a testable Windows handoff bundle in:

```text
/media/sf_DEL_ME
```

If you only want to copy the source tree into `DEL_ME` and then run/build it on Windows, use:

```bash
npm run transfer:delme
```

That stages the project into:

```text
/media/sf_DEL_ME/open-collar-transfer/current
```

The Windows handoff instructions live in:

```text
docs/WINDOWS_RUN.md
```

Run:

```bash
npm run deploy:shared
```

Default behavior:

- run frontend tests
- build the frontend
- package `worker/open-collar-worker.exe` with PyInstaller when run on Windows
- build `open-collar.exe` with Tauri when run on Windows
- assemble a portable folder in `current/`
- generate `current/RUN_OPEN_COLLAR.bat`
- write startup logs to `current/logs/open-collar.log`

Important:

- the script must run on a Windows-capable host to produce the `.exe`
- if you only want a source handoff from Linux, run it with `BUILD_WINDOWS_EXE=0`

Portable folder layout:

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

## Repository docs

Read these on GitHub for the full code walkthrough:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/CODE_TOUR.md](docs/CODE_TOUR.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Current status

What is working in this repo now:

- React UI shell
- Python worker runtime
- JSONL protocol
- SQLite-backed state model in Tauri
- deterministic Notepad++ planning path
- fake-tool E2E coverage

What still needs a real Windows machine to fully prove:

- `pywinauto` desktop automation against live windows
- full Tauri desktop build and native runtime packaging

## Vision

The MVP starts with one trustworthy Windows scenario, but the shape is bigger than that:

- richer planner outputs
- browser task tools
- stronger verification strategies
- safer recovery from desktop ambiguity
- broader Windows application coverage

The goal is not “an agent that sometimes clicks things.”

The goal is a local operator console for dependable desktop action.
