#!/usr/bin/env python3
"""Automated import migration script.

Converts old import patterns to the new fully-qualified format:
    from app.X import Y  →  from backend.app.X import Y
    import app.X  →  import backend.app.X

Usage:
    python migrate_imports.py                  # Preview changes
    python migrate_imports.py --apply          # Apply changes to files
    python migrate_imports.py --dry-run        # Test without writing
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


def is_python_file(path: Path) -> bool:
    """Check if a file is a Python source file."""
    return path.suffix == ".py" and not path.name.startswith(".")


def migrate_imports_in_file(filepath: Path) -> Tuple[str, int]:
    """Migrate imports in a single file.
    
    Returns:
        (new_content, number_of_changes)
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, IOError):
        return content, 0
    
    original = content
    changes = 0
    
    # Pattern 1: from app.X import Y → from backend.app.X import Y
    content = re.sub(
        r'^(\s*)from app\.',
        r'\1from backend.app.',
        content,
        flags=re.MULTILINE
    )
    
    # Pattern 2: import app.X → import backend.app.X
    content = re.sub(
        r'^(\s*)import app\.',
        r'\1import backend.app.',
        content,
        flags=re.MULTILINE
    )
    
    # Count changes
    if content != original:
        changes = content.count("backend.app") - original.count("backend.app")
    
    return content, changes


def migrate_directory(
    directory: Path,
    apply_changes: bool = False,
    verbose: bool = False
) -> Tuple[int, int, List[str]]:
    """Migrate imports in all Python files in a directory.
    
    Returns:
        (total_changes, files_modified, file_list)
    """
    total_changes = 0
    files_modified = []
    modified_files = []
    
    for py_file in directory.rglob("*.py"):
        # Skip virtual environments and caches
        if any(part in py_file.parts for part in ["venv", ".venv", "__pycache__", ".git"]):
            continue
        
        new_content, changes = migrate_imports_in_file(py_file)
        
        if changes > 0:
            total_changes += changes
            files_modified.append(py_file)
            modified_files.append(str(py_file.relative_to(directory)))
            
            if apply_changes:
                py_file.write_text(new_content, encoding="utf-8")
                if verbose:
                    print(f"✓ {py_file.relative_to(directory)} ({changes} changes)")
            else:
                if verbose:
                    print(f"  {py_file.relative_to(directory)} ({changes} changes)")
    
    return total_changes, len(files_modified), modified_files


def print_summary(total_changes: int, files_modified: List[str], applied: bool = False):
    """Print a summary of migration results."""
    print("\n" + "=" * 80)
    if applied:
        print("MIGRATION COMPLETE")
    else:
        print("MIGRATION PREVIEW (no changes applied)")
    print("=" * 80 + "\n")
    
    print(f"Total changes: {total_changes}")
    print(f"Files modified: {len(files_modified)}\n")
    
    if files_modified:
        print("Modified files:")
        for filepath in sorted(files_modified):
            print(f"  • {filepath}")
    
    print("\n" + "=" * 80)
    if not applied:
        print("To apply these changes, run:")
        print("  python migrate_imports.py --apply")
    print("=" * 80 + "\n")


def main():
    """Main entry point."""
    apply_changes = "--apply" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    root_dir = Path(__file__).parent
    backend_dir = root_dir / "backend"
    
    if not backend_dir.exists():
        print("❌ Error: 'backend' directory not found")
        sys.exit(1)
    
    print(f"Migrating imports in: {backend_dir}\n")
    
    total_changes, files_count, modified_files = migrate_directory(
        backend_dir,
        apply_changes=apply_changes,
        verbose=verbose
    )
    
    print_summary(total_changes, modified_files, applied=apply_changes)
    
    if total_changes == 0:
        print("✅ No import changes needed!")
        sys.exit(0)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
