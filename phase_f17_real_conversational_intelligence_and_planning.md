# Phase F17 Report: Real Conversational Intelligence & Advanced Personal Planning

**Project:** HELIOX AI / Quantum AI Personal Optimization Assistant  
**Date:** October 18, 2026  
**Status:** Completed & Verified  

---

## 1. Executive Summary & Vertical Slice Delivery

Phase F17 delivers a complete, production-grade conversational personal planning assistant. It extends the foundations established in F14, F15, and F16 into an end-to-end, context-aware vertical slice:

$$\text{Natural-language request} \longrightarrow \text{LLM understanding / explicit fallback} \longrightarrow \text{Personal context retrieval} \longrightarrow \text{Multi-task plan validation} \longrightarrow \text{Feasible schedule} \longrightarrow \text{Grounded explanation} \longrightarrow \text{Conversational refinement} \longrightarrow \text{User acceptance} \longrightarrow \text{Safe persistence} \longrightarrow \text{Updated dashboard}$$

Key advancements implemented in Phase F17:
1. **Multi-Provider LLM Abstraction with Secure Auto-Detection:** A clean, configurable provider interface supporting OpenAI, Google Gemini, Anthropic Claude, Groq, Ollama, and generic OpenAI-compatible HTTP endpoints. Includes API key masking in logs (`_mask_key`), zero prompt leakage, runtime typed schema validation, attribute stripping, HTML sanitization, and explicit parser provenance (`llm_openai`, `llm_gemini`, `llm_anthropic`, `llm_groq`, etc. vs. `deterministic_fallback`).
2. **Real-Life Compound Request Interpretation:** Full understanding of multi-task requests containing relative deadlines and horizon constraints:
   *"I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule."*
   Extracts tasks, relative deadlines resolved via timezone and controllable clock, duration bounds, priorities, and available hours.
3. **Multi-Criteria Decision Policy & Interval Scheduling:**
   - Evaluates deadline urgency, user-defined priority, duration, dependencies, and available time horizon.
   - Strictly separates mandatory constraints (dependencies, continuous non-overlapping intervals, horizon boundaries) from preferences.
   - Multi-hour continuous interval reservation guarantees that extended tasks (e.g., 2 hours) receive unbroken execution blocks without interleaving or overlap.
4. **Overload Detection, Feasible Subset Selection & Realistic Alternatives:**
   - When demanded workload exceeds the available horizon, the scheduler identifies `INFEASIBLE_OVERLOAD`, fits the highest-priority feasible subset into today's window, explicitly surfaces `unscheduled_tasks`, and presents three concrete realistic alternatives:
     - **Option A (Capacity Expansion):** Increase available horizon to execute all tasks today.
     - **Option B (Task Deferral):** Execute fitted tasks today and defer remaining work to tomorrow.
     - **Option C (Scope Reduction):** Compress lower-priority task durations.
5. **Complete Conversational Refinement:**
   - Persistent database-backed proposals (`plan_proposals` table) with UUID v4 identity and monotonic version incrementing (`v1` $\to$ `v2` $\to$ `v3`).
   - Seamless follow-up adjustments:
     - *"Move the assignment first."* (`move_first`)
     - *"Prioritize the exam instead."* (`reprioritize`)
     - *"Leave 30 minutes for revision."* (`add_buffer`)
     - *"Show me another feasible option."* (`alternative_schedule`)
     - *"I only have two hours available now."* (`reduce_available_hours`)
     - *"Accept this plan."* (`accept_plan`)
     - *"Reject this plan."* (`reject_plan`)
6. **Safe, Idempotent Acceptance & Data Isolation:**
   - Proposal acceptance revalidates task ownership, prevents duplicate task creation by matching pending tasks with the same title, persists start/end times non-overlappingly, transitions status to `ACCEPTED`, and updates the dashboard.
   - Proposal rejection transitions status to `REJECTED` and guarantees existing tasks remain untouched.
   - Strict cross-user isolation prevents unauthorized inspection or modification.
7. **Honest Provenance & Quantum/ML Transparency:**
   - Prediction provenance explicitly labels every duration estimate (`explicit_user_input`, `task_api`, `deterministic_heuristic`, `statistical_estimate`, or `personal_ml_model`).
   - Personal ML duration predictions are only invoked when the model passes readiness thresholds (`readiness.py`).
   - Quantum optimization is checked via `QuantumSuitabilityAnalyzer`: 1–4 task instances use simulated local statevector simulation, clearly labeled as simulation with no false claims of quantum speedup or quantum advantage.

---

## 2. Existing Services and Subsystems Reused

Phase F17 strictly preserves and directly leverages existing architectural assets without competing pipelines or duplicate engines:

- **`PlanProposalService` (`backend/app/services/plan_proposal_service.py`):** Authoritative database persistence of proposals in `behavior_engine.db` with monotonic versioning, optimistic locking, and idempotent acceptance.
- **`TaskLifecycleService` (`backend/app/services/task_lifecycle_service.py`):** Creation, validation, ownership checking, and scheduling of database tasks.
- **`DecisionPipeline` (`backend/app/pipeline/decision_pipeline.py`):** Central async reasoning workflow, feature extraction, RL scheduler integration, classical optimizer, and interval placement.
- **`ExecutiveCognitiveBrain` (`backend/app/orchestrator/executive_cognitive_brain.py`):** Multi-engine coordinator reviewing candidate plans, risk summaries, governance, and resource constraints.
- **`AIInteractionLayer` (`backend/app/interface/ai_interaction.py`):** Natural language command dispatcher, session manager, and intent router.
- **`VectorMemorySystem` (`backend/app/memory/vector_memory.py`):** Semantic context retrieval with local transformer / deterministic embedding fallback.
- **`BehaviorIntelligenceEngine` (`backend/app/services/behavior_engine.py`):** User productivity patterns and energy-level alignment.
- **`QuantumSuitabilityAnalyzer` & `QUBOFormulator` (`backend/app/quantum/`):** Formulation of discrete scheduling binary assignment and honest evaluation.

---

## 3. LLM Provider Configuration & Resilient Fallback

### 3.1 Supported Providers & Environment Variables
The `ConfiguredLLMProvider` abstraction automatically detects and configures external providers via standard environment variables:

| Provider | Auto-Detection Variable | Default Endpoint | Default Model | Payload Format |
|---|---|---|---|---|
| **OpenAI** | `OPENAI_API_KEY` or `HELIOX_LLM_PROVIDER=openai` | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` | Chat completions with `json_object` format |
| **Google Gemini** | `GEMINI_API_KEY` or `HELIOX_LLM_PROVIDER=gemini` | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `gemini-1.5-flash` | REST API with `response_mime_type: "application/json"` |
| **Anthropic** | `ANTHROPIC_API_KEY` or `HELIOX_LLM_PROVIDER=anthropic` | `https://api.anthropic.com/v1/messages` | `claude-3-5-sonnet-20241022` | Messages API with system prompt & JSON schema |
| **Groq** | `GROQ_API_KEY` or `HELIOX_LLM_PROVIDER=groq` | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.1-70b-versatile` | OpenAI-compatible JSON mode |
| **Ollama / Local** | `OLLAMA_HOST` or `HELIOX_LLM_PROVIDER=ollama` | `{OLLAMA_HOST}/v1/chat/completions` | `llama3` | OpenAI-compatible local HTTP endpoint |

### 3.2 Security, Sanitization & Privacy
- **API Key Masking:** Helper `_mask_key(key)` ensures logs never expose credentials (e.g., `sk-...234` or `***`).
- **Zero Prompt Leakage:** User prompts are never logged in plaintext error traces.
- **Untrusted Output Handling:** LLM output is strictly validated against `ExtractedTaskSpec`:
  - Titles: Stripped of HTML/script tags (`re.sub(r"<[^>]*>", "", raw_title)`).
  - Priority: Clamped to integer $[1, 5]$.
  - Duration: Clamped to float $[0.25, 24.0]$ hours.
  - Deadlines: Validated against controllable clock reference.
  - Client attributes stripped: LLM responses cannot inject database IDs or bypass authorization.
- **Resilient Fallback:** On timeout (`HELIOX_LLM_TIMEOUT`, default 5.0s), network error, HTTP 4xx/5xx, or malformed JSON, `HybridPlanningParser` seamlessly delegates to `DeterministicFallbackProvider` with `parser_provenance="deterministic_fallback"`.

---

## 4. Multi-Criteria Planning Engine & Decision Policy

### 4.1 Decision Policy Formulation
The scheduler prioritizes tasks using a documented multi-criteria evaluation policy:

$$\text{SortScore} = \text{OverrideWeight} + \text{DependencyPrecedence} + \text{DeadlineUrgency} + \text{StrategyTieBreaker}$$

1. **Explicit Order Overrides ($\text{OverrideWeight}$):** Manual user reordering (e.g., *"Move assignment first"*) takes absolute precedence ($\pm 1000$).
2. **Topological Dependency Precedence ($\text{DependencyPrecedence}$):** If Task B depends on Task A, Task A is boosted to precede Task B.
3. **Earliest Deadline First ($\text{DeadlineUrgency}$):** Tasks with earlier explicit deadlines sort before distant or unspecified deadlines.
4. **Strategy Tie-Breaker:**
   - Default (`deadline_first`): Higher priority ($-\text{priority}$) breaks deadline ties.
   - Alternative (`shortest_first`): Shorter duration ($\text{duration} - 0.1 \times \text{priority}$) breaks deadline ties.

### 4.2 Mandatory Constraints vs. Preferences
- **Mandatory (Hard Constraints):**
  - Dependency sequencing: Task B start time $\ge$ Task A end time.
  - Continuous non-overlapping intervals: Every multi-hour task receives a single unbroken block $[T_{\text{start}}, T_{\text{start}} + \text{duration}]$ with zero overlap.
  - Available horizon boundary: Tasks ending after $T_{\text{start}} + \text{available\_hours}$ are flagged as outside horizon.
- **Preferences (Soft Constraints):**
  - Preferred time of day (e.g., *"after lunch"* $\to \min(T_{\text{start}}) \ge 13:00$).
  - Focus slot alignment based on historical energy patterns.

### 4.3 Overload Handling & Explainable Trade-offs
When $\sum \text{duration} > \text{available\_hours}$:
- The scheduler fits tasks sequentially up to `available_hours`.
- Tasks that exceed the horizon are categorized into `unscheduled_tasks` and `infeasible_tasks`.
- Feasibility status is marked as `INFEASIBLE_OVERLOAD`.
- Grounded explanation states the exact demanded workload vs. available capacity and outlines three actionable options (Capacity Expansion, Task Deferral, or Scope Reduction).

---

## 5. Conversational Plan Refinement & Lifecycle

Refinement interactions maintain stable UUID v4 proposal identity, monotonic versioning, and state consistency:

```
[User Request] ──> Proposal v1 (PROPOSED)
                         │
        "Move assignment first"
                         ▼
                   Proposal v2 (PROPOSED)
                         │
        "Prioritize exam instead"
                         ▼
                   Proposal v3 (PROPOSED)
                         │
        "I only have 2 hours now"
                         ▼
        Proposal v4 (PROPOSED, INFEASIBLE_OVERLOAD)
                         │
        "Accept this plan"
                         ▼
                   Proposal v4 (ACCEPTED)
                         │
           Safe DB Persistence (Tasks Created/Updated)
```

- **Optimistic Concurrency:** Refinements check `expected_version` to prevent race conditions or stale updates.
- **Idempotent Acceptance:** Accepting an already accepted proposal returns the previously persisted task IDs without creating duplicates.
- **Safe Rejection:** Rejecting a proposal transitions status to `REJECTED` and guarantees existing database tasks are never modified.

---

## 6. Personal Context & Prediction Provenance

Every duration estimate and prediction exposes transparent provenance:

| Provenance Label | Source Description | Usage Scenario |
|---|---|---|
| `conversational_input` / `explicit_user_input` | Explicitly stated in the prompt by the user (e.g., *"for 2 hours"*, *"lasting 90 mins"*) | Direct user specification |
| `task_api` | Stored duration on an existing database task record | Reusing user's existing tasks |
| `deterministic_heuristic` | Rule-based estimation derived from task keywords (e.g., study=2.0h, writing=1.5h, coding=2.0h) | Unspecified duration baseline |
| `statistical_estimate` | Historical user average duration for matching task types | Sufficient historical task data |
| `personal_ml_model` | Validated gradient-boosted / neural model predictions | Model passes readiness gate ($\ge 50$ samples, $R^2 > 0.3$) |

### Quantum Suitability Provenance
- Evaluated via `QuantumSuitabilityAnalyzer`.
- Problems with 1–4 tasks: Labeled as `SIMULATED_LOCAL` (local statevector simulation on classical CPU), with exact classical reference comparison.
- Problems with $>4$ tasks: Marked `UNSUPPORTED` / `QUANTUM_CONSIDERED_BUT_REJECTED` due to scale and formulation constraints.
- No false claims of quantum advantage or physical QPU execution are made.

---

## 7. Frontend Integration & Experience

The frontend UI in `frontend/src/components/assistant/JamMessage.tsx` renders rich, interactive plan proposal cards:
- **Header:** Displays proposal ID and version tag (`v{version} • {id.slice(0, 8)}`), task count, and status badge (`Feasible Schedule` vs. `Workload Overload`).
- **Chronological Schedule:** Visualizes start and end times, duration, task type, priority, and origin badge (`Proposed New` vs. `Existing`).
- **Unscheduled / Deferred Work Section:** Explicitly lists tasks that cannot fit into today's horizon with reasons.
- **Explainable Rationale & Trade-offs:** Collapsible section displaying ordering drivers, trade-offs, and realistic alternatives.
- **Quick Refinement Chips:** One-click refinement prompts pre-configured with F17 natural language interactions.
- **Direct Refinement Input:** Text field for free-form conversational adjustments.
- **Governance & Technical Details:** Displays behavioral provenance, quantum suitability, and interval guarantees.
- **Action Footer:** "Accept Plan" and "Reject Proposal" buttons wired to React Query mutations with optimistic status updates and query cache invalidation.

---

## 8. Verification & Test Suite Execution

### 8.1 F17 Conversational Planning Suite (`test_f17_conversational_planning.py`)
Command: `.venv\Scripts\pytest.exe -v backend/tests/test_f17_conversational_planning.py`

| Test Name | Focus Area | Result |
|---|---|:---:|
| `test_llm_provider_configuration_and_key_masking` | Multi-provider auto-detection, key masking (`_mask_key`) | **PASSED** |
| `test_llm_structured_output_validation_and_sanitization` | Schema validation, HTML stripping, priority/duration clamping | **PASSED** |
| `test_provider_failure_and_deterministic_fallback` | Timeouts, malformed JSON, network errors $\to$ deterministic fallback | **PASSED** |
| `test_multi_task_interpretation_and_deadlines` | Multi-task parsing, relative deadlines (`tomorrow`, `in 3 days`, `next week`) | **PASSED** |
| `test_scheduling_constraints_and_intervals` | Multi-hour continuous intervals, non-overlapping, dependency enforcement | **PASSED** |
| `test_decision_policy_overload_and_realistic_alternatives` | Overload detection, unscheduled tasks, 3 realistic alternatives | **PASSED** |
| `test_conversational_refinement_actions` | Parsing `move_first`, `reprioritize`, `alternative_schedule`, `add_buffer`, `reduce_hours` | **PASSED** |
| `test_acceptance_idempotency_and_duplicate_prevention` | Idempotent acceptance, duplicate prevention, cross-user isolation | **PASSED** |
| `test_honest_quantum_and_behavioral_provenance` | Simulation vs classical comparison, behavioral provenance tracking | **PASSED** |

**F17 Suite Result:** **9 passed in 70.10s (100% pass rate)**.

### 8.2 Combined Regression Verification (`test_f16` + `test_f17`)
Command: `.venv\Scripts\pytest.exe -v backend/tests/test_f16_conversational_intelligence.py backend/tests/test_f17_conversational_planning.py`

- **Phase F16 Suite (`test_f16_conversational_intelligence.py`):** 9 / 9 passed.
- **Phase F17 Suite (`test_f17_conversational_planning.py`):** 9 / 9 passed.
- **Total:** **18 passed in 97.09s (100% pass rate, zero regressions)**.

### 8.3 Frontend Health & Compilation
- **TypeScript Typecheck:** `npm run typecheck` $\to$ **Exit code 0** (No TypeScript errors).
- **Production Build:** `npm run build` $\to$ **Exit code 0** (`✓ built in 41.23s`, assets bundled cleanly).

---

## 9. Remaining User-Visible Limitations

1. **Third-Party LLM Key Required for External Providers:** If no external API key (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `GROQ_API_KEY`) is set in the environment, the system gracefully operates on the deterministic rule-based extractor with explicit provenance reporting (`deterministic_fallback`).
2. **Local Quantum Simulation:** Discrete schedule QUBO formulations with 1–4 tasks are simulated via CPU statevector calculations; hardware QPU execution requires cloud credentials (e.g., IBM Quantum / Amazon Braket).
3. **Personal ML Cold-Start:** Personal duration ML models remain in fallback mode until a user logs $\ge 50$ completed task duration records to satisfy the production readiness quality gate.

---

## 10. Confirmation of Preserved Work & Databases

- **Authoritative Databases:** `behavior_engine.db` and all tables (`tasks`, `users`, `plan_proposals`, etc.) were strictly preserved. No database drops, migrations, or overwrites occurred.
- **Untracked & Modified Files:** All existing untracked files and uncommitted changes from earlier phases were preserved.
- **Git State:** No `git reset`, `git clean`, or destructive operations were run. No commits or pushes were made.
