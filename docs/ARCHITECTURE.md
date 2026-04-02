# Architecture

## Overview

`open collar` is a three-runtime desktop system:

- **React UI** presents the operator view
- **Tauri / Rust** owns the desktop shell, persistence, and worker bridge
- **Python worker** owns planning, execution, verification, and tool control

The design goal is simple: keep the UI responsive, keep the safety boundary explicit, and keep every action inspectable after the fact.

## High-level flow

1. The user enters a prompt in the React UI.
2. The UI calls a Tauri command such as `start_run`.
3. Rust creates a run record, persists it to SQLite, and forwards a JSONL command to the worker.
4. The worker creates a structured plan, emits step records, and either requests approval or starts execution.
5. Each tool call produces events, observations, and artifacts.
6. Rust persists those updates and pushes fresh app state back into the UI through a Tauri event channel.
7. The user watches progress live and approves the next step group when required.

## Layer responsibilities

### React

Key files:

- [`src/App.tsx`](../src/App.tsx)
- [`src/hooks/useOpenCollarApp.ts`](../src/hooks/useOpenCollarApp.ts)
- [`src/lib/tauri.ts`](../src/lib/tauri.ts)

Responsibilities:

- render run history, current run, logs, observations, and artifacts
- invoke Tauri commands for run lifecycle actions
- subscribe to `open-collar://state` snapshots
- keep the operator loop visible and understandable

### Tauri / Rust

Key files:

- [`src-tauri/src/main.rs`](../src-tauri/src/main.rs)
- [`src-tauri/src/db.rs`](../src-tauri/src/db.rs)
- [`src-tauri/src/worker.rs`](../src-tauri/src/worker.rs)
- [`src-tauri/src/models.rs`](../src-tauri/src/models.rs)

Responsibilities:

- initialize app storage
- create and load SQLite tables
- spawn the Python sidecar
- translate UI commands into worker envelopes
- persist worker output into normalized records
- emit fresh snapshots back to the frontend

### Python worker

Key files:

- [`worker/open_collar/runtime.py`](../worker/open_collar/runtime.py)
- [`worker/open_collar/planner.py`](../worker/open_collar/planner.py)
- [`worker/open_collar/tools.py`](../worker/open_collar/tools.py)
- [`worker/open_collar/model_client.py`](../worker/open_collar/model_client.py)

Responsibilities:

- create plans
- gate execution by mode
- instantiate the selected model client for each run
- validate and execute whitelisted tools
- capture verification data
- emit structured events over JSONL

## Persistence model

SQLite tables:

- `runs`
- `steps`
- `events`
- `observations`
- `artifacts`

This model gives the app two useful properties:

- active runs can stream live
- completed runs can be reloaded from disk without reconstructing state from logs

## Execution modes

- `observe`: plan and inspect only
- `assist`: require human approval for each step group
- `auto`: continue without pausing unless blocked, failed, or cancelled

The current MVP emphasizes `assist`, because it offers the best operator visibility while the tool surface is still small.

## Safety boundary

The most important architectural rule is that model output never becomes arbitrary code execution.

Safety constraints:

- only predeclared tools can run
- each tool has an expected argument shape
- unknown tools are rejected
- errors are surfaced, not hidden
- completion requires verification

This means the model can suggest actions, but it cannot escape the action vocabulary defined in `worker/open_collar/tools.py`.

## Notepad++ scenario path

The first shipped scenario is intentionally deterministic. The planner recognizes the Notepad++ save task and emits a fixed plan:

1. `create_folder`
2. `open_application`
3. `wait_for_window`
4. `focus_window`
5. `type_text`
6. `press_keys`
7. `save_file_as`
8. `verify_path_exists`
9. `capture_screenshot`

This keeps the MVP demonstrable even if model configuration is missing.
