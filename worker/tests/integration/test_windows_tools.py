import sys

import pytest

from open_collar.tools import ToolCallResult, ToolContext, ToolExecutionError, ToolRegistry


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only integration coverage.")
def test_windows_tool_registry_contains_required_tools(tmp_path) -> None:
    registry = ToolRegistry(ToolContext(artifact_dir=tmp_path))

    assert "open_application" in registry.tool_names
    assert "save_file_as" in registry.tool_names
    assert "capture_screenshot" in registry.tool_names


def test_press_keys_rejects_list_argument(tmp_path) -> None:
    registry = ToolRegistry(ToolContext(artifact_dir=tmp_path))

    with pytest.raises(ToolExecutionError, match="press_keys.keys must be a string"):
        registry.execute("press_keys", {"keys": ["ctrl+n", "ctrl+s"]})


def test_focus_window_normalizes_single_item_list(tmp_path) -> None:
    registry = ToolRegistry(ToolContext(artifact_dir=tmp_path))
    seen: dict[str, str] = {}

    def fake_focus_window(title_contains: str) -> ToolCallResult:
        seen["title_contains"] = title_contains
        return ToolCallResult({"title": title_contains, "focused": True})

    registry._handlers["focus_window"] = fake_focus_window

    registry.execute("focus_window", {"title_contains": ["Notepad++"]})
    assert seen["title_contains"] == "Notepad++"


def test_click_element_rejects_selector_list(tmp_path) -> None:
    registry = ToolRegistry(ToolContext(artifact_dir=tmp_path))

    with pytest.raises(ToolExecutionError, match="click_element.selector must be a string"):
        registry.execute("click_element", {"window": "Notepad++", "selector": ["File", "New"]})
