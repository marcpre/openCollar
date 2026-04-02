# Code Tour

## Frontend

### [`src/App.tsx`](../src/App.tsx)

Builds the main control-center layout and wires the selected run into:

- `RunHistory`
- `RunDetails`
- `InspectorPanel`
- `PromptComposer`

### [`src/hooks/useOpenCollarApp.ts`](../src/hooks/useOpenCollarApp.ts)

This is the frontend state bridge. It:

- loads the initial app snapshot from Tauri
- subscribes to state updates
- exposes run actions back to the UI

### [`src/lib/types.ts`](../src/lib/types.ts)

Defines the TypeScript-side runtime shapes:

- run state
- step state
- mode
- events
- observations
- artifacts

## Tauri / Rust

### [`src-tauri/src/main.rs`](../src-tauri/src/main.rs)

This is the orchestration layer.

It:

- boots the app
- opens the database
- spawns the worker
- defines Tauri commands
- handles worker messages
- emits full snapshots to the UI

### [`src-tauri/src/db.rs`](../src-tauri/src/db.rs)

Contains the persistence logic:

- schema creation
- snapshot loading
- step/event/observation/artifact inserts
- run upserts

### [`src-tauri/src/worker.rs`](../src-tauri/src/worker.rs)

Handles the Python process lifecycle and stdin/stdout piping.

The worker protocol is line-oriented JSON, so Rust only needs to:

- write envelopes
- read envelopes
- forward failures into the event stream

## Python worker

### [`worker/open_collar/runtime.py`](../worker/open_collar/runtime.py)

The heart of the agent runtime.

It:

- tracks run contexts
- processes inbound worker commands
- gates execution by mode
- executes step groups
- emits structured events

### [`worker/open_collar/planner.py`](../worker/open_collar/planner.py)

Contains two planning paths:

- a deterministic Notepad++ plan for the MVP
- a model-backed planner path for future tasks

### [`worker/open_collar/tools.py`](../worker/open_collar/tools.py)

Defines the allowed action surface.

This file is important because it is the safety boundary between “what the model wants” and “what the machine can do.”

Current tool list:

- `create_folder(path)`
- `open_application(app)`
- `wait_for_window(title_contains, timeout_ms)`
- `focus_window(title_contains)`
- `click_element(window, selector)`
- `click_coordinates(x, y)`
- `type_text(text)`
- `press_keys(keys)`
- `read_window_text(title_contains)`
- `save_file_as(path)`
- `capture_screenshot()`
- `verify_path_exists(path)`
- `get_active_window()`
- `list_window_elements(title_contains)`

### [`worker/open_collar/model_client.py`](../worker/open_collar/model_client.py)

Wraps the planning-model integrations and asks the selected model for strict JSON planning output.

Current focus:

- Gemini model selection per run
- transient user-entered API key handling
- strict JSON plan extraction before execution

The worker never allows this response to directly execute code. It is converted into step records and still must pass the tool whitelist.

## Tests

### Frontend

- [`src/App.test.tsx`](../src/App.test.tsx): smoke test for the control-center shell

### Worker

- [`worker/tests/test_planner.py`](../worker/tests/test_planner.py): deterministic plan generation
- [`worker/tests/test_runtime.py`](../worker/tests/test_runtime.py): runtime flow and fake-tool execution
- [`worker/tests/e2e/test_notepadpp_scenario.py`](../worker/tests/e2e/test_notepadpp_scenario.py): fake E2E path
- [`worker/tests/integration/test_windows_tools.py`](../worker/tests/integration/test_windows_tools.py): Windows-only tool presence check
