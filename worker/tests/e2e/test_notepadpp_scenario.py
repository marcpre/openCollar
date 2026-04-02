import sys

import pytest

from open_collar.runtime import OutputChannel, WorkerRuntime
from open_collar.schemas import Envelope, now_timestamp
from open_collar.tools import FakeToolRegistry


@pytest.mark.skipif(sys.platform.startswith("win"), reason="The deterministic fake E2E is primarily for non-Windows CI.")
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

    runtime.handle_envelope(
        Envelope(
            message_type="start_run",
            run_id="run-e2e",
            timestamp=now_timestamp(),
            payload={
                "prompt": "Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
                "mode": "auto",
            },
        )
    )

    runtime._require_context("run-e2e").worker_thread.join(timeout=5)
    assert any(name == "save_file_as" for name, _ in tools.calls)
    assert any(name == "capture_screenshot" for name, _ in tools.calls)
