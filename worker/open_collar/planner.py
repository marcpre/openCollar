from __future__ import annotations

from pathlib import Path
from typing import Any

from .model_client import PlanningModel
from .schemas import RunPlan, StepRecord, now_timestamp

POEM_TEXT = """Im leisen Licht des Monitors,
zieht still die Nacht durchs Zimmer.
Ein kleiner Klick, ein neues Wort,
und Ideen glühen immer.

Der Agent schreibt, der Cursor tanzt,
durch Fenster, Tasten, Zeiten.
Aus einem Prompt wird Schritt für Schritt
ein Werk aus Möglichkeiten.
"""


class Planner:
    def __init__(self, model_client: PlanningModel | None = None) -> None:
        self._model_client = model_client

    def build_plan(self, run_id: str, prompt: str, mode: str, tool_names: list[str]) -> RunPlan:
        lowered = prompt.lower()
        if "notepad++" in lowered and "gedicht.txt" in lowered:
            return self._build_notepad_plan(run_id)

        if self._model_client is None:
            raise RuntimeError(
                "No model client is configured for general planning. "
                "Use the Notepad++ scenario or choose a Gemini model and enter an API key."
            )

        response = self._model_client.plan_task(prompt=prompt, mode=mode, tool_names=tool_names)
        return self._plan_from_model_response(run_id, response)

    def _build_notepad_plan(self, run_id: str) -> RunPlan:
        target_dir = Path.home() / "Desktop" / "agent_test"
        target_file = target_dir / "gedicht.txt"
        timestamp = now_timestamp()

        steps = [
            [
                StepRecord(
                    id=f"{run_id}-step-0-0",
                    run_id=run_id,
                    title="Create destination folder",
                    goal="Ensure Desktop/agent_test exists before the editor launches.",
                    group_index=0,
                    step_index=0,
                    tool_name="create_folder",
                    tool_args={"path": str(target_dir)},
                    verification_target=str(target_dir),
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="If the folder already exists, treat the result as success.",
                )
            ],
            [
                StepRecord(
                    id=f"{run_id}-step-1-0",
                    run_id=run_id,
                    title="Open Notepad++",
                    goal="Launch Notepad++ on the Windows desktop.",
                    group_index=1,
                    step_index=0,
                    tool_name="open_application",
                    tool_args={"app": "notepad++"},
                    verification_target="Notepad++ process running",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="Fail clearly if Notepad++ is not installed.",
                ),
                StepRecord(
                    id=f"{run_id}-step-1-1",
                    run_id=run_id,
                    title="Wait for editor window",
                    goal="Wait for the Notepad++ window to appear.",
                    group_index=1,
                    step_index=1,
                    tool_name="wait_for_window",
                    tool_args={"title_contains": "Notepad++", "timeout_ms": 15000},
                    verification_target="Notepad++ window visible",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note=None,
                ),
                StepRecord(
                    id=f"{run_id}-step-1-2",
                    run_id=run_id,
                    title="Focus editor window",
                    goal="Bring the Notepad++ window to the foreground for text entry.",
                    group_index=1,
                    step_index=2,
                    tool_name="focus_window",
                    tool_args={"title_contains": "Notepad++"},
                    verification_target="Notepad++ is the active window",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note=None,
                ),
            ],
            [
                StepRecord(
                    id=f"{run_id}-step-2-0",
                    run_id=run_id,
                    title="Type poem",
                    goal="Write the full German poem into Notepad++.",
                    group_index=2,
                    step_index=0,
                    tool_name="type_text",
                    tool_args={"text": POEM_TEXT},
                    verification_target="Poem text visible in editor",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="If typing stalls, stop and ask for human review.",
                ),
                StepRecord(
                    id=f"{run_id}-step-2-1",
                    run_id=run_id,
                    title="Open save dialog",
                    goal="Trigger the save flow from Notepad++.",
                    group_index=2,
                    step_index=1,
                    tool_name="press_keys",
                    tool_args={"keys": "ctrl+s"},
                    verification_target="Save dialog opens",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note=None,
                ),
            ],
            [
                StepRecord(
                    id=f"{run_id}-step-3-0",
                    run_id=run_id,
                    title="Save poem to Desktop",
                    goal="Fill the save dialog and write the file to Desktop/agent_test/gedicht.txt.",
                    group_index=3,
                    step_index=0,
                    tool_name="save_file_as",
                    tool_args={"path": str(target_file)},
                    verification_target=str(target_file),
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="If Save As is blocked, stop rather than guessing.",
                ),
                StepRecord(
                    id=f"{run_id}-step-3-1",
                    run_id=run_id,
                    title="Verify saved file",
                    goal="Confirm the saved poem exists on disk.",
                    group_index=3,
                    step_index=1,
                    tool_name="verify_path_exists",
                    tool_args={"path": str(target_file)},
                    verification_target=str(target_file),
                    state="pending",
                    updated_at=timestamp,
                    fallback_note="Never mark the run complete without this verification.",
                ),
                StepRecord(
                    id=f"{run_id}-step-3-2",
                    run_id=run_id,
                    title="Capture final screenshot",
                    goal="Record the desktop state for human verification in the right panel.",
                    group_index=3,
                    step_index=2,
                    tool_name="capture_screenshot",
                    tool_args={},
                    verification_target="Screenshot artifact",
                    state="pending",
                    updated_at=timestamp,
                    fallback_note=None,
                ),
            ],
        ]

        return RunPlan(step_groups=steps, summary="Execute the fixed Notepad++ poem scenario.")

    def _plan_from_model_response(self, run_id: str, response: dict[str, Any]) -> RunPlan:
        summary = str(response.get("summary") or "Model-generated plan.")
        step_groups: list[list[StepRecord]] = []

        for group_index, raw_group in enumerate(response.get("stepGroups") or []):
            group: list[StepRecord] = []
            for step_index, raw_step in enumerate(raw_group):
                group.append(
                    StepRecord(
                        id=f"{run_id}-step-{group_index}-{step_index}",
                        run_id=run_id,
                        title=str(raw_step["title"]),
                        goal=str(raw_step["goal"]),
                        group_index=group_index,
                        step_index=step_index,
                        tool_name=str(raw_step.get("toolName")) if raw_step.get("toolName") else None,
                        tool_args=dict(raw_step.get("toolArgs") or {}),
                        verification_target=(
                            str(raw_step["verificationTarget"])
                            if raw_step.get("verificationTarget")
                            else None
                        ),
                        state="pending",
                        updated_at=now_timestamp(),
                        fallback_note=(
                            str(raw_step["fallbackNote"]) if raw_step.get("fallbackNote") else None
                        ),
                    )
                )
            step_groups.append(group)

        if not step_groups:
            raise RuntimeError("Model did not return any executable step groups.")

        return RunPlan(step_groups=step_groups, summary=summary)
