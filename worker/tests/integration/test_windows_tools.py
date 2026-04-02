import sys

import pytest

from open_collar.tools import ToolContext, ToolRegistry


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only integration coverage.")
def test_windows_tool_registry_contains_required_tools(tmp_path) -> None:
    registry = ToolRegistry(ToolContext(artifact_dir=tmp_path, mode="assist"))

    assert "open_application" in registry.tool_names
    assert "save_file_as" in registry.tool_names
    assert "capture_screenshot" in registry.tool_names
