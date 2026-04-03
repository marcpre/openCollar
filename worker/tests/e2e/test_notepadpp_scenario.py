import sys

import pytest

from open_collar.planner import Planner
from open_collar.runtime import OutputChannel, WorkerRuntime
from open_collar.schemas import Envelope, now_timestamp
from open_collar.tools import FakeToolRegistry


@pytest.mark.skipif(sys.platform.startswith("win"), reason="The fake desktop E2E is primarily for non-Windows CI.")
def test_notepadpp_scenario_e2e_with_fake_tools() -> None:
    class MemoryStream:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def write(self, content: str) -> None:
            self.lines.append(content)

        def flush(self) -> None:
            return

    stream = MemoryStream()
    tools = FakeToolRegistry()
    runtime = WorkerRuntime(output=OutputChannel(stream), tool_registry=tools)
    fake_plan = Planner(model_client=None)._plan_from_model_response(
        "run-e2e",
        {
            "summary": "Write and save the poem.",
            "stepGroups": [
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
                        "title": "Save file",
                        "goal": "Save the poem.",
                        "toolName": "save_file_as",
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
                ]
            ],
        },
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("open_collar.planner.Planner.build_plan", lambda *args, **kwargs: fake_plan)

    try:
        runtime.handle_envelope(
            Envelope(
                message_type="start_run",
                run_id="run-e2e",
                timestamp=now_timestamp(),
                payload={
                    "prompt": "Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
                    "modelConfig": {
                        "provider": "gemini",
                        "modelName": "gemini-2.5-pro",
                        "apiKey": "test-key",
                    },
                },
            )
        )
    finally:
        monkeypatch.undo()

    runtime._require_context("run-e2e").worker_thread.join(timeout=5)
    assert any(name == "save_file_as" for name, _ in tools.calls)
    assert any(name == "capture_screenshot" for name, _ in tools.calls)
