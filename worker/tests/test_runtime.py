import json

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


def test_runtime_emits_plan_and_approval_for_assist_mode() -> None:
    stream = MemoryStream()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=FakeToolRegistry())
    runtime.boot()

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-1",
            timestamp=now_timestamp(),
            payload={
                "prompt": "Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
                "mode": "assist",
            },
        )
    )

    joined = "".join(stream.lines)
    assert '"type": "plan_created"' in joined
    assert '"type": "approval_requested"' in joined


def test_runtime_auto_mode_executes_notepad_flow() -> None:
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
                "mode": "auto",
            },
        )
    )

    worker = runtime._require_context("run-auto").worker_thread
    assert worker is not None
    worker.join(timeout=5)

    tool_names = [name for name, _ in tools.calls]
    assert tool_names == [
        "create_folder",
        "open_application",
        "wait_for_window",
        "focus_window",
        "get_active_window",
        "type_text",
        "press_keys",
        "save_file_as",
        "verify_path_exists",
        "capture_screenshot",
    ]

    messages = [json.loads(line) for line in "".join(stream.lines).splitlines() if line.strip()]
    assert any(message["type"] == "artifact_created" for message in messages)
    assert any(
        message["type"] == "run_updated" and message["payload"]["state"] == "completed"
        for message in messages
    )


def test_runtime_accepts_gemini_selection_for_deterministic_flow() -> None:
    stream = MemoryStream()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=FakeToolRegistry())

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-gemini",
            timestamp=now_timestamp(),
            payload={
                "prompt": "Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
                "mode": "assist",
                "modelConfig": {
                    "provider": "gemini",
                    "modelName": "gemini-2.5-flash",
                    "apiKey": "test-key",
                },
            },
        )
    )

    context = runtime._require_context("run-gemini")
    assert context.model_provider == "gemini"
    assert context.model_name == "gemini-2.5-flash"
