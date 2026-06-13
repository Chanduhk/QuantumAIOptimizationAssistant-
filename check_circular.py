#!/usr/bin/env python3
"""Circular import detection tool.

Analyzes import dependencies to detect circular import patterns that could
cause runtime errors or import failures.

Usage:
    python check_circular.py                  # Check for circular imports
    python check_circular.py --verbose        # Show detailed dependency graph
    python check_circular.py --graph          # Generate dependency graph
"""
import ast
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional, Set


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that extracts import statements."""
    
    def __init__(self):
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, List[str]] = defaultdict(list)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        if node.module:
            self.imports.add(node.module)
            for alias in node.names:
                if alias.name != "*":
                    self.from_imports[node.module].append(alias.name)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)


def get_module_name(filepath: Path, root_dir: Path) -> str:
    """Convert file path to module name.
    
    Example:
        backend/app/cognitive/cognitive_engine.py -> backend.app.cognitive.cognitive_engine
    """
    relative = filepath.relative_to(root_dir)
    parts = list(relative.parts[:-1]) + [relative.stem]
    return ".".join(parts)


def extract_imports(filepath: Path) -> Set[str]:
    """Extract imports from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        visitor = ImportVisitor()
        visitor.visit(tree)
        return visitor.imports
    except (SyntaxError, UnicodeDecodeError):
        return set()


def normalize_import(imp: str, current_module: str) -> Optional[str]:
    """Normalize import statements to absolute module paths.
    
    Examples:
        'backend.app.X' -> 'backend.app.X'
        'app.X' -> 'app.X' (ambiguous, needs sys.path context)
        '.' -> parent of current module
        '.X' -> sibling of current module
    """
    # Fully-qualified imports
    if imp.startswith("backend."):
        return imp
    
    # Relative imports starting with dots
    if imp.startswith("."):
        parts = current_module.split(".")
        dots = len(imp) - len(imp.lstrip("."))
        
        if dots > len(parts):
            return None  # Invalid relative import
        
        base = ".".join(parts[:-dots]) if dots < len(parts) else ""
        remaining = imp.lstrip(".")
        
        return f"{base}.{remaining}" if remaining else base
    
    # Other imports (third-party, stdlib)
    return None


def build_dependency_graph(root_dir: Path) -> Dict[str, Set[str]]:
    """Build a dependency graph of backend modules.
    
    Returns:
        Dictionary mapping module names to sets of their dependencies
    """
    graph = {}
    
    for py_file in root_dir.rglob("*.py"):
        # Skip non-backend files
        if "backend" not in py_file.parts:
            continue
        if any(part in py_file.parts for part in ["venv", ".venv", "__pycache__"]):
            continue
        
        module_name = get_module_name(py_file, root_dir)
        imports = extract_imports(py_file)
        
        # Normalize imports to backend modules only
        backend_deps = set()
        for imp in imports:
            normalized = normalize_import(imp, module_name)
            if normalized and normalized.startswith("backend"):
                backend_deps.add(normalized)
        
        graph[module_name] = backend_deps
    
    return graph


def find_cycles_dfs(
    graph: Dict[str, Set[str]],
    start_node: str,
    visited: Set[str],
    path: List[str],
) -> List[List[str]]:
    """Find cycles starting from a node using DFS."""
    cycles = []
    
    if start_node in path:
        # Found a cycle
        cycle_start = path.index(start_node)
        cycle = path[cycle_start:] + [start_node]
        cycles.append(cycle)
        return cycles
    
    if start_node in visited:
        return cycles
    
    visited.add(start_node)
    path = path + [start_node]
    
    for neighbor in graph.get(start_node, set()):
        cycles.extend(find_cycles_dfs(graph, neighbor, visited, path))
    
    return cycles


def find_all_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find all cycles in the dependency graph."""
    all_cycles = []
    visited: Set[str] = set()
    
    for node in graph:
        cycles = find_cycles_dfs(graph, node, set(), [])
        all_cycles.extend(cycles)
    
    # Deduplicate cycles
    unique_cycles = []
    seen = set()
    for cycle in all_cycles:
        # Normalize cycle representation (rotate to smallest lexicographic form)
        normalized = tuple(sorted(cycle[:-1]))  # Exclude repeated last element
        if normalized not in seen:
            seen.add(normalized)
            unique_cycles.append(cycle)
    
    return unique_cycles


def print_dependency_graph(graph: Dict[str, Set[str]], verbose: bool = False):
    """Print the dependency graph."""
    if not verbose:
        return
    
    print("\n" + "=" * 80)
    print("DEPENDENCY GRAPH (Backend Modules Only)")
    print("=" * 80 + "\n")
    
    for module in sorted(graph.keys()):
        deps = graph[module]
        if deps:
            print(f"{module}")
            for dep in sorted(deps):
                print(f"  ├─ {dep}")
        else:
            print(f"{module} (no backend deps)")


def print_cycles_report(cycles: List[List[str]]):
    """Print a formatted report of detected cycles."""
    if not cycles:
        print("✅ No circular imports detected!")
        return
    
    print("\n" + "=" * 80)
    print("CIRCULAR IMPORT DETECTION REPORT")
    print("=" * 80 + "\n")
    
    print(f"Found {len(cycles)} circular import chain(s):\n")
    
    for i, cycle in enumerate(cycles, 1):
        print(f"{i}. Cycle (length {len(cycle) - 1}):")
        for j, module in enumerate(cycle[:-1]):
            next_module = cycle[j + 1]
            print(f"   {module}")
            print(f"     └→ imports {next_module}")
        print()
    
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    print("""
1. Break cycles by moving imports inside functions (lazy imports)
2. Reorganize modules to separate concerns
3. Use TYPE_CHECKING blocks for type-hint-only imports
4. Consider dependency injection instead of direct imports

Example fix (using TYPE_CHECKING):
    if TYPE_CHECKING:
        from backend.app.module import SomeClass
    
    def function(obj: 'SomeClass') -> None:
        # Use string annotation instead of import
        pass

Example fix (lazy import):
    def function():
        from backend.app.module import SomeClass  # Import inside function
        return SomeClass()
""")


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    show_graph = "--graph" in sys.argv
    
    root_dir = Path(__file__).parent
    
    print(f"Analyzing dependencies in: {root_dir}")
    print("Building dependency graph...\n")
    
    graph = build_dependency_graph(root_dir)
    
    if show_graph:
        print_dependency_graph(graph, verbose=True)
    
    # Find cycles
    cycles = find_all_cycles(graph)
    print_cycles_report(cycles)
    
    if cycles:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
