use std::path::Path;

use rusqlite::{params, Connection};
use serde_json::Value;

use crate::models::{
    AppSnapshot, ApprovalRequest, ArtifactRecord, EventRecord, ObservationRecord, RunRecord,
    StepRecord,
};

pub struct Database {
    connection: Connection,
}

impl Database {
    pub fn open(path: &Path) -> Result<Self, String> {
        let connection = Connection::open(path).map_err(|error| error.to_string())?;
        let database = Self { connection };
        database.create_tables()?;
        Ok(database)
    }

    fn create_tables(&self) -> Result<(), String> {
        self.connection
            .execute_batch(
                r#"
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    model_provider TEXT NOT NULL DEFAULT 'deterministic',
                    model_name TEXT NOT NULL DEFAULT 'deterministic-mvp',
                    state TEXT NOT NULL,
                    summary TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    pending_approval TEXT
                );

                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    group_index INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    tool_name TEXT,
                    verification_target TEXT,
                    state TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                );
                "#,
            )
            .map_err(|error| error.to_string())?;

        self.ensure_column("runs", "model_provider", "TEXT NOT NULL DEFAULT 'deterministic'")?;
        self.ensure_column("runs", "model_name", "TEXT NOT NULL DEFAULT 'deterministic-mvp'")?;

        Ok(())
    }

    fn ensure_column(&self, table_name: &str, column_name: &str, definition: &str) -> Result<(), String> {
        let pragma = format!("PRAGMA table_info({table_name})");
        let mut statement = self
            .connection
            .prepare(&pragma)
            .map_err(|error| error.to_string())?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(1))
            .map_err(|error| error.to_string())?;

        let mut exists = false;
        for row in rows {
            if row.map_err(|error| error.to_string())? == column_name {
                exists = true;
                break;
            }
        }

        if !exists {
            let alter = format!("ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}");
            self.connection
                .execute(&alter, [])
                .map_err(|error| error.to_string())?;
        }

        Ok(())
    }

    pub fn load_snapshot(&self) -> Result<AppSnapshot, String> {
        let mut snapshot = AppSnapshot::default();

        let mut run_statement = self
            .connection
            .prepare(
                r#"
                SELECT id, prompt, mode, model_provider, model_name, state, summary, error, created_at, updated_at, started_at, completed_at, pending_approval
                FROM runs
                ORDER BY created_at DESC
                "#,
            )
            .map_err(|error| error.to_string())?;

        let run_rows = run_statement
            .query_map([], |row| {
                let pending_approval_raw: Option<String> = row.get(12)?;
                let pending_approval = pending_approval_raw
                    .as_deref()
                    .and_then(|value| serde_json::from_str::<ApprovalRequest>(value).ok());

                Ok(RunRecord {
                    id: row.get(0)?,
                    prompt: row.get(1)?,
                    mode: row.get(2)?,
                    model_provider: row.get(3)?,
                    model_name: row.get(4)?,
                    state: row.get(5)?,
                    summary: row.get(6)?,
                    error: row.get(7)?,
                    created_at: row.get(8)?,
                    updated_at: row.get(9)?,
                    started_at: row.get(10)?,
                    completed_at: row.get(11)?,
                    pending_approval,
                    steps: Vec::new(),
                    events: Vec::new(),
                    observations: Vec::new(),
                    artifacts: Vec::new(),
                })
            })
            .map_err(|error| error.to_string())?;

        for run_row in run_rows {
            let mut run = run_row.map_err(|error| error.to_string())?;
            run.steps = self.load_steps(&run.id)?;
            run.events = self.load_events(&run.id)?;
            run.observations = self.load_observations(&run.id)?;
            run.artifacts = self.load_artifacts(&run.id)?;
            snapshot.runs.push(run);
        }

        snapshot.selected_run_id = snapshot.runs.first().map(|run| run.id.clone());
        Ok(snapshot)
    }

    fn load_steps(&self, run_id: &str) -> Result<Vec<StepRecord>, String> {
        let mut statement = self
            .connection
            .prepare(
                r#"
                SELECT id, run_id, title, goal, group_index, step_index, tool_name, verification_target, state, started_at, completed_at, updated_at
                FROM steps
                WHERE run_id = ?1
                ORDER BY group_index ASC, step_index ASC
                "#,
            )
            .map_err(|error| error.to_string())?;

        let rows = statement
            .query_map(params![run_id], |row| {
                Ok(StepRecord {
                    id: row.get(0)?,
                    run_id: row.get(1)?,
                    title: row.get(2)?,
                    goal: row.get(3)?,
                    group_index: row.get::<_, i64>(4)? as usize,
                    step_index: row.get::<_, i64>(5)? as usize,
                    tool_name: row.get(6)?,
                    verification_target: row.get(7)?,
                    state: row.get(8)?,
                    started_at: row.get(9)?,
                    completed_at: row.get(10)?,
                    updated_at: row.get(11)?,
                })
            })
            .map_err(|error| error.to_string())?;

        rows.map(|row| row.map_err(|error| error.to_string()))
            .collect()
    }

    fn load_events(&self, run_id: &str) -> Result<Vec<EventRecord>, String> {
        let mut statement = self
            .connection
            .prepare(
                r#"
                SELECT id, run_id, level, event_type, message, payload, created_at
                FROM events
                WHERE run_id = ?1
                ORDER BY id ASC
                "#,
            )
            .map_err(|error| error.to_string())?;

        let rows = statement
            .query_map(params![run_id], |row| {
                let payload_raw: Option<String> = row.get(5)?;
                Ok(EventRecord {
                    id: row.get(0)?,
                    run_id: row.get(1)?,
                    level: row.get(2)?,
                    event_type: row.get(3)?,
                    message: row.get(4)?,
                    payload: payload_raw
                        .as_deref()
                        .and_then(|value| serde_json::from_str::<Value>(value).ok()),
                    created_at: row.get(6)?,
                })
            })
            .map_err(|error| error.to_string())?;

        rows.map(|row| row.map_err(|error| error.to_string()))
            .collect()
    }

    fn load_observations(&self, run_id: &str) -> Result<Vec<ObservationRecord>, String> {
        let mut statement = self
            .connection
            .prepare(
                r#"
                SELECT id, run_id, kind, content, payload, created_at
                FROM observations
                WHERE run_id = ?1
                ORDER BY id ASC
                "#,
            )
            .map_err(|error| error.to_string())?;

        let rows = statement
            .query_map(params![run_id], |row| {
                let payload_raw: Option<String> = row.get(4)?;
                Ok(ObservationRecord {
                    id: row.get(0)?,
                    run_id: row.get(1)?,
                    kind: row.get(2)?,
                    content: row.get(3)?,
                    payload: payload_raw
                        .as_deref()
                        .and_then(|value| serde_json::from_str::<Value>(value).ok()),
                    created_at: row.get(5)?,
                })
            })
            .map_err(|error| error.to_string())?;

        rows.map(|row| row.map_err(|error| error.to_string()))
            .collect()
    }

    fn load_artifacts(&self, run_id: &str) -> Result<Vec<ArtifactRecord>, String> {
        let mut statement = self
            .connection
            .prepare(
                r#"
                SELECT id, run_id, kind, label, path, payload, created_at
                FROM artifacts
                WHERE run_id = ?1
                ORDER BY id ASC
                "#,
            )
            .map_err(|error| error.to_string())?;

        let rows = statement
            .query_map(params![run_id], |row| {
                let payload_raw: Option<String> = row.get(5)?;
                Ok(ArtifactRecord {
                    id: row.get(0)?,
                    run_id: row.get(1)?,
                    kind: row.get(2)?,
                    label: row.get(3)?,
                    path: row.get(4)?,
                    payload: payload_raw
                        .as_deref()
                        .and_then(|value| serde_json::from_str::<Value>(value).ok()),
                    created_at: row.get(6)?,
                })
            })
            .map_err(|error| error.to_string())?;

        rows.map(|row| row.map_err(|error| error.to_string()))
            .collect()
    }

    pub fn save_run(&self, run: &RunRecord) -> Result<(), String> {
        let pending_approval = run
            .pending_approval
            .as_ref()
            .map(|value| serde_json::to_string(value))
            .transpose()
            .map_err(|error| error.to_string())?;

        self.connection
            .execute(
                r#"
                INSERT INTO runs (id, prompt, mode, model_provider, model_name, state, summary, error, created_at, updated_at, started_at, completed_at, pending_approval)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)
                ON CONFLICT(id) DO UPDATE SET
                    prompt = excluded.prompt,
                    mode = excluded.mode,
                    model_provider = excluded.model_provider,
                    model_name = excluded.model_name,
                    state = excluded.state,
                    summary = excluded.summary,
                    error = excluded.error,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    pending_approval = excluded.pending_approval
                "#,
                params![
                    run.id,
                    run.prompt,
                    run.mode,
                    run.model_provider,
                    run.model_name,
                    run.state,
                    run.summary,
                    run.error,
                    run.created_at,
                    run.updated_at,
                    run.started_at,
                    run.completed_at,
                    pending_approval
                ],
            )
            .map_err(|error| error.to_string())?;

        Ok(())
    }

    pub fn save_step(&self, step: &StepRecord) -> Result<(), String> {
        self.connection
            .execute(
                r#"
                INSERT INTO steps (id, run_id, title, goal, group_index, step_index, tool_name, verification_target, state, started_at, completed_at, updated_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    goal = excluded.goal,
                    group_index = excluded.group_index,
                    step_index = excluded.step_index,
                    tool_name = excluded.tool_name,
                    verification_target = excluded.verification_target,
                    state = excluded.state,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    updated_at = excluded.updated_at
                "#,
                params![
                    step.id,
                    step.run_id,
                    step.title,
                    step.goal,
                    step.group_index as i64,
                    step.step_index as i64,
                    step.tool_name,
                    step.verification_target,
                    step.state,
                    step.started_at,
                    step.completed_at,
                    step.updated_at
                ],
            )
            .map_err(|error| error.to_string())?;

        Ok(())
    }

    pub fn insert_event(&self, event: &EventRecord) -> Result<i64, String> {
        let payload = event
            .payload
            .as_ref()
            .map(|value| serde_json::to_string(value))
            .transpose()
            .map_err(|error| error.to_string())?;

        self.connection
            .execute(
                r#"
                INSERT INTO events (run_id, level, event_type, message, payload, created_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                "#,
                params![
                    event.run_id,
                    event.level,
                    event.event_type,
                    event.message,
                    payload,
                    event.created_at
                ],
            )
            .map_err(|error| error.to_string())?;

        Ok(self.connection.last_insert_rowid())
    }

    pub fn insert_observation(&self, observation: &ObservationRecord) -> Result<i64, String> {
        let payload = observation
            .payload
            .as_ref()
            .map(|value| serde_json::to_string(value))
            .transpose()
            .map_err(|error| error.to_string())?;

        self.connection
            .execute(
                r#"
                INSERT INTO observations (run_id, kind, content, payload, created_at)
                VALUES (?1, ?2, ?3, ?4, ?5)
                "#,
                params![
                    observation.run_id,
                    observation.kind,
                    observation.content,
                    payload,
                    observation.created_at
                ],
            )
            .map_err(|error| error.to_string())?;

        Ok(self.connection.last_insert_rowid())
    }

    pub fn insert_artifact(&self, artifact: &ArtifactRecord) -> Result<i64, String> {
        let payload = artifact
            .payload
            .as_ref()
            .map(|value| serde_json::to_string(value))
            .transpose()
            .map_err(|error| error.to_string())?;

        self.connection
            .execute(
                r#"
                INSERT INTO artifacts (run_id, kind, label, path, payload, created_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                "#,
                params![
                    artifact.run_id,
                    artifact.kind,
                    artifact.label,
                    artifact.path,
                    payload,
                    artifact.created_at
                ],
            )
            .map_err(|error| error.to_string())?;

        Ok(self.connection.last_insert_rowid())
    }
}
