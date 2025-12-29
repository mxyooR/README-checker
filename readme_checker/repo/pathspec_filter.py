"""Pathspec-based file filtering.

This module uses the pathspec library for proper gitignore handling,
supporting negation patterns, double-star globs, and nested gitignore files.
"""

from pathlib import Path

try:
    import pathspec
except ImportError:
    pathspec = None  # type: ignore


# Default ignore patterns when no .gitignore exists
DEFAULT_IGNORE_PATTERNS: list[str] = [
    "node_modules/",
    "venv/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    ".git/",
    "dist/",
    "build/",
    "vendor/",
    "*.min.js",
    "*.min.css",
    ".idea/",
    ".vscode/",
    "*.egg-info/",
    ".tox/",
    ".pytest_cache/",
    ".mypy_cache/",
    "coverage/",
    ".nyc_output/",
    "target/",  # Rust/Java
    "bin/",
    "obj/",  # .NET
]


class PathspecFilter:
    """File filter based on pathspec library with nested gitignore support."""
    
    def __init__(self, repo_path: Path, include_nested: bool = True):
        """
        Initialize the filter.
        
        Args:
            repo_path: Repository root path
            include_nested: Whether to include nested .gitignore files
        """
        self.repo_path = repo_path
        self._root_spec: "pathspec.PathSpec | None" = None
        self._nested_specs: dict[Path, "pathspec.PathSpec"] = {}
        self._include_nested = include_nested
        self._load_gitignore()
        if include_nested:
            self._load_nested_gitignores()
    
    def _load_gitignore(self) -> None:
        """Load root .gitignore file."""
        if pathspec is None:
            return
        
        gitignore_path = self.repo_path / ".gitignore"
        
        if gitignore_path.exists():
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    lines = f.readlines()
                self._root_spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
            except Exception:
                self._root_spec = pathspec.PathSpec.from_lines(
                    "gitwildmatch", DEFAULT_IGNORE_PATTERNS
                )
        else:
            self._root_spec = pathspec.PathSpec.from_lines(
                "gitwildmatch", DEFAULT_IGNORE_PATTERNS
            )
    
    def _load_nested_gitignores(self) -> None:
        """Load nested .gitignore files from subdirectories."""
        if pathspec is None:
            return
        
        # Find all .gitignore files in subdirectories
        for gitignore_path in self.repo_path.rglob(".gitignore"):
            if gitignore_path.parent == self.repo_path:
                continue  # Skip root, already loaded
            
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    lines = f.readlines()
                spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
                self._nested_specs[gitignore_path.parent] = spec
            except Exception:
                pass  # Skip invalid gitignore files
    
    def should_ignore(self, path: Path) -> bool:
        """
        Check if a file should be ignored.
        
        Applies gitignore rules with correct precedence:
        1. Root .gitignore applies to all files
        2. Nested .gitignore files apply to files in their directory and below
        3. More specific (deeper) rules take precedence
        """
        if self._root_spec is None:
            return False
        
        try:
            # Get relative path
            if path.is_absolute():
                relative = path.relative_to(self.repo_path)
            else:
                relative = path
            
            relative_str = str(relative).replace("\\", "/")
            
            # Check root gitignore first
            if self._root_spec.match_file(relative_str):
                return True
            
            # Check nested gitignores (from most specific to least)
            if self._include_nested:
                # Sort by depth (deepest first)
                sorted_dirs = sorted(
                    self._nested_specs.keys(),
                    key=lambda p: len(p.parts),
                    reverse=True
                )
                
                for gitignore_dir in sorted_dirs:
                    try:
                        # Check if path is under this gitignore's directory
                        gitignore_relative = gitignore_dir.relative_to(self.repo_path)
                        if relative_str.startswith(str(gitignore_relative).replace("\\", "/")):
                            # Get path relative to the gitignore directory
                            path_from_gitignore = relative.relative_to(gitignore_relative)
                            if self._nested_specs[gitignore_dir].match_file(str(path_from_gitignore)):
                                return True
                    except ValueError:
                        continue
            
            return False
        except ValueError:
            return False
    
    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter paths, returning those that should NOT be ignored."""
        return [p for p in paths if not self.should_ignore(p)]
    
    def get_patterns(self) -> list[str]:
        """Get the root ignore patterns."""
        if self._root_spec is None:
            return []
        return [str(p) for p in self._root_spec.patterns]
    
    def get_all_patterns(self) -> dict[str, list[str]]:
        """Get all patterns including nested gitignores."""
        result = {"root": self.get_patterns()}
        for dir_path, spec in self._nested_specs.items():
            rel_path = str(dir_path.relative_to(self.repo_path))
            result[rel_path] = [str(p) for p in spec.patterns]
        return result
