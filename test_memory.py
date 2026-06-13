print("START")

from backend.app.memory.memory_manager import MemoryManager

print("IMPORT OK")

memory = MemoryManager()

print("INSTANCE OK")

memory.store_cycle_result({
    "evaluation": {
        "total_score": 0.82,
        "productivity_score": 0.85,
        "priority_score": 0.80,
        "energy_alignment_score": 0.75,
        "stress_penalty": 0.20
    },
    "forecast_score": 0.76
})

print("STORE OK")

summary = memory.get_system_summary()

print("SUMMARY TYPE:", type(summary))
print("SUMMARY:", summary)

print("END")