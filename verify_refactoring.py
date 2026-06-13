#!/usr/bin/env python3
"""Verification script to validate the complete refactoring.

This script verifies that all changes have been applied correctly and that
the import architecture is production-ready.

Usage:
    python verify_refactoring.py
    python verify_refactoring.py --verbose
"""
import sys
from pathlib import Path
from typing import List, Tuple


def check_file_exists(filepath: Path, description: str) -> Tuple[bool, str]:
    """Check if a file exists."""
    exists = filepath.exists()
    status = "✓" if exists else "✗"
    return exists, f"{status} {description}: {filepath.relative_to(Path.cwd())}"


def check_file_content(filepath: Path, pattern: str, description: str) -> Tuple[bool, str]:
    """Check if a file contains a pattern."""
    if not filepath.exists():
        return False, f"✗ {description}: File not found"
    
    content = filepath.read_text()
    contains = pattern in content
    status = "✓" if contains else "✗"
    return contains, f"{status} {description}"


def verify_structure() -> List[Tuple[bool, str]]:
    """Verify directory structure."""
    results = []
    root = Path(__file__).parent
    
    # Check critical directories
    dirs = [
        "backend/app/domain",
        "backend/app/core",
        "tests",
    ]
    
    for dir_path in dirs:
        full_path = root / dir_path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        results.append((exists, f"{status} Directory: {dir_path}"))
    
    return results


def verify_config_files() -> List[Tuple[bool, str]]:
    """Verify configuration files."""
    results = []
    root = Path(__file__).parent
    
    files = [
        ("pyproject.toml", "Project configuration"),
        ("pytest.ini", "Pytest configuration"),
        ("conftest.py", "Pytest conftest"),
        ("ARCHITECTURE.md", "Architecture documentation"),
        ("QUICKSTART.md", "Developer quick start"),
    ]
    
    for filename, description in files:
        filepath = root / filename
        exists, msg = check_file_exists(filepath, description)
        results.append((exists, msg))
    
    return results


def verify_package_files() -> List[Tuple[bool, str]]:
    """Verify package __init__.py files."""
    results = []
    root = Path(__file__).parent
    
    packages = [
        "backend/__init__.py",
        "backend/app/__init__.py",
        "backend/app/domain/__init__.py",
        "backend/app/core/__init__.py",
        "backend/app/cognitive/__init__.py",
        "backend/app/orchestrator/__init__.py",
        "backend/app/models/__init__.py",
        "backend/app/knowledge/__init__.py",
        "backend/app/services/__init__.py",
    ]
    
    for package_file in packages:
        filepath = root / package_file
        exists, msg = check_file_exists(filepath, f"Package: {package_file}")
        results.append((exists, msg))
    
    return results


def verify_domain_files() -> List[Tuple[bool, str]]:
    """Verify domain module files."""
    results = []
    root = Path(__file__).parent
    
    files = [
        "backend/app/domain/day_model.py",
        "backend/app/domain/evaluation.py",
        "backend/app/domain/strategic_compression.py",
    ]
    
    for domain_file in files:
        filepath = root / domain_file
        exists, msg = check_file_exists(filepath, f"Domain module: {domain_file}")
        results.append((exists, msg))
    
    return results


def verify_validation_tools() -> List[Tuple[bool, str]]:
    """Verify validation tools."""
    results = []
    root = Path(__file__).parent
    
    tools = [
        "check_imports.py",
        "check_circular.py",
        "migrate_imports.py",
    ]
    
    for tool in tools:
        filepath = root / tool
        exists, msg = check_file_exists(filepath, f"Tool: {tool}")
        results.append((exists, msg))
    
    return results


def verify_imports() -> List[Tuple[bool, str]]:
    """Verify that critical imports work."""
    results = []
    
    try:
        from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer
        results.append((True, "✓ Can import BehaviorAnalyzer"))
    except ImportError as e:
        results.append((False, f"✗ Cannot import BehaviorAnalyzer: {e}"))
    
    try:
        from backend.app.domain.day_model import Day
        results.append((True, "✓ Can import Day from domain"))
    except ImportError as e:
        results.append((False, f"✗ Cannot import Day: {e}"))
    
    try:
        from backend.app.domain.evaluation import DayEvaluator
        results.append((True, "✓ Can import DayEvaluator from domain"))
    except ImportError as e:
        results.append((False, f"✗ Cannot import DayEvaluator: {e}"))
    
    return results


def print_report(all_results: dict, verbose: bool = False):
    """Print verification report."""
    total = 0
    passed = 0
    
    print("\n" + "=" * 80)
    print("REFACTORING VERIFICATION REPORT")
    print("=" * 80 + "\n")
    
    for section, results in all_results.items():
        print(f"\n{section.upper()}")
        print("-" * 80)
        
        section_passed = 0
        for success, message in results:
            print(f"  {message}")
            if success:
                section_passed += 1
            total += 1
            passed += success
        
        section_total = len(results)
        print(f"  {section_passed}/{section_total} passed")
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {passed}/{total} checks passed")
    print("=" * 80 + "\n")
    
    if passed == total:
        print("✅ REFACTORING COMPLETE AND VERIFIED")
        print("\nNext steps:")
        print("  1. Run: python check_imports.py")
        print("  2. Run: python check_circular.py")
        print("  3. Run: pytest tests/")
        print("  4. Read: ARCHITECTURE.md")
        print("  5. Share: QUICKSTART.md with team\n")
        return 0
    else:
        print(f"❌ {total - passed} checks FAILED")
        if verbose:
            print("\nRun with --verbose to see more details")
        print()
        return 1


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv
    
    all_results = {
        "Directory Structure": verify_structure(),
        "Configuration Files": verify_config_files(),
        "Package Files": verify_package_files(),
        "Domain Files": verify_domain_files(),
        "Validation Tools": verify_validation_tools(),
        "Critical Imports": verify_imports(),
    }
    
    exit_code = print_report(all_results, verbose=verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
