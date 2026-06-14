# QUANTUM LIFE AI - PYTHON ARCHITECTURE GUIDE

**Last Updated:** 2026-06-10  
**Version:** 1.0 - Production Grade  
**Status:** Official Architecture Standard

---

## 1. IMPORT STRATEGY: FULLY-QUALIFIED ABSOLUTE IMPORTS

### THE RULE

All imports must use **fully-qualified absolute paths** from the project root:

```python
# ✅ CORRECT: Fully-qualified absolute imports
from backend.app.cognitive import CognitiveEngine
from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.models import Task, BehaviorData

# ❌ WRONG: Relative app imports (don't work from project root)
from app.cognitive import CognitiveEngine

# ⚠️ NOT RECOMMENDED: Relative imports within same package (last resort only)
from .cognitive_engine import CognitiveEngine  # Only within backend/app/cognitive/
```

### WHY THIS STRATEGY

| Aspect | Fully-Qualified | Relative | app.* |
|--------|---|---|---|
| Works from any directory | ✅ Always | ⚠️ With PYTHONPATH | ❌ Never |
| Docker compatible | ✅ Yes | ✅ Yes | ❌ No |
| FastAPI compatible | ✅ Yes | ✅ Yes | ❌ No |
| IDE autocomplete | ✅✅ Perfect | ⚠️ Good | ⚠️ Flaky |
| Circular import detection | ✅ Obvious | ✅ Obvious | ❌ Hidden |
| Scale to 1000s modules | ✅ Yes | ⚠️ Maybe | ❌ No |
| Production-grade | ✅✅ Yes | ✅ Yes | ❌ No |

---

## 2. PACKAGE STRUCTURE

### Correct Structure

```
backend/
├── __init__.py                     # Minimal (no imports)
├── main.py                         # FastAPI app
├── app/                            # Core application
│   ├── __init__.py                # Minimal (no imports)
│   ├── domain/                    # AI algorithms & models
│   │   ├── __init__.py
│   │   ├── day_model.py
│   │   ├── evaluation.py
│   │   └── strategic_compression.py
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── task.py
│   │   └── behavior_data.py
│   ├── cognitive/                 # Cognitive layer
│   │   ├── __init__.py            # No imports!
│   │   ├── behavior_analyzer.py
│   │   └── cognitive_engine.py
│   ├── knowledge/                 # Knowledge graph
│   │   ├── __init__.py            # No imports!
│   │   └── knowledge_graph.py
│   ├── orchestrator/              # Central coordinator
│   │   ├── __init__.py            # No imports!
│   │   ├── ai_orchestrator.py
│   │   └── ai_brain.py
│   └── [other packages]/          # All follow same pattern
└── tests/                          # Test directory
```

### Key Principles

1. **Each package has `__init__.py` but imports NOTHING**
   - Users import directly from submodules
   - Prevents cascading imports
   - Enables test isolation

2. **Deeply nested is OK**
   - `backend.app.orchestrator.ai_brain` is fine
   - Long imports are GOOD (they're explicit)
   - Short imports often hide dependencies

3. **No `__all__` unless exposing public API**
   - Most `__init__.py` files should be nearly empty
   - Use `__all__ = []` to signal "no public exports"

---

## 3. WHAT GOES IN __init__.py

### ✅ ACCEPTABLE

```python
# Minimal docstring
"""Package description."""

# Version or metadata
__version__ = "1.0.0"

# Public API definition (ONLY if you're exposing a public interface)
# But still, users should import directly from submodules:
__all__ = []  # Empty is preferred
```

### ❌ NEVER DO THIS

```python
# ❌ NO: Imports at package level
from .module import ClassName
from backend.app.other.module import AnotherClass

# ❌ NO: Side effects
create_database()
initialize_logging()

# ❌ NO: Heavy dependencies
import expensive_ml_model
```

### Why?

When Python imports ANY submodule of a package, it executes the `__init__.py` file. If your `__init__.py` imports everything, the entire package gets loaded even if you only wanted one module.

**Example of the problem:**
```python
# backend/app/cognitive/__init__.py (BAD)
from .cognitive_engine import CognitiveEngine  # This ALWAYS loads cognitive_engine.py

# When you try to import just the analyzer:
from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer
# Python still loads cognitive_engine.py even though you didn't ask for it!
```

---

## 4. CIRCULAR IMPORT PATTERNS TO AVOID

### Pattern 1: Circular Imports Between Packages

```python
# ❌ BAD: Creates circular import
# backend/app/cognitive/cognitive_engine.py
from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph

# backend/app/knowledge/knowledge_graph.py
from backend.app.cognitive.cognitive_engine import CognitiveEngine
```

**Solution: Use TYPE_CHECKING**

```python
# backend/app/cognitive/cognitive_engine.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph

class CognitiveEngine:
    def __init__(self, kg: "AIKnowledgeGraph") -> None:
        self.kg = kg
```

### Pattern 2: Circular Imports in __init__.py

```python
# ❌ BAD: Package __init__.py causes cascade
# backend/app/orchestrator/__init__.py
from .ai_orchestrator import AIOrchestrator  # This triggers all orchestrator dependencies

# backend/app/orchestrator/ai_orchestrator.py
from backend.app.cognitive import CognitiveEngine  # Which triggers cognitive imports
from backend.app.knowledge import AIKnowledgeGraph  # Which might trigger orchestrator import
```

**Solution: Empty __init__.py**

```python
# backend/app/orchestrator/__init__.py
"""Orchestrator package."""
__all__ = []  # Users import directly from submodules
```

### Pattern 3: Module-Level Side Effects

```python
# ❌ BAD: Side effects during import
# backend/app/database/db.py
engine = create_engine("postgres://...")  # Runs on import!
session_local = sessionmaker(bind=engine)  # Runs on import!
```

**Solution: Lazy initialization**

```python
# backend/app/database/db.py
_engine = None
_session_local = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine("postgres://...")
    return _engine

def get_session():
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(bind=get_engine())
    return _session_local()
```

---

## 5. RELATIVE IMPORTS (When Acceptable)

### ✅ YES: Use relative imports WITHIN same package

```python
# backend/app/cognitive/cognitive_engine.py
# ✅ Importing from same package directory
from .behavior_analyzer import BehaviorAnalyzer

# ✅ Importing from parent package (rare)
from ..models import Task
```

### ❌ NO: Don't use relative imports across packages

```python
# backend/app/orchestrator/ai_orchestrator.py
# ❌ WRONG: Relative import across package boundary
from ..cognitive.cognitive_engine import CognitiveEngine

# ✅ CORRECT: Fully-qualified
from backend.app.cognitive.cognitive_engine import CognitiveEngine
```

---

## 6. NEW MODULE CHECKLIST

When creating a new module in `backend/app/`, use this checklist:

```
□ Create directory: backend/app/[new_module]/
□ Create __init__.py with only a docstring and __all__ = []
□ Create your module files inside
□ All imports use: from backend.app.X.Y import Z
□ No relative imports across package boundaries
□ No side effects in __init__.py
□ Run: python check_imports.py (should pass)
□ Run: python check_circular.py (should show no cycles)
□ Add to this ARCHITECTURE.md document
□ Update the test structure documentation
```

---

## 7. TESTING CONFIGURATION

All tests must work from the project root using:

```bash
pytest tests/
pytest backend/tests/
```

**Configuration files:**

1. **pytest.ini** - Sets `pythonpath = .` to ensure imports work
2. **conftest.py** - Adds project root to sys.path
3. **pyproject.toml** - Declares backend as an installable package

---

## 8. FASTAPI DEPLOYMENT

For FastAPI applications:

```python
# backend/main.py
from backend.app.orchestrator import AIOrchestrator
from backend.app.database import get_db
from backend.app.models import Task

app = FastAPI()

@app.get("/schedule")
def get_schedule(user_id: int, db: Session = Depends(get_db)):
    orchestrator = AIOrchestrator(db)
    return orchestrator.schedule_tasks()
```

**NO sys.path manipulation needed** - imports just work.

---

## 9. DOCKER DEPLOYMENT

For Docker containerization:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Install dependencies
RUN pip install -r backend/requirements.txt

# Run FastAPI with fully-qualified imports
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**These imports work in Docker because they're fully-qualified:**

```python
# backend/main.py - works in Docker
from backend.app.orchestrator import AIOrchestrator
```

---

## 10. VALIDATION SCRIPTS

Three scripts help maintain import hygiene:

### 1. Check Invalid Imports

```bash
python check_imports.py
python check_imports.py --verbose  # Show details
python check_imports.py --fix-report  # Generate fix commands
```

**What it checks:**
- No `from app.` imports (must be `from backend.app.`)
- No `import app.` statements
- No sys.path manipulation

### 2. Detect Circular Dependencies

```bash
python check_circular.py
python check_circular.py --verbose  # Show dependency graph
```

**What it checks:**
- Circular import chains (A → B → A)
- Deep cycles (A → B → C → A)

### 3. Automated Migration

If you have old-style imports to convert:

```bash
python migrate_imports.py                # Preview changes
python migrate_imports.py --apply        # Apply to files
```

---

## 11. COMMON MISTAKES & FIXES

### Mistake 1: Importing in __init__.py

```python
# ❌ backend/app/cognitive/__init__.py
from .cognitive_engine import CognitiveEngine

# User's test file
from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer  # Crashes!
# Because importing behavior_analyzer imports __init__.py which tries to import cognitive_engine
```

**Fix:**

```python
# ✅ backend/app/cognitive/__init__.py
"""Cognitive package."""
__all__ = []

# User's test file
from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer  # Works!
```

### Mistake 2: Using app.* imports

```python
# ❌ backend/app/orchestrator/ai_orchestrator.py
from app.cognitive import CognitiveEngine  # Fails if backend/ not on sys.path
```

**Fix:**

```python
# ✅ backend/app/orchestrator/ai_orchestrator.py
from backend.app.cognitive import CognitiveEngine  # Works always
```

### Mistake 3: sys.path manipulation

```python
# ❌ backend/app/context/context_builder.py
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
from day_model import Day  # Fragile!
```

**Fix:**

```python
# ✅ backend/app/context/context_builder.py
from backend.app.domain.day_model import Day  # Clean!
```

### Mistake 4: Heavy __init__.py imports

```python
# ❌ backend/app/engines/__init__.py
from .brain_workflow import QuantumLifeBrain  # Triggers entire engines package
from .decision_engine import DecisionEngine    # All dependencies loaded
from .learning_engine import LearningEngine    # Even if only one is needed
# ... 7 more imports
```

**Fix:**

```python
# ✅ backend/app/engines/__init__.py
"""Engines package."""
__all__ = []

# Users import what they need directly
from backend.app.engines.decision_engine import DecisionEngine
```

---

## 12. FOR FUTURE MICROSERVICES

When you split into microservices:

```
# Before (monolith)
backend/app/
  ├── cognitive/
  ├── orchestrator/
  ├── memory/
  └── services/

# After (microservices)
services/
  ├── cognitive-service/
  │   └── app/
  │       └── cognitive/
  ├── orchestration-service/
  │   └── app/
  │       └── orchestrator/
  └── memory-service/
      └── app/
          └── memory/
```

The fully-qualified import strategy makes this clean:

```python
# In cognitive-service, imports within the service:
from backend.app.cognitive import CognitiveEngine  # Just works

# Cross-service calls use API layer, not imports
client = HTTPClient("http://orchestration-service:8001")
response = client.post("/schedule", data=...)
```

---

## 13. TEAM STANDARDS

### Before Committing Code

```bash
# 1. Run import validation
python check_imports.py

# 2. Run circular dependency check
python check_circular.py

# 3. Run tests
pytest

# 4. Verify specific imports work
python -c "from backend.app.cognitive import CognitiveEngine; print('✓ Imports work')"
```

### Code Review Checklist

- [ ] No `from app.*` imports (should be `from backend.app.*`)
- [ ] No sys.path manipulation
- [ ] __init__.py files are minimal (empty is best)
- [ ] No circular imports (run check_circular.py)
- [ ] All imports are fully-qualified paths
- [ ] Tests can run from project root with pytest

---

## 14. QUESTIONS & ANSWERS

**Q: Why can't we use `from app.X import Y`?**  
A: Because `app` isn't a top-level package. It's `backend/app/`, so the fully-qualified name is `backend.app.X`. Using `app.X` only works if the `backend/` directory is on sys.path, which fails in Docker and production.

**Q: Why can't we put imports in __init__.py?**  
A: Because __init__.py is executed whenever ANY submodule is imported. If it imports everything, even small imports become heavy. This breaks test isolation and wastes startup time.

**Q: Can we use relative imports?**  
A: Only within the same package (use `from .sibling import X`). Never across package boundaries (never use `from ..sibling import X` unless it's a small file structure).

**Q: What if we have a circular import?**  
A: Use `TYPE_CHECKING` blocks to break the cycle, or refactor to separate concerns.

**Q: Can we use `import backend.app.cognitive.cognitive_engine as ce`?**  
A: Yes, but prefer `from backend.app.cognitive.cognitive_engine import CognitiveEngine` for clarity.

---

## 15. CONTACT & UPDATES

- **Architecture Owner:** [Your Team]
- **Last Review:** 2026-06-10
- **Next Review:** 2026-09-10

For questions about this architecture, file an issue or contact the architecture team.

---

**This document is OFFICIAL ARCHITECTURE for all Python code in QUANTUM_LIFE_AI.**  
**All team members must follow these standards.**
