from open_collar.planner import Planner


class FakeModelClient:
    def plan_task(self, prompt: str, tool_names: list[str]) -> dict[str, object]:
        assert "open_application" in tool_names
        return {
            "summary": "Open Notepad++, write a poem, and save it.",
            "stepGroups": [
                [
                    {
                        "title": "Open Notepad++",
                        "goal": "Launch Notepad++.",
                        "toolName": "open_application",
                        "toolArgs": {"app": "notepad++"},
                        "verificationTarget": "Notepad++ window visible",
                        "fallbackNote": "Stop if Notepad++ is unavailable.",
                    }
                ],
                [
                    {
                        "title": "Capture screenshot",
                        "goal": "Record the result.",
                        "toolName": "capture_screenshot",
                        "toolArgs": {},
                        "verificationTarget": "Screenshot artifact",
                        "fallbackNote": None,
                    }
                ],
            ],
        }


def test_planner_builds_plan_from_model_response() -> None:
    planner = Planner(model_client=FakeModelClient())

    plan = planner.build_plan(
        run_id="run-1",
        prompt="Use the model client to make a tiny capture plan.",
        tool_names=["open_application", "capture_screenshot"],
    )

    assert len(plan.step_groups) == 2
    assert plan.step_groups[0][0].tool_name == "open_application"
    assert plan.step_groups[1][0].tool_name == "capture_screenshot"


class FlatGroupModelClient:
    def plan_task(self, prompt: str, tool_names: list[str]) -> dict[str, object]:
        return {
            "summary": "Open the editor.",
            "stepGroups": [
                {
                    "title": "Open Notepad++",
                    "goal": "Launch Notepad++.",
                    "toolName": "open_application",
                    "toolArgs": {"app": "notepad++"},
                },
                {
                    "title": "Wait for the window",
                    "goal": "Wait until the window appears.",
                    "toolName": "wait_for_window",
                    "toolArgs": {"title_contains": "Notepad++", "timeout_ms": 15000},
                },
            ],
        }


class NestedStepsModelClient:
    def plan_task(self, prompt: str, tool_names: list[str]) -> dict[str, object]:
        return {
            "summary": "Grouped plan.",
            "stepGroups": [
                {
                    "label": "Launch",
                    "steps": [
                        {
                            "title": "Open Notepad++",
                            "goal": "Launch Notepad++.",
                            "toolName": "open_application",
                            "toolArgs": {"app": "notepad++"},
                        }
                    ],
                }
            ],
        }


class AliasKeyModelClient:
    def plan_task(self, prompt: str, tool_names: list[str]) -> dict[str, object]:
        return {
            "summary": "Alias-based plan.",
            "stepGroups": [
                [
                    {
                        "title": "Open Notepad++",
                        "goal": "Launch Notepad++.",
                        "tool": "open_application",
                        "args": {"app": "notepad++"},
                        "verify": "Notepad++ window visible",
                        "fallback": "Stop if launch fails.",
                    }
                ]
            ],
        }


def test_planner_accepts_flat_step_groups() -> None:
    planner = Planner(model_client=FlatGroupModelClient())

    plan = planner.build_plan(
        run_id="run-flat",
        prompt="open notepad++",
        tool_names=["open_application", "wait_for_window"],
    )

    assert len(plan.step_groups) == 2
    assert plan.step_groups[0][0].tool_name == "open_application"
    assert plan.step_groups[1][0].tool_name == "wait_for_window"


def test_planner_accepts_group_objects_with_steps() -> None:
    planner = Planner(model_client=NestedStepsModelClient())

    plan = planner.build_plan(
        run_id="run-nested",
        prompt="open notepad++",
        tool_names=["open_application"],
    )

    assert len(plan.step_groups) == 1
    assert len(plan.step_groups[0]) == 1
    assert plan.step_groups[0][0].tool_name == "open_application"


def test_planner_accepts_alias_tool_keys() -> None:
    planner = Planner(model_client=AliasKeyModelClient())

    plan = planner.build_plan(
        run_id="run-alias",
        prompt="open notepad++",
        tool_names=["open_application"],
    )

    step = plan.step_groups[0][0]
    assert step.tool_name == "open_application"
    assert step.tool_args == {"app": "notepad++"}
    assert step.verification_target == "Notepad++ window visible"
    assert step.fallback_note == "Stop if launch fails."


def test_planner_builds_deterministic_notepad_open_write_plan() -> None:
    planner = Planner(model_client=None)

    plan = planner.build_plan(
        run_id="run-notepad-write",
        prompt='open notepad++ and write "hello opencollar"',
        tool_names=[],
    )

    assert plan.step_groups[0][0].tool_name == "open_application"
    assert plan.step_groups[0][1].tool_name == "wait_for_window"
    assert plan.step_groups[0][2].tool_name == "focus_window"
    assert plan.step_groups[0][3].tool_name == "type_text"
    assert plan.step_groups[0][3].tool_args == {"text": "hello opencollar"}


def test_planner_builds_deterministic_notepad_new_file_plan() -> None:
    planner = Planner(model_client=None)

    plan = planner.build_plan(
        run_id="run-notepad-new-file",
        prompt='open notepad++ and create a new file and write "hello opencollar"',
        tool_names=[],
    )

    tool_names = [step.tool_name for step in plan.step_groups[0]]
    assert "press_keys" in tool_names
    assert any(step.tool_args == {"keys": "ctrl+n"} for step in plan.step_groups[0] if step.tool_name == "press_keys")


def test_planner_builds_deterministic_notepad_save_plan() -> None:
    planner = Planner(model_client=None)

    plan = planner.build_plan(
        run_id="run-notepad-save",
        prompt='open notepad++ and write "hello opencollar" to C:\\Users\\tester\\Desktop\\agent_test\\hello.txt',
        tool_names=[],
    )

    tool_names = [step.tool_name for step in plan.step_groups[0]]
    assert "create_folder" in tool_names
    assert "save_file_as" in tool_names
    assert "verify_path_exists" in tool_names
