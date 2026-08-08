# DEVELOPER QUICK START CHECKLIST

## Before You Code

- [ ] Read [ARCHITECTURE.md](ARCHITECTURE.md)
- [ ] Understand fully-qualified imports: `from backend.app.X.Y import Z`
- [ ] Know that __init__.py should be empty (or near-empty)

## Creating a New Module

### Step 1: Create Directory

```bash
mkdir -p backend/app/[my_module]
```

### Step 2: Create __init__.py

```python
# backend/app/[my_module]/__init__.py
"""[Module name] - [brief description]."""

__all__ = []
```

### Step 3: Create Your Module

```python
# backend/app/[my_module]/my_module.py
from backend.app.other_module import SomeClass

class MyClass:
    def __init__(self, obj: SomeClass):
        self.obj = obj
```

**Key Rules:**
- ✅ Use fully-qualified imports: `from backend.app.X`
- ❌ Never use: `from app.X`
- ❌ Never use sys.path manipulation
- ✅ Only use relative imports within same package: `from .sibling import X`

### Step 4: Validate

```bash
# Check for import issues
python check_imports.py

# Check for circular imports
python check_circular.py

# Run your tests
pytest tests/test_my_module.py
```

## Importing in Your Code

### ✅ DO THIS

```python
# At the top of your file
from backend.app.cognitive import BehaviorAnalyzer
from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.models import Task, BehaviorData

# In your class or function
class MyProcessor:
    def __init__(self, analyzer: BehaviorAnalyzer):
        self.analyzer = analyzer
```

### ❌ DON'T DO THIS

```python
# Wrong: relative app.* imports
from app.cognitive import BehaviorAnalyzer  # ❌ FAILS from project root

# Wrong: sys.path manipulation
import sys
sys.path.insert(0, "/some/path")
from my_module import Something  # ❌ FRAGILE

# Wrong: heavy __init__.py imports
from backend.app.cognitive import BehaviorAnalyzer  # ❌ If __init__.py imports everything

# Wrong: relative imports across packages
from ..cognitive.cognitive_engine import CognitiveEngine  # ❌ From orchestrator
# Use instead: from backend.app.cognitive.cognitive_engine import CognitiveEngine

# Wrong: circular imports
# File A imports from File B, File B imports from File A
```

## Testing

### Running Tests

```bash
# From project root
pytest tests/

# With coverage
pytest --cov=backend tests/

# Specific test file
pytest tests/test_behavior_analyzer.py

# Specific test
pytest tests/test_behavior_analyzer.py::test_analyze
```

### Import Testing

Your test should be able to import directly:

```python
# tests/test_my_module.py
from backend.app.my_module import MyClass

def test_my_class():
    obj = MyClass()
    assert obj is not None
```

## Before Committing

```bash
# 1. Validate imports
python check_imports.py
# Should show: ✅ All imports are valid!

# 2. Check circular dependencies
python check_circular.py
# Should show: ✅ No circular imports detected!

# 3. Run tests
pytest

# 4. Check specific imports work
python -c "from backend.app.my_module import MyClass; print('✓')"
```

## Common Issues & Fixes

### Issue 1: ModuleNotFoundError: No module named 'app'

**Cause:** Using `from app.X` instead of `from backend.app.X`

**Fix:**
```bash
# Use the migration script
python migrate_imports.py --apply
```

### Issue 2: Imports work in IDE but fail in pytest

**Cause:** Running pytest from wrong directory or missing pytest.ini

**Fix:**
```bash
# Run pytest from project root
cd /path/to/quantum_life_ai
pytest tests/

# Or ensure pytest.ini exists with pythonpath = .
```

### Issue 3: Circular import error at startup

**Cause:** Your __init__.py imports modules that depend on each other

**Fix:** Empty your __init__.py files:
```python
# backend/app/[package]/__init__.py
"""[Package]."""
__all__ = []
```

### Issue 4: Test isolation problems (tests interfere with each other)

**Cause:** sys.path is being manipulated during imports

**Fix:** Use fully-qualified imports only, no sys.path manipulation

## Running FastAPI for Development

```bash
cd /path/to/quantum_life_ai
python -m uvicorn backend.main:app --reload
```

## Docker Build

```bash
# From project root
docker build -f backend/Dockerfile -t quantum-life-ai:latest .

# Run
docker run -p 8000:8000 quantum-life-ai:latest
```

## Project Structure Reference

```
quantum_life_ai/
├── backend/              # Main backend package
│   ├── __init__.py      # Minimal
│   ├── main.py          # FastAPI app
│   └── app/             # Application core
│       ├── __init__.py  # Minimal
│       ├── domain/      # Algorithms (day_model, evaluation, etc.)
│       ├── models/      # Data models (Task, BehaviorData)
│       ├── cognitive/   # Goal parsing (BehaviorAnalyzer, CognitiveEngine)
│       ├── knowledge/   # Knowledge graph
│       ├── orchestrator/# AI brain (AIOrchestrator, AIBrain)
│       ├── services/    # Business logic (BehaviorIntelligenceEngine)
│       ├── memory/      # Vector memory and history
│       ├── engines/     # AI engines (Decision, Planning, etc.)
│       ├── adaptive/    # Adaptive scheduling
│       ├── ai_rl/       # Reinforcement learning
│       ├── context/     # State management
│       ├── database/    # SQLAlchemy
│       ├── ml/          # ML models (FeatureStore, ModelRegistry)
│       ├── pipeline/    # Request pipelines
│       ├── interface/   # API layer
│       ├── monitoring/  # System monitoring
│       ├── learning/    # Autonomous learning
│       └── recommendation/  # Recommendations
│
├── tests/               # Unit tests (run with pytest)
├── pytest.ini          # Pytest configuration
├── conftest.py         # Pytest fixtures
├── pyproject.toml      # Project metadata
├── ARCHITECTURE.md     # Architecture rules
├── check_imports.py    # Validation tool
├── check_circular.py   # Circular import checker
└── migrate_imports.py  # Import migration tool
```

## Key Files to Know

| File | Purpose |
|------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Read this first!** Complete architecture guide |
| [check_imports.py](check_imports.py) | Validates import patterns |
| [check_circular.py](check_circular.py) | Detects circular dependencies |
| [migrate_imports.py](migrate_imports.py) | Auto-converts old-style imports |
| [pytest.ini](pytest.ini) | Test configuration |
| [conftest.py](conftest.py) | Pytest setup |
| [pyproject.toml](pyproject.toml) | Project metadata |

## Questions?

1. Check [ARCHITECTURE.md](ARCHITECTURE.md) section 13 (FAQ)
2. Run validation scripts: `python check_imports.py`
3. Run tests: `pytest --verbose`
4. Ask team lead

---

**Remember:** 
- `from backend.app.X import Y` ✅
- `from app.X import Y` ❌
- Empty __init__.py files ✅
- Heavy __init__.py imports ❌
