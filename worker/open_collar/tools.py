from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class ToolExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ToolCallResult:
    data: dict[str, Any]


@dataclass(slots=True)
class ToolContext:
    artifact_dir: Path


class ToolRegistry:
    def __init__(self, context: ToolContext) -> None:
        self._context = context
        self._handlers: dict[str, Callable[..., ToolCallResult]] = {
            "create_folder": self.create_folder,
            "open_application": self.open_application,
            "wait_for_window": self.wait_for_window,
            "focus_window": self.focus_window,
            "click_element": self.click_element,
            "click_coordinates": self.click_coordinates,
            "type_text": self.type_text,
            "press_keys": self.press_keys,
            "read_window_text": self.read_window_text,
            "save_file_as": self.save_file_as,
            "capture_screenshot": self.capture_screenshot,
            "verify_path_exists": self.verify_path_exists,
            "get_active_window": self.get_active_window,
            "list_window_elements": self.list_window_elements,
        }

    @property
    def tool_names(self) -> list[str]:
        return list(self._handlers.keys())

    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolCallResult:
        if tool_name not in self._handlers:
            raise ToolExecutionError("tool_not_whitelisted", f"Unknown tool {tool_name!r}.")

        normalized_args = self._validate(tool_name, args)
        return self._handlers[tool_name](**normalized_args)

    def _validate(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        required: dict[str, tuple[str, ...]] = {
            "create_folder": ("path",),
            "open_application": ("app",),
            "wait_for_window": ("title_contains", "timeout_ms"),
            "focus_window": ("title_contains",),
            "click_element": ("window", "selector"),
            "click_coordinates": ("x", "y"),
            "type_text": ("text",),
            "press_keys": ("keys",),
            "read_window_text": ("title_contains",),
            "save_file_as": ("path",),
            "capture_screenshot": (),
            "verify_path_exists": ("path",),
            "get_active_window": (),
            "list_window_elements": ("title_contains",),
        }
        missing = [name for name in required[tool_name] if name not in args]
        if missing:
            raise ToolExecutionError("validation_error", f"Missing arguments for {tool_name}: {', '.join(missing)}")

        normalized = dict(args)
        if tool_name in {"create_folder", "open_application", "focus_window", "read_window_text", "save_file_as", "verify_path_exists", "list_window_elements"}:
            string_key = {
                "create_folder": "path",
                "open_application": "app",
                "focus_window": "title_contains",
                "read_window_text": "title_contains",
                "save_file_as": "path",
                "verify_path_exists": "path",
                "list_window_elements": "title_contains",
            }[tool_name]
            normalized[string_key] = self._coerce_string(tool_name, string_key, normalized[string_key])
        elif tool_name == "wait_for_window":
            normalized["title_contains"] = self._coerce_string(tool_name, "title_contains", normalized["title_contains"])
            normalized["timeout_ms"] = self._coerce_int(tool_name, "timeout_ms", normalized["timeout_ms"])
        elif tool_name == "click_element":
            normalized["window"] = self._coerce_string(tool_name, "window", normalized["window"])
            normalized["selector"] = self._coerce_string(tool_name, "selector", normalized["selector"])
        elif tool_name == "click_coordinates":
            normalized["x"] = self._coerce_int(tool_name, "x", normalized["x"])
            normalized["y"] = self._coerce_int(tool_name, "y", normalized["y"])
        elif tool_name == "type_text":
            normalized["text"] = self._coerce_string(tool_name, "text", normalized["text"])
        elif tool_name == "press_keys":
            normalized["keys"] = self._coerce_string(tool_name, "keys", normalized["keys"])

        return normalized

    def _coerce_string(self, tool_name: str, field_name: str, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str) and value[0].strip():
            return value[0]
        actual_type = type(value).__name__
        raise ToolExecutionError(
            "validation_error",
            f"{tool_name}.{field_name} must be a string, but received {actual_type}.",
        )

    def _coerce_int(self, tool_name: str, field_name: str, value: Any) -> int:
        if isinstance(value, bool):
            raise ToolExecutionError(
                "validation_error",
                f"{tool_name}.{field_name} must be an integer, but received bool.",
            )
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError as error:
                raise ToolExecutionError(
                    "validation_error",
                    f"{tool_name}.{field_name} must be an integer, but received str.",
                ) from error
        actual_type = type(value).__name__
        raise ToolExecutionError(
            "validation_error",
            f"{tool_name}.{field_name} must be an integer, but received {actual_type}.",
        )

    def _ensure_windows(self) -> None:
        if not sys.platform.startswith("win"):
            raise ToolExecutionError("unsupported_platform", "Windows desktop automation only runs on Windows.")

    def _desktop(self):
        self._ensure_windows()
        from pywinauto import Desktop

        return Desktop(backend="uia")

    def _find_window(self, title_contains: str, timeout_ms: int | None = None):
        deadline = time.time() + ((timeout_ms or 0) / 1000)
        desktop = self._desktop()
        while True:
            for window in desktop.windows():
                title = window.window_text()
                if title_contains.lower() in title.lower():
                    return window

            if timeout_ms is None or time.time() >= deadline:
                break
            time.sleep(0.3)

        raise ToolExecutionError("window_not_found", f"No window contains {title_contains!r}.")

    def create_folder(self, path: str) -> ToolCallResult:
        folder = Path(path).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        return ToolCallResult({"path": str(folder), "created": True})

    def open_application(self, app: str) -> ToolCallResult:
        launch_targets = {
            "notepad++": ["notepad++"],
            "notepad": ["notepad.exe"],
        }
        command = launch_targets.get(app.lower(), [app])
        if app.lower() == "notepad++":
            resolved = (
                shutil.which("notepad++")
                or shutil.which("notepad++.exe")
                or shutil.which("C:\\Program Files\\Notepad++\\notepad++.exe")
                or shutil.which("C:\\Program Files (x86)\\Notepad++\\notepad++.exe")
            )
            if resolved:
                command = [resolved]
        try:
            process = subprocess.Popen(command)
        except FileNotFoundError as error:
            raise ToolExecutionError("application_not_found", str(error)) from error
        return ToolCallResult({"app": app, "pid": process.pid})

    def wait_for_window(self, title_contains: str, timeout_ms: int) -> ToolCallResult:
        window = self._find_window(title_contains=title_contains, timeout_ms=timeout_ms)
        return ToolCallResult({"title": window.window_text()})

    def focus_window(self, title_contains: str) -> ToolCallResult:
        window = self._find_window(title_contains=title_contains, timeout_ms=5000)
        window.set_focus()
        return ToolCallResult({"title": window.window_text(), "focused": True})

    def click_element(self, window: str, selector: str) -> ToolCallResult:
        target_window = self._find_window(title_contains=window, timeout_ms=5000)
        for control in target_window.descendants():
            info = control.element_info
            haystacks = [
                getattr(info, "name", "") or "",
                getattr(info, "automation_id", "") or "",
                getattr(info, "class_name", "") or "",
            ]
            if any(selector.lower() in value.lower() for value in haystacks):
                control.click_input()
                return ToolCallResult({"window": target_window.window_text(), "selector": selector})
        raise ToolExecutionError("element_not_found", f"Could not find selector {selector!r}.")

    def click_coordinates(self, x: int, y: int) -> ToolCallResult:
        self._ensure_windows()
        from pywinauto import mouse

        mouse.click(button="left", coords=(x, y))
        return ToolCallResult({"x": x, "y": y})

    def type_text(self, text: str) -> ToolCallResult:
        self._ensure_windows()
        from pywinauto.keyboard import send_keys

        payload = text.replace("{", "{{}").replace("}", "{}}").replace("\n", "{ENTER}")
        send_keys(payload, with_spaces=True, pause=0.02, vk_packet=True)
        return ToolCallResult({"characters": len(text)})

    def press_keys(self, keys: str) -> ToolCallResult:
        self._ensure_windows()
        from pywinauto.keyboard import send_keys

        normalized = keys.lower().replace("ctrl+", "^").replace("shift+", "+").replace("alt+", "%")
        send_keys(normalized, pause=0.02)
        return ToolCallResult({"keys": keys})

    def read_window_text(self, title_contains: str) -> ToolCallResult:
        window = self._find_window(title_contains=title_contains, timeout_ms=5000)
        try:
            content = window.window_text()
        except Exception as error:  # pragma: no cover - pywinauto specifics
            raise ToolExecutionError("read_failed", str(error)) from error
        return ToolCallResult({"title": window.window_text(), "text": content})

    def save_file_as(self, path: str) -> ToolCallResult:
        dialog = self._find_window(title_contains="Save", timeout_ms=10000)
        try:
            edit = dialog.child_window(control_type="Edit")
            edit.set_edit_text(path)
        except Exception:
            self.type_text(path)
        try:
            save_button = dialog.child_window(title_re="Save", control_type="Button")
            save_button.click_input()
        except Exception:
            self.press_keys("enter")
        return ToolCallResult({"path": path})

    def capture_screenshot(self) -> ToolCallResult:
        self._ensure_windows()
        from PIL import ImageGrab

        self._context.artifact_dir.mkdir(parents=True, exist_ok=True)
        target = self._context.artifact_dir / f"screenshot-{int(time.time() * 1000)}.png"
        ImageGrab.grab(all_screens=True).save(target)
        return ToolCallResult({"path": str(target), "kind": "screenshot"})

    def verify_path_exists(self, path: str) -> ToolCallResult:
        exists = Path(path).expanduser().exists()
        if not exists:
            raise ToolExecutionError("path_missing", f"Expected path does not exist: {path}")
        return ToolCallResult({"path": path, "exists": True})

    def get_active_window(self) -> ToolCallResult:
        self._ensure_windows()
        from pywinauto import Desktop, findwindows

        try:
            window = Desktop(backend="uia").window(active_only=True).wrapper_object()
        except Exception:
            try:
                active_element = findwindows.find_element(backend="uia", active_only=True)
                window = Desktop(backend="uia").window(handle=active_element.handle).wrapper_object()
            except Exception:
                for candidate in Desktop(backend="uia").windows():
                    try:
                        if candidate.is_active():
                            window = candidate
                            break
                    except Exception:
                        continue
                else:
                    raise ToolExecutionError("active_window_unavailable", "Could not resolve the active window.")

        return ToolCallResult({"title": window.window_text()})

    def list_window_elements(self, title_contains: str) -> ToolCallResult:
        window = self._find_window(title_contains=title_contains, timeout_ms=5000)
        items: list[dict[str, str]] = []
        for control in window.descendants():
            info = control.element_info
            items.append(
                {
                    "name": getattr(info, "name", "") or "",
                    "automation_id": getattr(info, "automation_id", "") or "",
                    "class_name": getattr(info, "class_name", "") or "",
                    "control_type": getattr(info, "control_type", "") or "",
                }
            )
        return ToolCallResult({"window": window.window_text(), "elements": items})


class FakeToolRegistry(ToolRegistry):
    def __init__(self) -> None:
        super().__init__(ToolContext(artifact_dir=Path.cwd() / ".tmp-artifacts"))
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolCallResult:
        self.calls.append((tool_name, json.loads(json.dumps(args))))
        result = super().execute(tool_name, args)
        if tool_name == "capture_screenshot":
            target = self._context.artifact_dir / "fake-screenshot.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fake", encoding="utf-8")
            return ToolCallResult({"path": str(target), "kind": "screenshot"})
        if tool_name == "verify_path_exists":
            return ToolCallResult({"path": result.data["path"], "exists": True})
        if tool_name == "get_active_window":
            return ToolCallResult({"title": "Notepad++"})
        return result

    def create_folder(self, path: str) -> ToolCallResult:
        return ToolCallResult({"path": path, "created": True})

    def open_application(self, app: str) -> ToolCallResult:
        return ToolCallResult({"app": app, "pid": 1234})

    def wait_for_window(self, title_contains: str, timeout_ms: int) -> ToolCallResult:
        return ToolCallResult({"title": title_contains})

    def focus_window(self, title_contains: str) -> ToolCallResult:
        return ToolCallResult({"title": title_contains, "focused": True})

    def click_element(self, window: str, selector: str) -> ToolCallResult:
        return ToolCallResult({"window": window, "selector": selector})

    def click_coordinates(self, x: int, y: int) -> ToolCallResult:
        return ToolCallResult({"x": x, "y": y})

    def type_text(self, text: str) -> ToolCallResult:
        return ToolCallResult({"characters": len(text)})

    def press_keys(self, keys: str) -> ToolCallResult:
        return ToolCallResult({"keys": keys})

    def read_window_text(self, title_contains: str) -> ToolCallResult:
        return ToolCallResult({"title": title_contains, "text": ""})

    def save_file_as(self, path: str) -> ToolCallResult:
        return ToolCallResult({"path": path})

    def verify_path_exists(self, path: str) -> ToolCallResult:
        return ToolCallResult({"path": path, "exists": True})

    def capture_screenshot(self) -> ToolCallResult:
        target = self._context.artifact_dir / "fake-screenshot.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fake", encoding="utf-8")
        return ToolCallResult({"path": str(target), "kind": "screenshot"})

    def list_window_elements(self, title_contains: str) -> ToolCallResult:
        return ToolCallResult({"window": title_contains, "elements": []})
