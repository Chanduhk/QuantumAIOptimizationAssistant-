from backend.app.interface.nl_extractor import NaturalLanguageExtractor
from datetime import datetime

extractor = NaturalLanguageExtractor(clock=lambda: datetime(2026, 10, 17, 9, 0, 0))
cmd = "I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule."
ctx = extractor.parse_planning_request(cmd)

print("Available hours:", ctx.available_hours)
print("Extracted tasks count:", len(ctx.extracted_tasks))
for t in ctx.extracted_tasks:
    print(f"Task: '{t.title}' | Type: {t.task_type} | Deadline: '{t.deadline_expression}' -> {t.deadline_dt} | Duration: {t.estimated_duration}h ({t.estimated_duration_source}) | Priority: {t.priority}")

# Test refinement
ref1 = extractor.parse_refinement("Move the assignment ahead of the exam preparation.", [])
print("Refinement 1:", ref1)
ref2 = extractor.parse_refinement("Leave 30 minutes for revision.", [])
print("Refinement 2:", ref2)
ref3 = extractor.parse_refinement("Start the project work after lunch.", [])
print("Refinement 3:", ref3)
ref4 = extractor.parse_refinement("Show me another schedule that prioritizes the exam.", [])
print("Refinement 4:", ref4)
ref5 = extractor.parse_refinement("Keep the assignment first but reduce the project time today.", [])
print("Refinement 5:", ref5)
