from datetime import datetime, timezone
from backend.app.interface.nl_extractor import NaturalLanguageExtractor, ExtractedPlanningContext

# Test 1
fixed_now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
extractor = NaturalLanguageExtractor(clock=lambda: fixed_now)

text = (
    "I have an assignment due tomorrow, an exam in three days, and a project submission "
    "next week. I have four hours available today. Plan my schedule."
)
res = extractor.extract(text, user_tz="UTC")

print("Test 1:")
print("Available hours:", res.available_hours)
print("Tasks count:", len(res.extracted_tasks))
for i, t in enumerate(res.extracted_tasks):
    print(f"Task {i+1}: title='{t.title}', deadline_expr='{t.deadline_expression}', deadline_dt={t.deadline_dt}, priority={t.priority}")

assert res.available_hours == 4.0
assert len(res.extracted_tasks) == 3
assert "assignment" in res.extracted_tasks[0].title.lower()
assert res.extracted_tasks[0].deadline_expression == "tomorrow"
assert res.extracted_tasks[0].deadline_dt.day == 21
assert "exam" in res.extracted_tasks[1].title.lower()
assert res.extracted_tasks[1].deadline_expression == "in 3 days"
assert res.extracted_tasks[1].deadline_dt.day == 23
assert "project" in res.extracted_tasks[2].title.lower()
assert res.extracted_tasks[2].deadline_expression == "next week"
assert res.extracted_tasks[2].deadline_dt.day == 27
print("Test 1 passed!")

# Test 2
text2 = "Complete literature review for 2 hours due 2026-10-25 with high priority. Then write thesis draft for 3 hours after literature review."
res2 = extractor.extract(text2, user_tz="UTC")
print("\nTest 2:")
print("Tasks count:", len(res2.extracted_tasks))
for i, t in enumerate(res2.extracted_tasks):
    print(f"Task {i+1}: title='{t.title}', duration={t.estimated_duration}, deadline_dt={t.deadline_dt}, priority={t.priority}, deps={t.dependencies}")

assert len(res2.extracted_tasks) == 2
assert "literature review" in res2.extracted_tasks[0].title.lower()
assert res2.extracted_tasks[0].estimated_duration == 2.0
assert res2.extracted_tasks[0].deadline_dt.strftime("%Y-%m-%d") == "2026-10-25"
assert res2.extracted_tasks[0].priority == 4
assert "thesis draft" in res2.extracted_tasks[1].title.lower()
assert res2.extracted_tasks[1].estimated_duration == 3.0
assert len(res2.extracted_tasks[1].dependencies) == 1
assert "literature review" in res2.extracted_tasks[1].dependencies[0]
print("Test 2 passed!")

# Test 3
text3 = "Hello, can you help me plan something vague?"
res3 = extractor.extract(text3)
print("\nTest 3:")
print("Tasks count:", len(res3.extracted_tasks))
print("Clarification needed:", res3.clarification_needed)
print("Clarification question:", res3.clarification_question)
assert len(res3.extracted_tasks) == 0
assert res3.clarification_needed is True
assert "could not detect" in res3.clarification_question.lower()
print("Test 3 passed!")

print("\nALL EXTRACTOR UNIT TESTS PASSED!")
