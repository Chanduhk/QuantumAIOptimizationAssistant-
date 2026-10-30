# Phase F16 Report: Context-Aware Conversational Intelligence

**Project:** HELIOX AI / Quantum AI Personal Optimization Assistant  
**Date:** October 18, 2026  
**Status:** Completed & Fully Verified  

---

## 1. Executive Summary

Phase F16 extends HELIOX AI into a robust, context-aware personal planning assistant capable of natural-language understanding, personal context retrieval, multi-turn conversational plan refinement, and database-backed proposal lifecycle management.

Prior to F16, planning proposals generated during conversational sessions relied strictly on in-memory ephemeral caching, making them fragile across backend server restarts, multi-worker web processes, or browser page reloads. Furthermore, user intent parsing lacked formal provider abstraction for external LLMs with deterministic offline baselines.

In Phase F16, the system was upgraded with:
1. **Authoritative Proposal Persistence:** An authoritative `plan_proposals` table managed by `PlanProposalService`, establishing UUID v4 proposal identity, monotonic versioning (`v1` -> `v2` -> `v3`), status lifecycle transitions (`PROPOSED`, `ACCEPTED`, `REJECTED`, `EXPIRED`), and 24-hour expiration windows.
2. **Hybrid LLM Provider Abstraction:** A strict contract (`BaseLLMProvider`) implementing `ConfiguredLLMProvider` (with runtime schema validation, attribute stripping, and zero blind trust) alongside `DeterministicFallbackProvider` using rule-based parsing. Every output explicitly reports `parser_provenance` (`llm_provider` vs `deterministic_fallback`).
3. **Context-Aware Intent & Query Understanding:** Handling requests like *"Plan my day around my three most important tasks"*, *"Use my existing tasks and goals"*, and multi-deadline constraints like *"I have an assignment due tomorrow, an exam in three days, and a project next week. I have four hours available today."*
4. **Conversational Plan Refinement & Overload Detection:** In-flight adjustment handling *"I only have two hours available now. Adjust the plan."* (detecting `INFEASIBLE_OVERLOAD` and surfacing trade-offs), *"Move the assignment ahead of my exam preparation."*, and *"Show me another schedule that prioritizes the exam."*
5. **Idempotent Acceptance & Ownership Revalidation:** Proposal acceptance prevents duplicate task creation, revalidates foreign task ownership, and updates existing tasks safely. Rejection marks the proposal `REJECTED` and guarantees existing database tasks remain untouched.
6. **Frontend Experience:** Proposal version badges (`v{version} • {id.slice(0, 8)}`), quick conversational refinement chips, authoritative acceptance with task reconciliation, and plan rejection mutations.

---

## 2. Architectural Components Implemented

### 2.1 Database-Backed Proposal Model (`PlanProposal`)
- **Location:** `backend/app/models/plan_proposal.py`, exported in `backend/app/models/__init__.py`.
- **Table:** `plan_proposals` in `behavior_engine.db`.
- **Schema:**
  - `id`: String (UUID v4 primary key).
  - `user_id`: Integer, indexed.
  - `version`: Integer (default 1, monotonically incrementing with each conversational refinement).
  - `status`: String (`PROPOSED`, `ACCEPTED`, `REJECTED`, `EXPIRED`).
  - `goal_text`: String / Text.
  - `available_hours`: Float (planning horizon).
  - `schedule_data`, `tasks_data`, `constraints_data`, `provenance_data`, `raw_result_data`: JSON-serialized columns with automatic `default=str` datetime/UUID handling.
  - `created_at`, `updated_at`, `expires_at`: Timestamps with index on `expires_at`.

### 2.2 Proposal Lifecycle Service (`PlanProposalService`)
- **Location:** `backend/app/services/plan_proposal_service.py`.
- **Core Operations:**
  - `create_proposal(...)`: Persists new proposal in `PROPOSED` status at version 1.
  - `get_proposal_by_id(...)` & `get_active_proposal(...)`: Enforces strict `user_id` filtering, lazily flags expired proposals.
  - `update_proposal_refinement(...)`: Enforces optimistic concurrency (`expected_version` check), increments version to `v+1`, updates schedule, constraints, and horizon.
  - `accept_proposal(...)`:
    - Revalidates user ownership of every task in the proposed schedule.
    - Idempotently links existing tasks without duplication.
    - Idempotently creates proposed tasks (matching pending tasks with same title to prevent re-creation).
    - Saves persisted task IDs back to the proposal record and transitions status to `ACCEPTED`.
  - `reject_proposal(...)`: Transitions proposal status to `REJECTED`, leaving the database task records untouched.

### 2.3 LLM Provider Abstraction (`HybridPlanningParser`)
- **Location:** `backend/app/interface/llm_provider.py`.
- **Architecture:**
  - `BaseLLMProvider`: Standardized parsing contract.
  - `ConfiguredLLMProvider`: Reads environment variables (`HELIOX_LLM_PROVIDER`, `HELIOX_LLM_API_KEY`, etc.), strips untrusted client attributes, enforces strict JSON schema validation, and falls back gracefully on network or validation errors.
  - `DeterministicFallbackProvider`: Offline, fully deterministic parser backed by `NaturalLanguageExtractor`.
  - `HybridPlanningParser`: Central entry point that delegates to the configured LLM provider if valid, seamlessly falling back to the deterministic parser with `parser_provenance="deterministic_fallback"`.

### 2.4 Context Extraction & Command Parsing
- **Location:** `backend/app/interface/nl_extractor.py` & `backend/app/interface/ai_interaction.py`.
- **Context Capabilities:**
  - Recognizes `use_existing_tasks` prompts (*"Plan my day around my three most important tasks"*, *"Use my existing tasks and goals"*).
  - Extracts numeric task bounds (`task_count=3`).
  - Distinguishes initial planning (`plan_day`), refinements (`refine_plan`), acceptance (`accept_plan`), and rejection (`reject_plan`).
  - Refinement parser identifies `reduce_available_hours`, `move_first`, `reorder`, and `reprioritize`.

### 2.5 Brain Controller & Central Planning Orchestration
- **Location:** `backend/app/orchestrator/ai_brain_controller.py`.
- **Capabilities:**
  - `_execute_central_planning`: If `use_existing_tasks` is specified, queries the user's active tasks from `TaskLifecycleService`, ranks them using personal priorities, and schedules them within the specified horizon. Proposals are saved to `PlanProposal` via `PlanProposalService`.
  - `_execute_proposal_refinement`: Retrieves the persisted active proposal from `PlanProposalService`, applies constraint adjustments (re-ordering, reprioritizing, or reducing available hours), detects overload (`INFEASIBLE_OVERLOAD`) when workload exceeds the horizon, and persists the refined proposal at `v+1`.
  - Backwards-compatible `execute_intent` and `process_intent` unified interface.

### 2.6 REST API Endpoints
- **Location:** `backend/main.py`.
  - `POST /api/v1/ai/plan/accept` & `POST /api/v1/ai/accept-plan`: Accepts proposal with optional version and schedule override.
  - `POST /api/v1/ai/plan/reject` & `POST /api/v1/ai/reject-plan`: Rejects proposal and prevents subsequent acceptance.
  - `GET /api/v1/ai/plan/active`: Fetches the current user's active proposal with full schedule and provenance metadata.

### 2.7 Frontend Assistant Experience
- **Files:** `frontend/src/components/assistant/JamMessage.tsx`, `frontend/src/api/endpoints.ts`, `frontend/src/api/hooks.ts`.
  - Displays proposal ID and version tag (`v{version} • {id.slice(0, 8)}`).
  - Interactive refinement chips pre-loaded with F16 prompts (*"Only 2 hours available"*, *"Move assignment first"*, *"Prioritize exam"*, *"Use existing tasks"*).
  - Explicit Accept and Reject buttons connected to React Query mutations (`useAcceptPlan`, `useRejectPlan`).

---

## 3. Existing Subsystems Reused

Phase F16 directly reuses existing core production services:
- **`TaskLifecycleService`:** Reused for querying active database tasks, creating validated tasks, and revalidating task ownership during plan acceptance.
- **`DecisionPipeline`:** Reused for stage-by-stage optimization (classical scheduler, constraint propagation, buffer enforcement).
- **`VectorMemorySystem`:** Reused for semantic context matching and preference retrieval without duplicating embedding pipelines.
- **`BehaviorIntelligenceEngine`:** Reused for personal productivity profiles and energy-level alignment.

---

## 4. Verification and Test Results

### 4.1 F16 Test Suite (`test_f16_conversational_intelligence.py`)
Execution: `pytest backend/tests/test_f16_conversational_intelligence.py -v`  
**Result:** **9 passed in 81.58s** (100% pass rate).

| Test Name | Focus Area | Result |
|---|---|:---:|
| `test_hybrid_parser_llm_and_deterministic_fallback` | Provider abstraction, fallback, explicit provenance | **PASSED** |
| `test_natural_language_prompts_and_context_detection` | Multi-task parsing, existing tasks, horizon detection | **PASSED** |
| `test_proposal_lifecycle_database_persistence_and_restart` | Database persistence across simulated backend restarts | **PASSED** |
| `test_stale_proposal_optimistic_locking` | Version conflict detection & optimistic concurrency | **PASSED** |
| `test_acceptance_idempotency_and_duplicate_prevention` | Repeated acceptance, no task duplication, ID tracking | **PASSED** |
| `test_rejected_proposal_leaves_database_unmodified` | Rejection flow, database task immutability | **PASSED** |
| `test_user_isolation_security` | Strict cross-user data isolation and authorization | **PASSED** |
| `test_multi_turn_conversational_refinement_flow` | 4-turn journey: Plan -> Reorder -> Overload -> Accept | **PASSED** |
| `test_use_existing_tasks_context_retrieval` | "Plan day around 3 most important tasks" with DB tasks | **PASSED** |

### 4.2 F15 Regression Test Suite (`test_f15_natural_language_planning.py`)
Execution: `pytest backend/tests/test_f15_natural_language_planning.py -v`  
**Result:** **11 passed in 48.05s** (100% pass rate).

### 4.3 Frontend TypeScript & Vite Build
Execution: `npm run build` (`tsc -b && vite build`)  
**Result:** **Exit code 0**, 2412 modules transformed, 0 TypeScript errors.

---

## 5. Integrity and Preservation Verification

1. **Database Preservation:**
   - Authoritative database `behavior_engine.db` verified via sqlite3 inspection.
   - User tasks count: **7 tasks** (100% preserved, no data deleted or reset).
   - Table schema expanded cleanly: `['tasks', 'behavior_data', 'users', 'auth_sessions', 'plan_proposals']`.
2. **Git Workspace Preservation:**
   - All modified and untracked files preserved.
   - No `git reset`, `git clean`, `git restore`, or destructive checkout operations executed.
   - No commits or pushes performed.
3. **Provenance Integrity:**
   - Zero synthetic benchmark data mixed into user tasks.
   - All estimation sources explicitly flagged (`conversational_input`, `deterministic_fallback`, `stored`, `heuristic`).
