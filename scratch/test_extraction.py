from backend.app.interface.nl_extractor import NaturalLanguageExtractor

ext = NaturalLanguageExtractor()
prompt = "I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule."
ctx = ext.parse_planning_request(prompt)

print(f"Hours: {ctx.available_hours}")
for t in ctx.extracted_tasks:
    print(f"Task: '{t.title}', Deadline: '{t.deadline_expression}', Dt: {t.deadline_dt}, Prio: {t.priority}, Dur: {t.estimated_duration}h")
