from backend.app.pipeline.decision_pipeline import DecisionPipeline


def test_goal_task_without_estimate_keeps_unknown_provenance_instead_of_guessing():
    pipeline = DecisionPipeline(session=None)  # type: ignore[arg-type]

    task = pipeline._normalize_goal_task(
        {"title": "Execute main work block", "type": "general", "priority": 8},
        index=1,
        user_id=7,
        goal_metadata={"goal": "Plan my day"},
    )

    assert task["estimated_duration"] is None
    assert task["estimated_duration_unit"] == "unknown"
    assert task["estimated_duration_source"] is None
    assert task["duration_provenance_status"] == "UNKNOWN_UNIT"
    assert pipeline._goal_task_duration_errors([task]) == ["Execute main work block"]


def test_goal_task_with_explicit_estimate_and_source_passes_duration_gate():
    pipeline = DecisionPipeline(session=None)  # type: ignore[arg-type]

    task = pipeline._normalize_goal_task(
        {
            "title": "Prepare report",
            "type": "writing",
            "estimated_duration": 30,
            "estimated_duration_unit": "minutes",
            "estimated_duration_source": "task_api",
        },
        index=1,
        user_id=7,
        goal_metadata={"goal": "Prepare report"},
    )

    assert task["estimated_duration"] == 30
    assert task["estimated_duration_unit"] == "minutes"
    assert task["estimated_duration_source"] == "task_api"
    assert task["duration_provenance_status"] == "KNOWN_UNIT"
    assert pipeline._goal_task_duration_errors([task]) == []


def test_actual_duration_is_not_accepted_as_a_goal_estimate():
    pipeline = DecisionPipeline(session=None)  # type: ignore[arg-type]
    task = pipeline._normalize_goal_task(
        {"title": "Completed item", "actual_duration": 45},
        index=1,
        user_id=7,
        goal_metadata={},
    )

    assert task["estimated_duration"] is None
    assert pipeline._goal_task_duration_errors([task]) == ["Completed item"]
