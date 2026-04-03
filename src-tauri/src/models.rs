use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSnapshot {
    pub worker_status: String,
    pub selected_run_id: Option<String>,
    pub runs: Vec<RunRecord>,
}

impl Default for AppSnapshot {
    fn default() -> Self {
        Self {
            worker_status: "offline".to_string(),
            selected_run_id: None,
            runs: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ApprovalRequest {
    pub group_index: usize,
    pub reason: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunRecord {
    pub id: String,
    pub prompt: String,
    pub mode: String,
    pub model_provider: String,
    pub model_name: String,
    pub state: String,
    pub summary: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub pending_approval: Option<ApprovalRequest>,
    pub steps: Vec<StepRecord>,
    pub events: Vec<EventRecord>,
    pub observations: Vec<ObservationRecord>,
    pub artifacts: Vec<ArtifactRecord>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StepRecord {
    pub id: String,
    pub run_id: String,
    pub title: String,
    pub goal: String,
    pub group_index: usize,
    pub step_index: usize,
    pub tool_name: Option<String>,
    pub verification_target: Option<String>,
    pub state: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub updated_at: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EventRecord {
    pub id: i64,
    pub run_id: String,
    pub level: String,
    pub event_type: String,
    pub message: String,
    pub payload: Option<Value>,
    pub created_at: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ObservationRecord {
    pub id: i64,
    pub run_id: String,
    pub kind: String,
    pub content: String,
    pub payload: Option<Value>,
    pub created_at: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactRecord {
    pub id: i64,
    pub run_id: String,
    pub kind: String,
    pub label: String,
    pub path: String,
    pub payload: Option<Value>,
    pub created_at: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StartRunInput {
    pub prompt: String,
    pub api_key: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlanCreatedPayload {
    pub steps: Vec<StepRecord>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StepUpdatedPayload {
    pub step: StepRecord,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EventPayload {
    pub level: String,
    pub event_type: String,
    pub message: String,
    pub payload: Option<Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ObservationPayload {
    pub kind: String,
    pub content: String,
    pub payload: Option<Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactPayload {
    pub kind: String,
    pub label: String,
    pub path: String,
    pub payload: Option<Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunUpdatedPayload {
    pub state: String,
    pub summary: Option<String>,
    pub error: Option<String>,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub pending_approval: Option<ApprovalRequest>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkerEnvelope {
    #[serde(rename = "type")]
    pub message_type: String,
    pub run_id: Option<String>,
    pub timestamp: String,
    pub request_id: Option<String>,
    pub payload: Value,
}

pub fn now_timestamp() -> String {
    Utc::now().to_rfc3339()
}
