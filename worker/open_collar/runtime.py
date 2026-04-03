from __future__ import annotations

import json
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from .browser import BrowserAutomation
from .model_client import create_model_client
from .planner import Planner
from .schemas import Envelope, RunPlan, StepRecord, now_timestamp
from .tools import ToolContext, ToolExecutionError, ToolRegistry


@dataclass(slots=True)
class RunContext:
    run_id: str
    prompt: str
    model_provider: str
    model_name: str
    model_config: dict[str, Any]
    plan: RunPlan | None = None
    state: str = "queued"
    current_group_index: int = 0
    cancelled: bool = False
    worker_thread: threading.Thread | None = None


class OutputChannel:
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def send(self, message_type: str, run_id: str | None, payload: dict[str, Any]) -> None:
        envelope = Envelope(
            message_type=message_type,
            run_id=run_id,
            timestamp=now_timestamp(),
            payload=payload,
        )
        line = json.dumps(envelope.to_dict(), ensure_ascii=False)
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()


class WorkerRuntime:
    def __init__(self, output: OutputChannel, tool_registry: ToolRegistry | None = None) -> None:
        app_data_root = self._resolve_app_data_dir()
        context = ToolContext(artifact_dir=app_data_root / "artifacts")
        self.output = output
        self.browser = BrowserAutomation()
        self.tool_registry = tool_registry or ToolRegistry(context)
        self._lock = threading.Lock()
        self._runs: dict[str, RunContext] = {}

    def _resolve_app_data_dir(self) -> Path:
        from os import getenv

        configured = getenv("OPEN_COLLAR_APP_DATA_DIR")
        if configured:
            root = Path(configured)
        elif sys.platform.startswith("win"):
            root = Path.home() / "AppData" / "Local" / "open-collar"
        else:
            root = Path.home() / ".local" / "share" / "open-collar"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def boot(self) -> None:
        self.output.send("worker_ready", None, {"status": "ready"})

    def handle_envelope(self, envelope: Envelope) -> None:
        if envelope.message_type == "start_run":
            self._start_run(envelope)
        elif envelope.message_type == "cancel_run":
            self._cancel_run(envelope)
        elif envelope.message_type == "shutdown":
            return
        else:
            raise RuntimeError(f"Unknown message type {envelope.message_type!r}.")

    def _start_run(self, envelope: Envelope) -> None:
        run_id = envelope.run_id
        if not run_id:
            raise RuntimeError("start_run is missing run_id.")

        prompt = str(envelope.payload.get("prompt", ""))
        model_config = dict(envelope.payload.get("modelConfig") or {})
        model_provider = str(model_config.get("provider") or "gemini")
        model_name = str(model_config.get("modelName") or "gemini-2.5-pro")
        context = RunContext(
            run_id=run_id,
            prompt=prompt,
            model_provider=model_provider,
            model_name=model_name,
            model_config=model_config,
        )

        with self._lock:
            self._runs[run_id] = context

        self.output.send(
            "run_updated",
            run_id,
            {
                "state": "queued",
                "summary": "Planning the task.",
                "error": None,
                "startedAt": now_timestamp(),
                "completedAt": None,
                "pendingApproval": None,
            },
        )
        self._spawn_worker(context, self._plan_and_run)

    def _cancel_run(self, envelope: Envelope) -> None:
        context = self._require_context(envelope.run_id)
        context.cancelled = True
        self.output.send(
            "event_logged",
            context.run_id,
            {
                "level": "warn",
                "eventType": "run_cancelled",
                "message": "The run was stopped by the user.",
                "payload": None,
            },
        )
        self.output.send(
            "run_updated",
            context.run_id,
            {
                "state": "cancelled",
                "summary": "Run stopped by the user.",
                "error": None,
                "startedAt": None,
                "completedAt": now_timestamp(),
                "pendingApproval": None,
            },
        )

    def _spawn_execution(self, context: RunContext) -> None:
        self._spawn_worker(context, self._run_groups)

    def _spawn_worker(self, context: RunContext, target: Any) -> None:
        if context.worker_thread and context.worker_thread.is_alive():
            return
        thread = threading.Thread(target=target, args=(context.run_id,), daemon=True)
        context.worker_thread = thread
        thread.start()

    def _plan_and_run(self, run_id: str) -> None:
        try:
            context = self._require_context(run_id)
            planner = Planner(model_client=create_model_client(context.model_config))
            plan = planner.build_plan(
                run_id=run_id,
                prompt=context.prompt,
                tool_names=self.tool_registry.tool_names,
            )
            context.plan = plan

            if context.cancelled:
                return

            self.output.send("plan_created", run_id, {"steps": [step.for_transport() for step in plan.flattened_steps]})
            self.output.send(
                "run_updated",
                run_id,
                {
                    "state": "running",
                    "summary": "Plan ready. The agent is starting work.",
                    "error": None,
                    "startedAt": None,
                    "completedAt": None,
                    "pendingApproval": None,
                },
            )
            self.output.send(
                "event_logged",
                run_id,
                {
                    "level": "info",
                    "eventType": "planner_summary",
                    "message": plan.summary,
                    "payload": {
                        "groups": len(plan.step_groups),
                        "modelProvider": context.model_provider,
                        "modelName": context.model_name,
                    },
                },
            )
            self._run_groups(run_id)
        except Exception as error:  # pragma: no cover - defensive event path
            self.output.send(
                "run_updated",
                run_id,
                {
                    "state": "failed",
                    "summary": "Run failed during planning.",
                    "error": f"Planning failed: {error}",
                    "startedAt": None,
                    "completedAt": now_timestamp(),
                    "pendingApproval": None,
                },
            )
            self.output.send(
                "worker_error",
                run_id,
                {
                    "level": "error",
                    "eventType": "execution_failed",
                    "message": traceback.format_exc(),
                    "payload": None,
                },
            )

    def _run_groups(self, run_id: str) -> None:
        try:
            context = self._require_context(run_id)
            if context.plan is None:
                raise RuntimeError("Planning did not produce a run plan.")

            while context.current_group_index < len(context.plan.step_groups):
                if context.cancelled:
                    return

                self._execute_group(context)
                context.current_group_index += 1

            if context.cancelled:
                return

            self.output.send(
                "run_updated",
                run_id,
                {
                    "state": "completed",
                    "summary": "Run completed with verification artifacts recorded.",
                    "error": None,
                    "startedAt": None,
                    "completedAt": now_timestamp(),
                    "pendingApproval": None,
                },
            )
        except Exception as error:  # pragma: no cover - defensive event path
            self.output.send(
                "run_updated",
                run_id,
                {
                    "state": "failed",
                    "summary": "Run failed during execution.",
                    "error": str(error),
                    "startedAt": None,
                    "completedAt": now_timestamp(),
                    "pendingApproval": None,
                },
            )
            self.output.send(
                "worker_error",
                run_id,
                {
                    "level": "error",
                    "eventType": "execution_failed",
                    "message": traceback.format_exc(),
                    "payload": None,
                },
            )

    def _execute_group(self, context: RunContext) -> None:
        if context.plan is None:
            raise RuntimeError("Planning did not produce a run plan.")
        group = context.plan.step_groups[context.current_group_index]
        for step in group:
            if context.cancelled:
                return
            self._execute_step(context, step)

    def _execute_step(self, context: RunContext, step: StepRecord) -> None:
        step.state = "running"
        step.started_at = now_timestamp()
        step.updated_at = now_timestamp()
        self.output.send("step_updated", context.run_id, {"step": step.for_transport()})
        self.output.send(
            "event_logged",
            context.run_id,
            {
                "level": "info",
                "eventType": "step_started",
                "message": f"Working on: {step.title}. {step.goal}",
                "payload": {"stepId": step.id, "toolName": step.tool_name},
            },
        )
        self.output.send(
            "run_updated",
            context.run_id,
            {
                "state": "running",
                "summary": step.goal,
                "error": None,
                "startedAt": None,
                "completedAt": None,
                "pendingApproval": None,
            },
        )

        try:
            result = self.tool_registry.execute(step.tool_name or "", step.tool_args)
        except ToolExecutionError as error:
            step.state = "failed"
            step.updated_at = now_timestamp()
            self.output.send("step_updated", context.run_id, {"step": step.for_transport()})
            self.output.send(
                "event_logged",
                context.run_id,
                {
                    "level": "error",
                    "eventType": "tool_error",
                    "message": f'The plan for "{step.title}" failed. {error}',
                    "payload": {"toolName": step.tool_name, "code": error.code, "stepTitle": step.title},
                },
            )
            raise

        if context.cancelled:
            return

        step.state = "done"
        step.completed_at = now_timestamp()
        step.updated_at = now_timestamp()
        self.output.send("step_updated", context.run_id, {"step": step.for_transport()})
        self.output.send(
            "event_logged",
            context.run_id,
            {
                "level": "info",
                "eventType": "step_completed",
                "message": f"Completed: {step.title}.",
                "payload": result.data,
            },
        )

        if step.tool_name == "focus_window":
            active_window = self.tool_registry.execute("get_active_window", {})
            self.output.send(
                "observation_recorded",
                context.run_id,
                {
                    "kind": "active_window",
                    "content": active_window.data.get("title", "Unknown active window"),
                    "payload": active_window.data,
                },
            )
        elif step.tool_name == "verify_path_exists":
            self.output.send(
                "observation_recorded",
                context.run_id,
                {
                    "kind": "verification",
                    "content": f"Verified path exists: {result.data['path']}",
                    "payload": result.data,
                },
            )
        elif step.tool_name == "capture_screenshot":
            self.output.send(
                "artifact_created",
                context.run_id,
                {
                    "kind": "screenshot",
                    "label": "Final desktop screenshot",
                    "path": result.data["path"],
                    "payload": result.data,
                },
            )

    def _require_context(self, run_id: str | None) -> RunContext:
        if not run_id:
            raise RuntimeError("Missing run_id.")
        with self._lock:
            if run_id not in self._runs:
                raise RuntimeError(f"Unknown run {run_id!r}.")
            return self._runs[run_id]


def main() -> None:
    output = OutputChannel(sys.stdout)
    runtime = WorkerRuntime(output=output)
    runtime.boot()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            envelope = Envelope.from_dict(json.loads(line))
            runtime.handle_envelope(envelope)
        except Exception as error:  # pragma: no cover - safety net around stdin loop
            output.send(
                "worker_error",
                envelope.run_id if "envelope" in locals() else None,
                {
                    "level": "error",
                    "eventType": "worker_loop_error",
                    "message": str(error),
                    "payload": {"traceback": traceback.format_exc()},
                },
            )
