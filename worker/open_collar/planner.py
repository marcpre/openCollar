from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .model_client import PlanningModel
from .schemas import RunPlan, StepRecord, now_timestamp


class Planner:
    def __init__(self, model_client: PlanningModel | None = None) -> None:
        self._model_client = model_client

    def build_plan(self, run_id: str, prompt: str, tool_names: list[str]) -> RunPlan:
        notepad_plan = self._maybe_build_notepad_plan(run_id, prompt)
        if notepad_plan is not None:
            return notepad_plan

        if self._model_client is None:
            raise RuntimeError("No Gemini planner is configured. Add a Gemini API key and try again.")

        response = self._model_client.plan_task(prompt=prompt, tool_names=tool_names)
        return self._plan_from_model_response(run_id, response)

    def _maybe_build_notepad_plan(self, run_id: str, prompt: str) -> RunPlan | None:
        lowered = prompt.lower()
        if "notepad++" not in lowered and "notepad" not in lowered:
            return None
        if not any(keyword in lowered for keyword in ("write", "type", "create a new file", "new file", "save")):
            return None

        app_name = "notepad++" if "notepad++" in lowered else "notepad"
        timestamp = now_timestamp()
        steps: list[StepRecord] = [
            StepRecord(
                id=f"{run_id}-step-0-0",
                run_id=run_id,
                title=f"Open {app_name}",
                goal=f"Launch the {app_name} application.",
                group_index=0,
                step_index=0,
                tool_name="open_application",
                tool_args={"app": app_name},
                verification_target=f"{app_name} process running",
                state="pending",
                updated_at=timestamp,
                fallback_note=f"Stop if {app_name} is unavailable.",
            ),
            StepRecord(
                id=f"{run_id}-step-0-1",
                run_id=run_id,
                title=f"Wait for {app_name} window",
                goal=f"Ensure the {app_name} application has fully loaded before proceeding.",
                group_index=0,
                step_index=1,
                tool_name="wait_for_window",
                tool_args={"title_contains": "Notepad++" if app_name == "notepad++" else "Notepad", "timeout_ms": 15000},
                verification_target=f"{app_name} window visible",
                state="pending",
                updated_at=timestamp,
                fallback_note="Fail clearly if the window never appears.",
            ),
            StepRecord(
                id=f"{run_id}-step-0-2",
                run_id=run_id,
                title=f"Focus {app_name}",
                goal=f"Make the {app_name} window the active window to receive keyboard input.",
                group_index=0,
                step_index=2,
                tool_name="focus_window",
                tool_args={"title_contains": "Notepad++" if app_name == "notepad++" else "Notepad"},
                verification_target=f"{app_name} focused",
                state="pending",
                updated_at=timestamp,
                fallback_note="Stop if another window keeps focus.",
            ),
        ]

        next_step_index = len(steps)
        if "create a new file" in lowered or "new file" in lowered:
            steps.append(
                StepRecord(
                    id=f"{run_id}-step-0-{next_step_index}",
                    run_id=run_id,
                    title="Create a new file",
                    goal="Use the keyboard shortcut to create a new empty file.",
                    group_index=0,
                    step_index=next_step_index,
                    tool_name="press_keys",
                    tool_args={"keys": "ctrl+n"},
                    verification_target="Fresh document ready",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="Stop if the editor does not create a new file.",
                )
            )
            next_step_index += 1

        text_to_write = self._extract_text_to_write(prompt)
        if text_to_write:
            steps.append(
                StepRecord(
                    id=f"{run_id}-step-0-{next_step_index}",
                    run_id=run_id,
                    title="Write requested text",
                    goal=f'Write "{text_to_write}" into the active editor.',
                    group_index=0,
                    step_index=next_step_index,
                    tool_name="type_text",
                    tool_args={"text": text_to_write},
                    verification_target="Requested text visible in the editor",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="Stop if typing does not land in the editor.",
                )
            )
            next_step_index += 1

        save_path = self._extract_save_path(prompt)
        if save_path:
            save_dir = str(Path(save_path).expanduser().parent)
            steps.extend(
                [
                    StepRecord(
                        id=f"{run_id}-step-0-{next_step_index}",
                        run_id=run_id,
                        title="Create destination folder",
                        goal="Ensure the target folder exists before saving the file.",
                        group_index=0,
                        step_index=next_step_index,
                        tool_name="create_folder",
                        tool_args={"path": save_dir},
                        verification_target=save_dir,
                        state="pending",
                        updated_at=timestamp,
                        fallback_note="Treat an existing folder as success.",
                    ),
                    StepRecord(
                        id=f"{run_id}-step-0-{next_step_index + 1}",
                        run_id=run_id,
                        title="Open save dialog",
                        goal="Open the save dialog from the active editor.",
                        group_index=0,
                        step_index=next_step_index + 1,
                        tool_name="press_keys",
                        tool_args={"keys": "ctrl+s"},
                        verification_target="Save dialog open",
                        state="pending",
                        updated_at=timestamp,
                        fallback_note="Stop if the save dialog does not appear.",
                    ),
                    StepRecord(
                        id=f"{run_id}-step-0-{next_step_index + 2}",
                        run_id=run_id,
                        title="Save file",
                        goal=f"Save the current file to {save_path}.",
                        group_index=0,
                        step_index=next_step_index + 2,
                        tool_name="save_file_as",
                        tool_args={"path": save_path},
                        verification_target=save_path,
                        state="pending",
                        updated_at=timestamp,
                        fallback_note="Stop if the file cannot be saved.",
                    ),
                    StepRecord(
                        id=f"{run_id}-step-0-{next_step_index + 3}",
                        run_id=run_id,
                        title="Verify saved file",
                        goal="Confirm that the saved file exists on disk.",
                        group_index=0,
                        step_index=next_step_index + 3,
                        tool_name="verify_path_exists",
                        tool_args={"path": save_path},
                        verification_target=save_path,
                        state="pending",
                        updated_at=timestamp,
                        fallback_note="Never report success without verifying the file.",
                    ),
                ]
            )
            next_step_index += 4

        if not any(step.tool_name == "type_text" for step in steps):
            return None

        steps.append(
            StepRecord(
                id=f"{run_id}-step-0-{next_step_index}",
                run_id=run_id,
                title="Capture final screenshot",
                goal="Capture the final desktop state for the observer panel.",
                group_index=0,
                step_index=next_step_index,
                tool_name="capture_screenshot",
                tool_args={},
                verification_target="Screenshot artifact",
                state="pending",
                updated_at=timestamp,
                fallback_note=None,
            )
        )

        return RunPlan(
            step_groups=[steps],
            summary=f'Open {app_name}, create a new file, and write "{text_to_write}".' if "new file" in lowered or "create a new file" in lowered else f'Open {app_name} and write "{text_to_write}".',
        )

    def _extract_text_to_write(self, prompt: str) -> str | None:
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', prompt)
        if quoted:
            first = quoted[0]
            return first[0] or first[1]

        match = re.search(r"\b(?:write|type)\b(?:\s+in\s+it)?\s+(.+)", prompt, flags=re.IGNORECASE)
        if not match:
            return None

        candidate = match.group(1).strip().rstrip(".")
        candidate = re.sub(r"\b(?:and\s+save.*|to\s+.+)$", "", candidate, flags=re.IGNORECASE).strip()
        return candidate or None

    def _extract_save_path(self, prompt: str) -> str | None:
        path_match = re.search(r"\bto\s+([A-Za-z]:\\[^\"']+\.\w+)", prompt)
        if path_match:
            return path_match.group(1).strip()
        return None

    def _plan_from_model_response(self, run_id: str, response: dict[str, Any]) -> RunPlan:
        summary = str(response.get("summary") or "Model-generated plan.")
        step_groups: list[list[StepRecord]] = []

        for group_index, raw_group in enumerate(self._normalize_step_groups(response)):
            group: list[StepRecord] = []
            for step_index, raw_step in enumerate(self._normalize_steps(raw_group)):
                tool_name = self._extract_tool_name(raw_step)
                group.append(
                    StepRecord(
                        id=f"{run_id}-step-{group_index}-{step_index}",
                        run_id=run_id,
                        title=str(raw_step.get("title") or f"Step {group_index + 1}.{step_index + 1}"),
                        goal=str(raw_step.get("goal") or raw_step.get("title") or "Complete this action."),
                        group_index=group_index,
                        step_index=step_index,
                        tool_name=tool_name,
                        tool_args=self._extract_tool_args(raw_step),
                        verification_target=(
                            str(raw_step["verificationTarget"])
                            if raw_step.get("verificationTarget")
                            else str(raw_step["verify"])
                            if raw_step.get("verify")
                            else None
                        ),
                        state="pending",
                        updated_at=now_timestamp(),
                        fallback_note=(
                            str(raw_step["fallbackNote"])
                            if raw_step.get("fallbackNote")
                            else str(raw_step["fallback"])
                            if raw_step.get("fallback")
                            else None
                        ),
                    )
                )
            step_groups.append(group)

        if not step_groups:
            raise RuntimeError("Model did not return any executable step groups.")

        return RunPlan(step_groups=step_groups, summary=summary)

    def _normalize_step_groups(self, response: dict[str, Any]) -> list[Any]:
        raw_groups = response.get("stepGroups")
        if not isinstance(raw_groups, list):
            raise RuntimeError("Model response must include a stepGroups array.")

        if not raw_groups:
            return []

        if all(isinstance(group, dict) and self._looks_like_step(group) for group in raw_groups):
            return [[group] for group in raw_groups]

        return raw_groups

    def _normalize_steps(self, raw_group: Any) -> list[dict[str, Any]]:
        if isinstance(raw_group, list):
            steps = raw_group
        elif isinstance(raw_group, dict):
            if isinstance(raw_group.get("steps"), list):
                steps = raw_group["steps"]
            elif self._looks_like_step(raw_group):
                steps = [raw_group]
            else:
                raise RuntimeError("A step group object must contain a steps array or a single step object.")
        else:
            raise RuntimeError("Each step group must be an array or object.")

        normalized: list[dict[str, Any]] = []
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                raise RuntimeError("Each step must be a JSON object.")
            if self._extract_tool_name(raw_step) is None:
                raise RuntimeError("Each step must include toolName.")
            normalized.append(raw_step)
        return normalized

    def _looks_like_step(self, value: dict[str, Any]) -> bool:
        return (
            "toolName" in value
            or "tool" in value
            or "action" in value
            or "name" in value
            or "toolArgs" in value
            or "args" in value
            or "parameters" in value
            or "goal" in value
            or "title" in value
        )

    def _extract_tool_name(self, raw_step: dict[str, Any]) -> str | None:
        for key in ("toolName", "tool", "action", "command", "name"):
            value = raw_step.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_tool_args(self, raw_step: dict[str, Any]) -> dict[str, Any]:
        for key in ("toolArgs", "args", "parameters"):
            value = raw_step.get(key)
            if isinstance(value, dict):
                return dict(value)
        return {}
