import json

from open_collar.planner import Planner
from open_collar.runtime import OutputChannel, WorkerRuntime
from open_collar.schemas import Envelope, now_timestamp
from open_collar.tools import FakeToolRegistry


class MemoryStream:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, content: str) -> None:
        self.lines.append(content)

    def flush(self) -> None:
        return


def _model_config() -> dict[str, str]:
    return {
        "provider": "gemini",
        "modelName": "gemini-2.5-pro",
        "apiKey": "test-key",
    }


def _fake_plan_payload() -> dict[str, object]:
    return {
        "summary": "Write the poem in Notepad++ and save it.",
        "stepGroups": [
            [
                {
                    "title": "Create folder",
                    "goal": "Create the destination folder.",
                    "toolName": "create_folder",
                    "toolArgs": {"path": "C:\\Users\\tester\\Desktop\\agent_test"},
                    "verificationTarget": "Folder exists",
                    "fallbackNote": None,
                }
            ],
            [
                {
                    "title": "Open Notepad++",
                    "goal": "Launch the editor.",
                    "toolName": "open_application",
                    "toolArgs": {"app": "notepad++"},
                    "verificationTarget": "Editor visible",
                    "fallbackNote": None,
                },
                {
                    "title": "Wait for window",
                    "goal": "Wait for the editor window.",
                    "toolName": "wait_for_window",
                    "toolArgs": {"title_contains": "Notepad++", "timeout_ms": 15000},
                    "verificationTarget": "Window visible",
                    "fallbackNote": None,
                },
                {
                    "title": "Focus window",
                    "goal": "Bring the editor to the foreground.",
                    "toolName": "focus_window",
                    "toolArgs": {"title_contains": "Notepad++"},
                    "verificationTarget": "Editor focused",
                    "fallbackNote": None,
                },
                {
                    "title": "Type poem",
                    "goal": "Enter the poem text.",
                    "toolName": "type_text",
                    "toolArgs": {"text": "poem"},
                    "verificationTarget": "Poem visible",
                    "fallbackNote": None,
                },
                {
                    "title": "Open save dialog",
                    "goal": "Trigger the save flow.",
                    "toolName": "press_keys",
                    "toolArgs": {"keys": "ctrl+s"},
                    "verificationTarget": "Save dialog open",
                    "fallbackNote": None,
                },
                {
                    "title": "Save file",
                    "goal": "Save the poem.",
                    "toolName": "save_file_as",
                    "toolArgs": {"path": "C:\\Users\\tester\\Desktop\\agent_test\\gedicht.txt"},
                    "verificationTarget": "File exists",
                    "fallbackNote": None,
                },
                {
                    "title": "Verify file",
                    "goal": "Confirm the file was written.",
                    "toolName": "verify_path_exists",
                    "toolArgs": {"path": "C:\\Users\\tester\\Desktop\\agent_test\\gedicht.txt"},
                    "verificationTarget": "File exists",
                    "fallbackNote": None,
                },
                {
                    "title": "Capture screenshot",
                    "goal": "Capture the desktop.",
                    "toolName": "capture_screenshot",
                    "toolArgs": {},
                    "verificationTarget": "Screenshot artifact",
                    "fallbackNote": None,
                },
            ],
        ],
    }


def _build_fake_plan(run_id: str):
    return Planner(model_client=None)._plan_from_model_response(run_id, _fake_plan_payload())


def test_runtime_executes_autonomous_flow(monkeypatch) -> None:
    monkeypatch.setattr("open_collar.planner.Planner.build_plan", lambda *args, **kwargs: _build_fake_plan("run-auto"))
    stream = MemoryStream()
    tools = FakeToolRegistry()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=tools)

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-auto",
            timestamp=now_timestamp(),
            payload={
                "prompt": "Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
                "modelConfig": _model_config(),
            },
        )
    )

    worker = runtime._require_context("run-auto").worker_thread
    assert worker is not None
    worker.join(timeout=5)

    tool_names = [name for name, _ in tools.calls]
    assert tool_names[:9] == [
        "create_folder",
        "open_application",
        "wait_for_window",
        "focus_window",
        "get_active_window",
        "type_text",
        "press_keys",
        "save_file_as",
        "verify_path_exists",
    ]

    messages = [json.loads(line) for line in "".join(stream.lines).splitlines() if line.strip()]
    assert any(message["type"] == "artifact_created" for message in messages)
    assert any(
        message["type"] == "event_logged" and message["payload"]["eventType"] == "step_started"
        for message in messages
    )
    assert any(
        message["type"] == "run_updated" and message["payload"]["state"] == "completed"
        for message in messages
    )


def test_runtime_stops_when_user_cancels(monkeypatch) -> None:
    monkeypatch.setattr("open_collar.planner.Planner.build_plan", lambda *args, **kwargs: _build_fake_plan("run-stop"))
    stream = MemoryStream()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=FakeToolRegistry())

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-stop",
            timestamp=now_timestamp(),
            payload={
                "prompt": "Do something on the computer",
                "modelConfig": _model_config(),
            },
        )
    )
    runtime.handle_envelope(
        Envelope(
            message_type="cancel_run",
            run_id="run-stop",
            timestamp=now_timestamp(),
            payload={},
        )
    )

    joined = "".join(stream.lines)
    assert '"eventType": "run_cancelled"' in joined
    assert '"state": "cancelled"' in joined


def test_runtime_invalid_model_plan_fails_during_planning(monkeypatch) -> None:
    def invalid_plan(*args, **kwargs):
        raise RuntimeError("Each step must include toolName.")

    monkeypatch.setattr("open_collar.planner.Planner.build_plan", invalid_plan)
    stream = MemoryStream()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=FakeToolRegistry())

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-invalid-plan",
            timestamp=now_timestamp(),
            payload={
                "prompt": "open notepad++",
                "modelConfig": _model_config(),
            },
        )
    )

    runtime._require_context("run-invalid-plan").worker_thread.join(timeout=5)
    joined = "".join(stream.lines)
    assert '"summary": "Run failed during planning."' in joined
    assert 'Planning failed: Each step must include toolName.' in joined
