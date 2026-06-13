#!/usr/bin/env python3
"""Automated import validation and checking.

Detects invalid import patterns and helps enforce the fully-qualified import
strategy across the entire codebase.

Usage:
    python check_imports.py                 # Check all files
    python check_imports.py --fix-report    # Generate a fixing report
    python check_imports.py --verbose       # Show all details
"""
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Invalid import patterns that violate the architecture
INVALID_PATTERNS = [
    # (pattern, description, severity)
    (r"^\s*from\s+app\.", "Relative app.* imports (should be: from backend.app.*)", "ERROR"),
    (r"^\s*import\s+app\.", "Relative app.* imports (should be: from backend.app.*)", "ERROR"),
    (r"^\s*from\s+[a-z_]+\s+import.*\bapp\b", "Importing app module directly", "WARNING"),
]

# Acceptable import patterns
ACCEPTABLE_PATTERNS = [
    r"^\s*from\s+backend\.app\.",
    r"^\s*import\s+backend\.app\.",
    r"^\s*from\s+backend\.",
    r"^\s*import\s+backend\.",
    r"^\s*from\s+\.",  # Relative imports within package
    r"^\s*from\s+\.\.",  # Relative imports from parent
    r"^\s*from\s+__future__",  # Future imports
    r"^\s*from\s+typing",  # Standard library
    r"^\s*import\s+sys",  # Standard library
    r"^\s*import\s+os",  # Standard library
    r"^\s*import\s+re",  # Standard library
    r"^\s*import\s+json",  # Standard library
    r"^\s*import\s+logging",  # Standard library
    r"^\s*from\s+pathlib",  # Standard library
    r"^\s*from\s+dataclasses",  # Standard library
    r"^\s*from\s+datetime",  # Standard library
    r"^\s*from\s+[a-z_]+",  # Third-party packages
    r"^\s*import\s+[a-z_]+",  # Third-party packages
]


def is_python_file(path: Path) -> bool:
    """Check if a file is a Python source file."""
    return path.suffix == ".py" and not path.name.startswith(".")


def check_file(filepath: Path) -> List[Tuple[int, str, str, str]]:
    """Check a single file for invalid import patterns.
    
    Returns:
        List of (line_number, line_content, pattern_desc, severity) tuples
    """
    errors = []
    
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, IOError):
        return errors
    
    for line_no, line in enumerate(content.split("\n"), 1):
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        
        # Check for invalid patterns
        for pattern, desc, severity in INVALID_PATTERNS:
            if re.match(pattern, line):
                errors.append((line_no, stripped, desc, severity))
                break
    
    return errors


def scan_directory(directory: Path) -> Dict[str, List[Tuple[int, str, str, str]]]:
    """Scan a directory recursively for import issues.
    
    Returns:
        Dictionary mapping file paths to list of errors
    """
    issues = {}
    
    for py_file in directory.rglob("*.py"):
        # Skip virtual environments and caches
        if any(part in py_file.parts for part in ["venv", ".venv", "__pycache__", ".git"]):
            continue
        
        errors = check_file(py_file)
        if errors:
            issues[str(py_file.relative_to(directory))] = errors
    
    return issues


def print_report(issues: Dict[str, List[Tuple[int, str, str, str]]], verbose: bool = False):
    """Print a formatted report of import issues."""
    if not issues:
        print("✅ All imports are valid!")
        return
    
    print("\n" + "=" * 80)
    print("IMPORT VALIDATION REPORT")
    print("=" * 80 + "\n")
    
    total_errors = sum(len(errs) for errs in issues.values())
    error_count = sum(
        1 for errs in issues.values() 
        for _, _, _, severity in errs 
        if severity == "ERROR"
    )
    warning_count = total_errors - error_count
    
    print(f"Total Issues: {total_errors}")
    print(f"  Errors:   {error_count} ❌")
    print(f"  Warnings: {warning_count} ⚠️\n")
    
    for filepath in sorted(issues.keys()):
        errors = issues[filepath]
        print(f"\n{filepath}")
        print("-" * 80)
        
        for line_no, line_content, pattern_desc, severity in errors:
            icon = "❌" if severity == "ERROR" else "⚠️"
            print(f"  Line {line_no}: {icon} {pattern_desc}")
            if verbose:
                print(f"           {line_content}")
    
    print("\n" + "=" * 80)
    print("FIX: Replace 'from app.' with 'from backend.app.'")
    print("=" * 80 + "\n")


def generate_fix_commands(issues: Dict[str, List[Tuple[int, str, str, str]]]) -> List[str]:
    """Generate fix commands for identified issues."""
    fixes = []
    
    for filepath in sorted(issues.keys()):
        errors = issues[filepath]
        for line_no, line_content, _, _ in errors:
            # Extract the old import and suggest the new one
            old = line_content
            if re.match(r"from app\.", line_content):
                new = line_content.replace("from app.", "from backend.app.", 1)
                fixes.append(f"# {filepath}:{line_no}")
                fixes.append(f"#   OLD: {old}")
                fixes.append(f"#   NEW: {new}")
                fixes.append("")
    
    return fixes


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    fix_report = "--fix-report" in sys.argv
    
    # Scan the backend directory
    backend_path = Path(__file__).parent / "backend"
    if not backend_path.exists():
        print("❌ Error: 'backend' directory not found")
        sys.exit(1)
    
    print(f"Scanning: {backend_path}")
    issues = scan_directory(backend_path)
    
    # Print the report
    print_report(issues, verbose=verbose)
    
    # Generate fix report if requested
    if fix_report and issues:
        print("\nGenerated fix commands:")
        print("=" * 80)
        for line in generate_fix_commands(issues):
            print(line)
        print("=" * 80 + "\n")
    
    # Exit with error code if there are errors
    if issues:
        error_count = sum(
            1 for errs in issues.values() 
            for _, _, _, severity in errs 
            if severity == "ERROR"
        )
        sys.exit(1 if error_count > 0 else 0)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
