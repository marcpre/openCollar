from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Envelope:
    message_type: str
    run_id: str | None
    timestamp: str
    payload: dict[str, Any]
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.message_type,
            "runId": self.run_id,
            "timestamp": self.timestamp,
            "requestId": self.request_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Envelope":
        return cls(
            message_type=str(raw.get("type", "")),
            run_id=raw.get("runId"),
            timestamp=str(raw.get("timestamp", now_timestamp())),
            request_id=raw.get("requestId"),
            payload=dict(raw.get("payload") or {}),
        )


@dataclass(slots=True)
class ApprovalRequest:
    group_index: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "groupIndex": self.group_index,
            "reason": self.reason,
        }


@dataclass(slots=True)
class StepRecord:
    id: str
    run_id: str
    title: str
    goal: str
    group_index: int
    step_index: int
    tool_name: str | None
    verification_target: str | None
    state: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str = field(default_factory=now_timestamp)
    tool_args: dict[str, Any] = field(default_factory=dict)
    fallback_note: str | None = None

    def for_transport(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("tool_args")
        payload.pop("fallback_note")
        return payload


@dataclass(slots=True)
class RunPlan:
    step_groups: list[list[StepRecord]]
    summary: str

    @property
    def flattened_steps(self) -> list[StepRecord]:
        return [step for group in self.step_groups for step in group]
