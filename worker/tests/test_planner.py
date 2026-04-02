from open_collar.planner import Planner


def test_planner_builds_deterministic_notepad_plan() -> None:
    planner = Planner(model_client=None)

    plan = planner.build_plan(
        run_id="run-1",
        prompt="Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt",
        mode="assist",
        tool_names=[],
    )

    assert len(plan.step_groups) == 4
    assert plan.step_groups[0][0].tool_name == "create_folder"
    assert plan.step_groups[3][-1].tool_name == "capture_screenshot"
