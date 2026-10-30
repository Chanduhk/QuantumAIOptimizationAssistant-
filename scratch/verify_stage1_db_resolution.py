"""Stage 1: Verify Database Configuration & URL Resolution across all 6 scenarios."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.db import get_database_url, DEFAULT_SQLITE_PATH

def run_stage1_db_resolution():
    print("=== STAGE 1: DATABASE CONFIGURATION & URL RESOLUTION AUDIT ===")
    
    # Baseline check: current resolved URL in running environment
    active_url = get_database_url()
    print(f"1. Active resolved DATABASE_URL: {active_url}")
    assert "behavior_engine.db" in active_url
    assert Path(active_url.replace("sqlite:///", "")).exists(), "Authoritative DB file does not exist!"
    
    # Scenario A: Missing / empty DATABASE_URL
    orig_env = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = ""
        resolved_empty = get_database_url()
        print(f"2. Missing DATABASE_URL resolved to default: {resolved_empty}")
        assert resolved_empty == f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
        
        # Scenario B: Explicit relative SQLite URLs
        for rel_variant in ["sqlite:///./behavior_engine.db", "sqlite:///behavior_engine.db"]:
            os.environ["DATABASE_URL"] = rel_variant
            resolved_rel = get_database_url()
            print(f"3. Relative variant '{rel_variant}' resolved to: {resolved_rel}")
            assert (PROJECT_ROOT / "behavior_engine.db").as_posix().lower() in resolved_rel.lower()
            
        # Scenario C: In-memory SQLite (used by automated unit tests)
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        resolved_mem = get_database_url()
        print(f"4. Test in-memory URL resolved to: {resolved_mem}")
        assert resolved_mem == "sqlite:///:memory:"

        # Scenario D: Explicit absolute SQLite URL (custom path)
        custom_abs = "sqlite:///C:/external_storage/custom.db"
        os.environ["DATABASE_URL"] = custom_abs
        resolved_custom = get_database_url()
        print(f"5. Explicit absolute SQLite URL resolved to: {resolved_custom}")
        assert resolved_custom == custom_abs

        # Scenario E: Supported non-SQLite database URLs (PostgreSQL, MySQL, etc.)
        postgres_url = "postgresql://user:secret@localhost:5432/production_behavior"
        os.environ["DATABASE_URL"] = postgres_url
        resolved_pg = get_database_url()
        print(f"6. External PostgreSQL URL resolved to: {resolved_pg}")
        assert resolved_pg == postgres_url, "External database was silently redirected!"

        # Scenario F: Legacy postgres:// scheme normalization
        legacy_pg = "postgres://user:secret@localhost:5432/production_behavior"
        os.environ["DATABASE_URL"] = legacy_pg
        resolved_legacy = get_database_url()
        print(f"7. Legacy postgres:// URL normalized to: {resolved_legacy}")
        assert resolved_legacy == postgres_url

    finally:
        if orig_env is not None:
            os.environ["DATABASE_URL"] = orig_env
        else:
            os.environ.pop("DATABASE_URL", None)

    print("\nPASS: All 6 database URL resolution scenarios verified successfully.")
    print("PASS: Authoritative database file confirmed at E:/quantum_life_ai/behavior_engine.db.")
    print("=== STAGE 1 VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    run_stage1_db_resolution()
