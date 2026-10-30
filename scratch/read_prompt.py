import json

log_file = r"C:\Users\thanu\.gemini\antigravity-ide\brain\f27a7c59-2aa4-4698-b882-b14d4abc1ebc\.system_generated\logs\transcript_full.jsonl"
with open(log_file, "r", encoding="utf-8") as f:
    for line in f:
        if '"step_index":9676' in line:
            data = json.loads(line)
            if data.get("step_index") == 9676:
                with open("E:/quantum_life_ai/scratch/f17_prompt.txt", "w", encoding="utf-8") as out:
                    out.write(data["content"])
                print("Wrote f17_prompt.txt successfully, length:", len(data["content"]))
                break
