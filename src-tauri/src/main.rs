mod db;
mod logging;
mod models;
mod worker;

use std::{
    env,
    fs,
    path::PathBuf,
    sync::{Arc, Mutex},
};

use db::Database;
use models::{
    now_timestamp, AppSnapshot, ApprovalRequest, ArtifactPayload, ArtifactRecord, EventPayload,
    EventRecord, ObservationPayload, ObservationRecord, PlanCreatedPayload, RunRecord,
    RunUpdatedPayload, StartRunInput, StepRecord, StepUpdatedPayload, WorkerEnvelope,
};
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager, State};
use uuid::Uuid;
use worker::{spawn_worker, WorkerManager};

const STATE_EVENT: &str = "open-collar://state";

struct RuntimeState {
    snapshot: Mutex<AppSnapshot>,
    database: Mutex<Database>,
    worker: Mutex<WorkerManager>,
}

impl RuntimeState {
    fn emit_snapshot(&self, app: &AppHandle) -> Result<(), String> {
        let snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Snapshot lock poisoned.".to_string())?
            .clone();
        app.emit(STATE_EVENT, snapshot).map_err(|error| error.to_string())
    }
}

#[tauri::command]
fn get_app_snapshot(state: State<'_, Arc<RuntimeState>>) -> Result<AppSnapshot, String> {
    state
        .snapshot
        .lock()
        .map_err(|_| "Snapshot lock poisoned.".to_string())
        .map(|snapshot| snapshot.clone())
}

#[tauri::command]
fn start_run(
    app: AppHandle,
    state: State<'_, Arc<RuntimeState>>,
    input: StartRunInput,
) -> Result<String, String> {
    let run_id = Uuid::new_v4().to_string();
    let timestamp = now_timestamp();
    let prompt = input.prompt.clone();
    let model_provider = "gemini".to_string();
    let model_name = "gemini-2.5-pro".to_string();
    let api_key = input.api_key.clone();
    let run = RunRecord {
        id: run_id.clone(),
        prompt: prompt.clone(),
        mode: "auto".to_string(),
        model_provider: model_provider.clone(),
        model_name: model_name.clone(),
        state: "queued".to_string(),
        summary: Some("Planning the task.".to_string()),
        error: None,
        created_at: timestamp.clone(),
        updated_at: timestamp.clone(),
        started_at: None,
        completed_at: None,
        pending_approval: None,
        steps: Vec::new(),
        events: Vec::new(),
        observations: Vec::new(),
        artifacts: Vec::new(),
    };

    {
        let mut snapshot = state
            .snapshot
            .lock()
            .map_err(|_| "Snapshot lock poisoned.".to_string())?;
        snapshot.selected_run_id = Some(run_id.clone());
        snapshot.worker_status = "busy".to_string();
        snapshot.runs.insert(0, run.clone());
    }

    state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .save_run(&run)?;

    log_event(
        &state,
        &run_id,
        EventPayload {
            level: "info".to_string(),
            event_type: "agent_started".to_string(),
            message: "The agent is reviewing your request and preparing a plan.".to_string(),
            payload: Some(json!({
                "prompt": prompt.clone(),
                "modelProvider": model_provider.clone(),
                "modelName": model_name.clone()
            })),
        },
    )?;

    let envelope = WorkerEnvelope {
        message_type: "start_run".to_string(),
        run_id: Some(run_id.clone()),
        timestamp: now_timestamp(),
        request_id: None,
        payload: json!({
            "prompt": prompt,
            "modelConfig": {
                "provider": model_provider,
                "modelName": model_name,
                "apiKey": api_key
            }
        }),
    };

    state
        .worker
        .lock()
        .map_err(|_| "Worker lock poisoned.".to_string())?
        .send(&envelope)?;

    state.emit_snapshot(&app)?;
    Ok(run_id)
}

#[tauri::command]
fn cancel_run(app: AppHandle, state: State<'_, Arc<RuntimeState>>, run_id: String) -> Result<(), String> {
    send_worker_control(&app, &state, "cancel_run", run_id, json!({}))
}

fn send_worker_control(
    app: &AppHandle,
    state: &State<'_, Arc<RuntimeState>>,
    message_type: &str,
    run_id: String,
    payload: serde_json::Value,
) -> Result<(), String> {
    let envelope = WorkerEnvelope {
        message_type: message_type.to_string(),
        run_id: Some(run_id.clone()),
        timestamp: now_timestamp(),
        request_id: None,
        payload,
    };

    state
        .worker
        .lock()
        .map_err(|_| "Worker lock poisoned.".to_string())?
        .send(&envelope)?;

    log_event(
        state,
        &run_id,
        EventPayload {
            level: "info".to_string(),
            event_type: message_type.to_string(),
            message: "Stop requested. The agent is stopping now.".to_string(),
            payload: None,
        },
    )?;

    state.emit_snapshot(app)
}

fn with_run_mut<F>(state: &Arc<RuntimeState>, run_id: &str, mutator: F) -> Result<(), String>
where
    F: FnOnce(&mut RunRecord) -> Result<(), String>,
{
    let run = {
        let mut snapshot = state
            .snapshot
            .lock()
            .map_err(|_| "Snapshot lock poisoned.".to_string())?;
        let run = snapshot
            .runs
            .iter_mut()
            .find(|candidate| candidate.id == run_id)
            .ok_or_else(|| format!("Unknown run id {run_id}"))?;
        mutator(run)?;
        run.clone()
    };

    state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .save_run(&run)
}

fn log_event(state: &Arc<RuntimeState>, run_id: &str, payload: EventPayload) -> Result<(), String> {
    let created_at = now_timestamp();
    let mut record = EventRecord {
        id: 0,
        run_id: run_id.to_string(),
        level: payload.level,
        event_type: payload.event_type,
        message: payload.message,
        payload: payload.payload,
        created_at,
    };

    let inserted_id = state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .insert_event(&record)?;
    record.id = inserted_id;

    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Snapshot lock poisoned.".to_string())?;
    if let Some(run) = snapshot.runs.iter_mut().find(|candidate| candidate.id == run_id) {
        run.events.push(record);
        run.updated_at = now_timestamp();
    }
    Ok(())
}

fn record_observation(
    state: &Arc<RuntimeState>,
    run_id: &str,
    payload: ObservationPayload,
) -> Result<(), String> {
    let created_at = now_timestamp();
    let mut record = ObservationRecord {
        id: 0,
        run_id: run_id.to_string(),
        kind: payload.kind,
        content: payload.content,
        payload: payload.payload,
        created_at,
    };

    let inserted_id = state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .insert_observation(&record)?;
    record.id = inserted_id;

    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Snapshot lock poisoned.".to_string())?;
    if let Some(run) = snapshot.runs.iter_mut().find(|candidate| candidate.id == run_id) {
        run.observations.push(record);
        run.updated_at = now_timestamp();
    }
    Ok(())
}

fn record_artifact(state: &Arc<RuntimeState>, run_id: &str, payload: ArtifactPayload) -> Result<(), String> {
    let created_at = now_timestamp();
    let mut record = ArtifactRecord {
        id: 0,
        run_id: run_id.to_string(),
        kind: payload.kind,
        label: payload.label,
        path: payload.path,
        payload: payload.payload,
        created_at,
    };

    let inserted_id = state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .insert_artifact(&record)?;
    record.id = inserted_id;

    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Snapshot lock poisoned.".to_string())?;
    if let Some(run) = snapshot.runs.iter_mut().find(|candidate| candidate.id == run_id) {
        run.artifacts.push(record);
        run.updated_at = now_timestamp();
    }
    Ok(())
}

fn upsert_step(state: &Arc<RuntimeState>, step: StepRecord) -> Result<(), String> {
    state
        .database
        .lock()
        .map_err(|_| "Database lock poisoned.".to_string())?
        .save_step(&step)?;

    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Snapshot lock poisoned.".to_string())?;

    if let Some(run) = snapshot.runs.iter_mut().find(|candidate| candidate.id == step.run_id) {
        if let Some(existing) = run.steps.iter_mut().find(|candidate| candidate.id == step.id) {
            *existing = step;
        } else {
            run.steps.push(step);
            run.steps
                .sort_by_key(|candidate| (candidate.group_index, candidate.step_index));
        }
        run.updated_at = now_timestamp();
    }

    Ok(())
}

fn handle_worker_message(app: &AppHandle, state: Arc<RuntimeState>, line: String) -> Result<(), String> {
    let envelope: WorkerEnvelope = serde_json::from_str(&line).map_err(|error| error.to_string())?;
    let run_id = envelope.run_id.clone();

    match envelope.message_type.as_str() {
        "worker_ready" => {
            logging::log("INFO", "worker reported ready");
            let mut snapshot = state
                .snapshot
                .lock()
                .map_err(|_| "Snapshot lock poisoned.".to_string())?;
            snapshot.worker_status = "ready".to_string();
        }
        "plan_created" => {
            let run_id = run_id.ok_or_else(|| "plan_created missing run_id".to_string())?;
            let payload: PlanCreatedPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;

            for step in payload.steps {
                upsert_step(&state, step)?;
            }

            with_run_mut(&state, &run_id, |run| {
                run.state = "running".to_string();
                run.summary = Some("Plan ready. The agent is starting work.".to_string());
                run.updated_at = now_timestamp();
                Ok(())
            })?;
        }
        "approval_requested" => {
            let run_id = run_id.ok_or_else(|| "approval_requested missing run_id".to_string())?;
            let payload: ApprovalRequest =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            with_run_mut(&state, &run_id, |run| {
                run.pending_approval = Some(payload);
                run.updated_at = now_timestamp();
                Ok(())
            })?;
        }
        "step_updated" => {
            let payload: StepUpdatedPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            upsert_step(&state, payload.step)?;
        }
        "event_logged" => {
            let run_id = run_id.ok_or_else(|| "event_logged missing run_id".to_string())?;
            let payload: EventPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            log_event(&state, &run_id, payload)?;
        }
        "observation_recorded" => {
            let run_id = run_id.ok_or_else(|| "observation_recorded missing run_id".to_string())?;
            let payload: ObservationPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            record_observation(&state, &run_id, payload)?;
        }
        "artifact_created" => {
            let run_id = run_id.ok_or_else(|| "artifact_created missing run_id".to_string())?;
            let payload: ArtifactPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            record_artifact(&state, &run_id, payload)?;
        }
        "run_updated" => {
            let run_id = run_id.ok_or_else(|| "run_updated missing run_id".to_string())?;
            let payload: RunUpdatedPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            with_run_mut(&state, &run_id, |run| {
                run.state = payload.state;
                run.summary = payload.summary;
                run.error = payload.error;
                run.started_at = payload.started_at;
                run.completed_at = payload.completed_at;
                run.pending_approval = payload.pending_approval;
                run.updated_at = now_timestamp();
                Ok(())
            })?;
        }
        "worker_error" => {
            let run_id = run_id.unwrap_or_else(|| "system".to_string());
            let payload: EventPayload =
                serde_json::from_value(envelope.payload).map_err(|error| error.to_string())?;
            logging::log(
                "ERROR",
                format!("worker_error event [{}]: {}", payload.event_type, payload.message),
            );
            log_event(&state, &run_id, payload)?;
            let mut snapshot = state
                .snapshot
                .lock()
                .map_err(|_| "Snapshot lock poisoned.".to_string())?;
            snapshot.worker_status = "error".to_string();
        }
        other => {
            return Err(format!("Unknown worker message type: {other}"));
        }
    }

    state.emit_snapshot(app)
}

fn resolve_app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(override_dir) = env::var("OPEN_COLLAR_APP_DATA_DIR") {
        return Ok(PathBuf::from(override_dir));
    }

    app.path().app_data_dir().map_err(|error| error.to_string())
}

fn build_runtime(app: &AppHandle) -> Result<Arc<RuntimeState>, String> {
    let app_dir = resolve_app_data_dir(app)?;
    fs::create_dir_all(&app_dir).map_err(|error| error.to_string())?;
    let database = Database::open(&app_dir.join("open-collar.sqlite"))?;
    let snapshot = database.load_snapshot()?;

    let runtime = Arc::new(RuntimeState {
        snapshot: Mutex::new(snapshot),
        database: Mutex::new(database),
        worker: Mutex::new(WorkerManager::unavailable()),
    });

    {
        let app_handle = app.clone();
        let runtime_clone = runtime.clone();
        let stderr_runtime = runtime.clone();
        let worker = spawn_worker(
            move |line| {
                if let Err(error) = handle_worker_message(&app_handle, runtime_clone.clone(), line) {
                    logging::log("ERROR", format!("worker bridge error: {error}"));
                    let _ = log_event(
                        &runtime_clone,
                        "system",
                        EventPayload {
                            level: "error".to_string(),
                            event_type: "worker_bridge_error".to_string(),
                            message: error,
                            payload: None,
                        },
                    );
                }
            },
            move |line| {
                logging::log("ERROR", format!("worker stderr bridged into timeline: {line}"));
                let _ = log_event(
                    &stderr_runtime,
                    "system",
                    EventPayload {
                        level: "error".to_string(),
                        event_type: "worker_stderr".to_string(),
                        message: line,
                        payload: None,
                    },
                );
            },
        );

        let mut worker_slot = runtime
            .worker
            .lock()
            .map_err(|_| "Worker lock poisoned.".to_string())?;

        match worker {
            Ok(handle) => {
                logging::log("INFO", "python worker bridge initialized successfully");
                *worker_slot = handle;
            }
            Err(error) => {
                logging::log("ERROR", format!("worker launch failed: {error}"));
                *worker_slot = WorkerManager::unavailable();
                let mut snapshot = runtime
                    .snapshot
                    .lock()
                    .map_err(|_| "Snapshot lock poisoned.".to_string())?;
                snapshot.worker_status = "error".to_string();
                drop(snapshot);
                log_event(
                    &runtime,
                    "system",
                    EventPayload {
                        level: "error".to_string(),
                        event_type: "worker_launch_failed".to_string(),
                        message: error,
                        payload: None,
                    },
                )?;
            }
        }
    }

    Ok(runtime)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let fallback_log_dir = resolve_app_data_dir(&app.handle())?.join("logs");
            let log_file = logging::init_logging(fallback_log_dir)?;
            logging::log("INFO", format!("open collar startup; log file {}", log_file.display()));
            let runtime = build_runtime(&app.handle())?;
            app.manage(runtime.clone());
            runtime.emit_snapshot(&app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_app_snapshot,
            start_run,
            cancel_run
        ])
        .run(tauri::generate_context!())
        .expect("error while running open collar");
}
