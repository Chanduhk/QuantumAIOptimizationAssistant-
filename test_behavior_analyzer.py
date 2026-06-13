from backend.app.memory.memory_manager import MemoryManager
from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer

memory = MemoryManager()

for score in [0.72, 0.76, 0.81, 0.84, 0.88]:
    memory.store_cycle_result({
        "evaluation": {
            "total_score": score,
            "productivity_score": score,
            "priority_score": score,
            "energy_alignment_score": score,
            "stress_penalty": 1 - score
        },
        "forecast_score": score
    })

analyzer = BehaviorAnalyzer(memory)

profile = analyzer.analyze()

print(profile)