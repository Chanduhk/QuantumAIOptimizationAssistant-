# PHASE F15 — HELIOX AI INTELLIGENT PLANNING AND NATURAL-LANGUAGE UNDERSTANDING

**Project:** HELIOX AI / Quantum AI Personal Optimization Assistant  
**Working Directory:** `E:\quantum_life_ai`  
**Production Database:** `behavior_engine.db` (Preserved intact: 7 verified user tasks, 0 synthetic records)  
**Status:** IMPLEMENTED, VERIFIED & PASSING  

---

## 1. Executive Summary & Capabilities Implemented

Phase F15 builds directly upon the foundational capabilities of F14 to deliver a complete, multi-task, natural-language planning and refinement pipeline. It bridges informal user conversations with realistic constraint-aware scheduling, explainable trade-offs, and safe user-isolated plan persistence.

Key capabilities delivered in F15:

1. **Multi-Task Natural Language Extraction Engine (`NaturalLanguageExtractor`):**
   - Extracts compound, multi-task commands containing heterogeneous deadlines and duration constraints in a single sentence (e.g., *"I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule."*).
   - Ingests injectable reference clocks (`clock=...`) enabling deterministic testing and localized datetime anchoring across arbitrary timezones.
   - Parses relative deadlines (*"today"*, *"tomorrow"*, *"in three days"*, *"next week"*), specific calendar dates (*"YYYY-MM-DD"*, *"October 25th"*), and explicit times-of-day (*"by 5pm"*).
   - Segments clauses using compound punctuation, coordinating conjunctions, and sentence boundaries while cleanly stripping conversational filler and greetings (*"Hello"*, *"Can you help me"*).
   - Extracts explicit durations with units and flags duration provenance as `conversational_input` or `deterministic_heuristic`.
   - Infers task priorities (1–5) and automatically detects elevated urgency for exams, critical deliverables, and explicit priority keywords.
   - Detects prerequisite task dependencies (*"Then write thesis draft for 3 hours after literature review"*).

2. **Conversational Refinement Engine (`parse_refinement`):**
   - Understands conversational follow-up instructions without requiring users to repeat task details.
   - Supports reordering constraints: *"Move the exam ahead of the assignment"*.
   - Supports buffer time allocation: *"Leave 30 minutes for revision"*.
   - Supports time-of-day constraints: *"Start the project work after lunch"* (maps to `scheduled_start >= 13.0`).
   - Supports scope and duration adjustments: *"Keep the assignment first but reduce the project time today to 1 hour"*.

3. **Constraint-Aware Non-Overlapping Decision Pipeline (`DecisionPipeline.optimize_schedule`):**
   - Applies Earliest Deadline First (EDF) ordering combined with priority and dependency constraints.
   - Strictly enforces prerequisite completion before dependent start (`scheduled_start >= dependency.scheduled_end`).
   - Enforces time-of-day constraints (e.g. afternoon scheduling `min_start_hour >= 13.0`).
   - Inserts requested buffer intervals between consecutive tasks.
   - Verifies deadline feasibility per task (`deadline_feasible` boolean and explicit `deadline_warning` flags).
   - Prevents overlapping intervals (`scheduled_start >= previous_scheduled_end`).
   - Generates transparent `reasons_for_prioritization` and explainable `trade_offs` detailing why tasks were ordered as proposed.
   - Handles capacity overload: when demanded workload exceeds available window, marks schedule as `INFEASIBLE_OVERLOAD`, flags un-fittable tasks with `fits_in_horizon=False`, and provides actionable alternative options (Capacity Expansion, Task Deferral, Scope Reduction).

4. **Safe User-Isolated Plan Acceptance & Rejection (`AIBrainController`):**
   - Caches active proposals in an in-memory, user-scoped proposal store (`_active_proposals[user_id]`).
   - Zero database mutations occur when generating or refining plan proposals.
   - Accepting a proposal (`/api/v1/ai/accept-plan` and `/api/v1/ai/plan/accept`) persists proposed tasks via `TaskLifecycleService`, assigns scheduled intervals (`start_time`, `end_time`), and updates existing tasks.
   - Enforces strict duplicate prevention: subsequent acceptance calls reuse existing matching tasks rather than creating duplicate records.
   - Enforces strict user isolation: authenticated user ID is verified against the payload; attempts by User B to alter or accept User A's tasks are blocked (403 Forbidden).
   - Rejecting a proposal (`"Reject plan proposal"`) completely clears cached proposals with zero database modifications.

5. **Enhanced Frontend Assistant Interface (`JamMessage.tsx` & `AssistantPage.tsx`):**
   - Enriched `PlanProposalCard` with:
     - Distinct task origin badges (**Proposed New** vs **Existing**).
     - Deadline badges (**Due: tomorrow**, **Due: in 3 days**) with deadline conflict warning pills.
     - Duration provenance labels (Deterministic NL vs Personal Model vs Heuristic).
     - Chronological schedule with start/end intervals and non-overlapping interval guarantees.
     - Unscheduled/Deferred tasks section for over-horizon workloads.
     - Prioritization ordering drivers and key trade-offs expandable section.
     - Conversational refinement quick chips (*"Move assignment ahead"*, *"Leave 30 minutes for revision"*, *"Start afternoon work after lunch"*) and a free-form refinement input bar.
     - Interactive **Accept Proposal** and **Reject Proposal** action buttons triggering instant TanStack Query cache invalidation.

---

## 2. Relevant Files Changed & Created

| File | Type | Purpose |
| :--- | :--- | :--- |
| `backend/app/interface/nl_extractor.py` | New Component | Multi-task extractor, relative & calendar deadline parser, dependency resolver, refinement parser, and clarification trigger. |
| `backend/app/interface/__init__.py` | Update | Exposes `NaturalLanguageExtractor`, `ExtractedPlanningContext`, and `ExtractedTaskSpec`. |
| `backend/app/interface/ai_interaction.py` | Update | Integrates intent classification (`refine_plan`, `reject_plan`, `accept_plan`, `plan_day`), extracts structured tasks, and sanitizes vector memory inputs. |
| `backend/app/pipeline/decision_pipeline.py` | Update | Earliest Deadline First (EDF) prioritization, order overrides, dependency enforcement, afternoon slot constraints, buffer insertion, deadline feasibility auditing, and trade-off rationales. |
| `backend/app/orchestrator/ai_brain_controller.py` | Update | Central proposal caching (`_active_proposals`), conversational proposal refinement execution, atomic database persistence on acceptance, proposal discarding on rejection, and duplicate prevention. |
| `backend/main.py` | Update | Added `@app.post("/api/v1/ai/accept-plan")` alias alongside `/api/v1/ai/plan/accept`. |
| `frontend/src/components/assistant/JamMessage.tsx` | UI Update | Upgraded `PlanProposalCard` with badges, conflict warnings, provenance details, trade-offs drawer, refinement quick chips, and accept/reject actions. |
| `frontend/src/pages/AssistantPage.tsx` | UI Update | Wired `onRefine={handleSend}` into `JamMessage`. |
| `backend/tests/test_f15_natural_language_planning.py` | New Test Suite | Comprehensive 11-case test suite verifying multi-task extraction, deadlines, constraints, refinements, rejection, acceptance, and user isolation. |

---

## 3. API & Schema Summary

### Conversational Planning & Refinement (`POST /api/v1/ai/command`)
- **Headers:** `X-CSRF-Token` (mandatory), Cookie session authentication.
- **Payload:**
  ```json
  {
    "user_id": 1,
    "command": "I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule.",
    "days_back": 90
  }
  ```
- **Response Format:**
  ```json
  {
    "intent": "plan_day",
    "result": {
      "success": true,
      "feasibility_status": "FEASIBLE",
      "available_hours": 4.0,
      "total_demanded_hours": 3.0,
      "schedule": [
        {
          "title": "Assignment",
          "origin": "proposed",
          "priority": 3,
          "scheduled_hour": 9.0,
          "scheduled_end_hour": 10.0,
          "duration_hours": 1.0,
          "duration_source": "deterministic_heuristic",
          "deadline_expression": "tomorrow",
          "deadline_dt": "2026-10-21T17:00:00",
          "deadline_feasible": true,
          "deadline_warning": null,
          "reasons_for_prioritization": ["Earliest deadline (tomorrow) scheduled first."]
        }
      ],
      "reasons_for_prioritization": ["Earliest deadline (tomorrow) scheduled first."],
      "trade_offs": ["Prioritized tasks with earliest deadlines first, trading off flexible tasks to minimize deadline slippage risk."],
      "infeasible_tasks": [],
      "alternative_actions": []
    }
  }
  ```

### Proposal Acceptance (`POST /api/v1/ai/accept-plan`)
- **Headers:** `X-CSRF-Token`, Cookie authentication.
- **Payload:**
  ```json
  {
    "user_id": 1,
    "schedule": [ ... ]
  }
  ```
- **Response Format:**
  ```json
  {
    "status": "success",
    "result": {
      "success": true,
      "action": "plan_accepted",
      "plan_accepted": true,
      "plan_rejected": false,
      "persisted_task_ids": [12, 13],
      "persisted_count": 2,
      "executive_summary": "Plan accepted and persisted for 2 task(s)."
    }
  }
  ```

---

## 4. Transparent Provenance & Known Product Limitations

1. **Heuristic & Conversational Provenance:**
   - Tasks extracted from conversation are explicitly labeled with `estimated_duration_source: "conversational_input"` or `"deterministic_heuristic"`.
   - Heuristics are NEVER labeled as personal ML predictions or quantum optimizations.
2. **Behavioral ML Model Gating:**
   - Personal ML productivity predictions are only generated when the user has >= 20 completed tasks in the database. For new users, baseline heuristic values are reported with clear disclosure.
3. **Local NLP Parsing Scope:**
   - Natural language extraction uses deterministic regex and semantic rule grammars without relying on external cloud LLM APIs. Highly ambiguous or non-standard syntax triggers a clarification question rather than guessing.

---

## 5. Verification & Test Suite Results

### A. F15 Comprehensive Test Suite
- **Command:** `.venv\Scripts\python.exe -m pytest backend/tests/test_f15_natural_language_planning.py -v -s`
- **Result:** **11 passed out of 11** (13.01s)
- **Coverage:**
  1. `test_nl_extractor_multi_task_and_relative_deadlines`: Extracted multiple tasks, relative deadlines (`tomorrow`, `in 3 days`, `next week`), durations, and priority escalation for exams.
  2. `test_nl_extractor_calendar_dates_and_dependencies`: Extracted ISO calendar dates (`2026-10-25`), durations, and prerequisite dependencies.
  3. `test_nl_extractor_refinement_instructions`: Verified refinement parsing for reordering, 30m buffers, afternoon slots (`min_start_hour=13.0`), and duration reduction.
  4. `test_nl_extractor_missing_information_triggers_clarification`: Confirmed vague inputs trigger clarification without creating empty or nonsense tasks.
  5. `test_e2e_multi_task_planning_without_db_tasks`: E2E multi-task planning without pre-existing DB tasks, non-overlapping intervals, EDF ordering, and prioritization reasons.
  6. `test_conversational_refinement_reorders_proposal_without_persistence`: Reordering proposal via conversational follow-up without mutating database state.
  7. `test_conversational_refinement_add_buffer_and_after_lunch`: Buffer insertion (gap >= 0.5h) and afternoon scheduling (start >= 13.0).
  8. `test_proposal_rejection_discards_cache_without_db_changes`: Rejecting proposal clears cached proposals with zero database writes.
  9. `test_safe_acceptance_persists_proposed_tasks_and_updates_existing`: Plan acceptance persists proposed tasks to DB with schedule times, and idempotent re-acceptance prevents duplicate creation.
  10. `test_user_isolation_on_plan_acceptance`: Rejects user mismatch (403) and blocks cross-user task modification.
  11. `test_overloaded_horizon_capacity_handling`: Overloaded workload (6h demanded vs 3h available) categorized as `INFEASIBLE_OVERLOAD`, flags un-fittable tasks with `fits_in_horizon=False`, and provides actionable alternative options.

### B. F14 Regression Test Suite
- **Command:** `.venv\Scripts\python.exe -m pytest backend/tests/test_f14_intelligence_and_optimization.py -v -s`
- **Result:** **6 passed out of 6** (10.92s)

### C. Frontend Production Build
- **Command:** `npm run build` (`tsc -b && vite build`)
- **Result:** **0 errors, successfully compiled** in `frontend/dist` (2m 25s)
