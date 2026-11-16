import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.db import Base
from backend.app.models.auth import User
from backend.app.models.goal import Goal
from backend.app.models.task import Task
from backend.app.services.goal_service import GoalService
from backend.app.services.task_lifecycle_service import TaskLifecycleService, ensure_task_lifecycle_schema
from backend.app.interface.nl_extractor import NaturalLanguageExtractor
from backend.app.pipeline.decision_pipeline import DecisionPipeline


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_task_lifecycle_schema(sessionmaker(bind=engine)())
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = User(id=1, email="test@example.com", password_hash="hashed_pw_secret_123", created_at=datetime.now(timezone.utc))
    session.add(user)
    session.commit()

    yield session
    session.close()


def test_goal_service_full_crud_and_progress(db_session):
    service = GoalService(db_session)
    target = datetime.now(timezone.utc) + timedelta(days=30)

    # 1. Create Goal
    goal = service.create_goal(
        user_id=1,
        title="Graduation Project",
        description="Complete and defend thesis",
        category="academic",
        priority=5,
        target_date=target,
        status="active",
        progress=0.1,
    )
    assert goal.id is not None
    assert goal.title == "Graduation Project"
    assert goal.priority == 5
    assert goal.category == "academic"

    # 2. Get Goal
    fetched = service.get_goal(goal_id=goal.id, user_id=1)
    assert fetched.id == goal.id

    # 3. List Goals
    goals = service.list_goals(user_id=1, status="active")
    assert len(goals) == 1
    assert goals[0].title == "Graduation Project"

    # 4. Update Goal
    updated = service.update_goal(
        goal_id=goal.id,
        user_id=1,
        title="Graduation Project (Honors)",
        priority=5,
        progress=0.4,
    )
    assert updated.title == "Graduation Project (Honors)"
    assert updated.progress == 0.4

    # 5. Serialization
    serialized = service.serialize_goal(updated)
    assert serialized["id"] == goal.id
    assert serialized["title"] == "Graduation Project (Honors)"
    assert serialized["progress"] == 0.4

    # 6. Delete Goal
    assert service.delete_goal(goal_id=goal.id, user_id=1) is True
    with pytest.raises(ValueError, match="Goal not found"):
        service.get_goal(goal_id=goal.id, user_id=1)


def test_task_lifecycle_with_deadline_goal_and_dependencies(db_session):
    goal_svc = GoalService(db_session)
    task_svc = TaskLifecycleService(db_session)

    goal = goal_svc.create_goal(
        user_id=1,
        title="AI Optimization Research",
        category="academic",
        priority=4,
    )

    deadline_1 = datetime.now(timezone.utc) + timedelta(days=2)
    deadline_2 = datetime.now(timezone.utc) + timedelta(days=5)

    # 1. Create Task A
    task_a = task_svc.create_task(
        user_id=1,
        title="Task A: Literature Review",
        task_type="research",
        priority=4,
        estimated_duration=120,
        estimated_duration_unit="minutes",
        deadline=deadline_1,
        goal_id=goal.id,
        description="Comprehensive survey of QUBO algorithms",
    )
    assert task_a.id is not None
    assert task_a.goal_id == goal.id
    assert task_a.deadline.replace(tzinfo=timezone.utc) == deadline_1
    assert task_a.description == "Comprehensive survey of QUBO algorithms"

    # 2. Create Task B depending on Task A
    task_b = task_svc.create_task(
        user_id=1,
        title="Task B: Implement QUBO formulation",
        task_type="coding",
        priority=5,
        estimated_duration=180,
        estimated_duration_unit="minutes",
        deadline=deadline_2,
        goal_id=goal.id,
        dependencies=[task_a.id],
    )
    assert task_b.id is not None
    serialized_b = task_svc.serialize_task(task_b)
    assert serialized_b["dependencies"] == [task_a.id]

    # 3. Prevent Self-Dependency
    with pytest.raises(ValueError, match="cannot depend on itself"):
        task_svc.update_task(
            task_id=task_a.id,
            user_id=1,
            dependencies=[task_a.id],
        )

    # 4. Prevent Dependency Cycles (A -> B, then try B -> A)
    with pytest.raises(ValueError, match="Dependency cycle detected"):
        task_svc.update_task(
            task_id=task_a.id,
            user_id=1,
            dependencies=[task_b.id],
        )

    # 5. Prevent cross-user prerequisite tasks
    with pytest.raises(ValueError, match="Prerequisite tasks not found or unauthorized"):
        task_svc.create_task(
            user_id=1,
            title="Task with unauthorized dep",
            task_type="general",
            priority=3,
            estimated_duration=30,
            dependencies=[9999],
        )

    # 6. Delete Task A cleans up dependencies in Task B
    task_svc.delete_task(task_id=task_a.id, user_id=1)
    db_session.refresh(task_b)
    assert task_svc.serialize_task(task_b)["dependencies"] == []


def test_natural_language_extractor_synopsis_prompt():
    extractor = NaturalLanguageExtractor()
    ref_dt = datetime(2026, 11, 3, 9, 0, 0)
    command = (
        "I have 6 hours available today. "
        "Complete thesis literature review, estimate 3 hours, high priority, contributes to Graduation goal. "
        "Also study for math exam for 2 hours, due Friday. "
        "Finally review paper draft for 1 hour after thesis literature review."
    )

    context = extractor.extract(command, reference_time=ref_dt)

    # Available horizon
    assert context.available_hours == 6.0
    assert len(context.extracted_tasks) == 3

    # Task 1: Thesis Literature Review
    t1 = context.extracted_tasks[0]
    assert "thesis literature review" in t1.title.lower()
    assert t1.estimated_duration == 3.0
    assert t1.priority >= 4
    assert t1.goal_title == "Graduation"

    # Task 2: Study For Math Exam
    t2 = context.extracted_tasks[1]
    assert "math exam" in t2.title.lower()
    assert t2.estimated_duration == 2.0
    assert t2.deadline_expression is not None
    assert "friday" in t2.deadline_expression.lower()
    assert t2.deadline_dt is not None
    assert t2.deadline_dt.weekday() == 4  # Friday

    # Task 3: Review Paper Draft
    t3 = context.extracted_tasks[2]
    assert "paper draft" in t3.title.lower()
    assert t3.estimated_duration == 1.0
    assert any("thesis literature review" in dep.lower() for dep in t3.dependencies)


def test_decision_pipeline_edf_and_dependency_ordering(db_session):
    pipeline = DecisionPipeline(session=db_session)
    now = datetime.now()

    tasks = [
        {
            "id": "task_flexible",
            "title": "Flexible Low-Priority Task",
            "task_type": "admin",
            "estimated_duration": 1.0,
            "priority": 2,
            "deadline": None,
        },
        {
            "id": "task_urgent_deadline",
            "title": "Urgent Due Tomorrow",
            "task_type": "work",
            "estimated_duration": 1.0,
            "priority": 3,
            "deadline_dt": (now + timedelta(hours=2)).isoformat(),
        },
        {
            "id": "task_prereq",
            "title": "Prerequisite Foundation Work",
            "task_type": "research",
            "estimated_duration": 1.0,
            "priority": 3,
            "deadline": None,
        },
        {
            "id": "task_dependent",
            "title": "Dependent Task Following Foundation",
            "task_type": "writing",
            "estimated_duration": 1.0,
            "priority": 3,
            "dependencies": ["task_prereq"],
            "deadline": None,
        },
    ]

    import asyncio
    result = asyncio.run(pipeline.run_pipeline(
        goal_text="Plan my day efficiently",
        user_id=1,
        tasks=tasks,
        available_hours=8.0,
    ))

    schedule = result.get("schedule", [])
    assert len(schedule) == 4

    # The task with earliest deadline or prerequisite should be prioritized ahead of flexible task
    scheduled_order = [s.get("task_id") or s.get("id") for s in schedule]
    
    # task_prereq must be scheduled before task_dependent
    assert scheduled_order.index("task_prereq") < scheduled_order.index("task_dependent")
    
    # urgent deadline task should be scheduled early
    assert scheduled_order.index("task_urgent_deadline") < scheduled_order.index("task_flexible")
