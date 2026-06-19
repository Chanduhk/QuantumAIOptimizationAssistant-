import math

import pytest

from backend.app.domain.day_model import Day
from backend.app.orchestrator.ai_brain import AIBrain


class FakeContextBuilder:
    def build(self, day):
        return {"task_count": len(day.tasks)}


class FakeScheduler:
    def __init__(self, output):
        self.output = output

    def generate(self, day):
        return self.output


class FakeForecastEngine:
    def __init__(self, output):
        self.output = output

    def simulate(self):
        return self.output


class FakeMemoryManager:
    def __init__(self, output=None):
        self.output = output

    def store_memory(self, description, metadata):
        return self.output


def make_brain(*, scheduler_output=None, forecast_output=0.5, memory_output=None) -> AIBrain:
    return AIBrain(
        scheduler=FakeScheduler({} if scheduler_output is None else scheduler_output),
        forecast_engine=FakeForecastEngine(forecast_output),
        context_builder=FakeContextBuilder(),
        memory_manager=FakeMemoryManager(memory_output),
    )


def test_generate_schedule_rejects_malformed_scheduler_output() -> None:
    brain = make_brain(scheduler_output=["bad"])

    with pytest.raises(ValueError, match="Scheduler must return"):
        brain.generate_schedule(Day(available_hours=8, sleep_hours=8))


@pytest.mark.parametrize("forecast_output", [math.nan, math.inf, "bad"])
def test_run_forecast_rejects_invalid_forecast_scores(forecast_output) -> None:
    brain = make_brain(forecast_output=forecast_output)

    with pytest.raises(ValueError, match="forecast_score"):
        brain.run_forecast(Day(available_hours=8, sleep_hours=8))


def test_record_cycle_rejects_malformed_memory_result() -> None:
    brain = make_brain(memory_output=["bad"])

    with pytest.raises(ValueError, match="memory_manager"):
        brain._record_cycle({"context": {}, "schedule": {}, "evaluation": {}, "forecast_score": 1.0})
