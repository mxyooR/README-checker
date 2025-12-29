"""Smart LOC counter.

Excludes vendor code, generated files, and minified code.
Provides language breakdown and meaningful metrics.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

from readme_checker.filters.pathspec_filter import PathspecFilter


# Patterns for vendor/third-party code
VENDOR_PATTERNS: list[str] = [
    "vendor/",
    "node_modules/",
    "third_party/",
    "third-party/",
    "external/",
    "deps/",
    "lib/",  # Often contains vendored code
    "packages/",  # Monorepo packages (analyze separately)
]

# Patterns for generated code
GENERATED_PATTERNS: list[str] = [
    "*.min.js",
    "*.min.css",
    "*.bundle.js",
    "*.generated.*",
    "*_generated.*",
    "*.pb.go",  # Protocol buffer generated
    "*.pb.py",
    "*_pb2.py",
    "*.g.dart",  # Flutter generated
    "*.freezed.dart",
    "swagger_client/",
    "openapi_client/",
]

# File extension to language mapping
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript (JSX)",
    ".tsx": "TypeScript (TSX)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Bash",
    ".zsh": "Zsh",
    ".ps1": "PowerShell",
}


@dataclass
class LOCResult:
    """LOC counting result."""
    total_loc: int = 0
    source_loc: int = 0  # Excluding vendor/generated
    test_loc: int = 0
    file_count: int = 0
    source_file_count: int = 0
    language_breakdown: dict[str, int] = field(default_factory=dict)
    excluded_vendor_loc: int = 0
    excluded_generated_loc: int = 0


class SmartLOCCounter:
    """Smart LOC counter that excludes vendor and generated code."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._pathspec_filter = PathspecFilter(repo_path)
    
    def count(self) -> LOCResult:
        """Count lines of code with smart filtering."""
        result = LOCResult()
        
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip gitignored files
            if self._pathspec_filter.should_ignore(file_path):
                continue
            
            # Check file extension
            ext = file_path.suffix.lower()
            if ext not in EXTENSION_TO_LANGUAGE:
                continue
            
            language = EXTENSION_TO_LANGUAGE[ext]
            relative_path = str(file_path.relative_to(self.repo_path))
            
            # Count lines
            loc = self._count_file_loc(file_path)
            if loc == 0:
                continue
            
            result.total_loc += loc
            result.file_count += 1
            
            # Check if vendor code
            if self._is_vendor(relative_path):
                result.excluded_vendor_loc += loc
                continue
            
            # Check if generated code
            if self._is_generated(relative_path, file_path):
                result.excluded_generated_loc += loc
                continue
            
            # Check if test file
            if self._is_test_file(relative_path):
                result.test_loc += loc
            else:
                result.source_loc += loc
                result.source_file_count += 1
            
            # Update language breakdown
            result.language_breakdown[language] = (
                result.language_breakdown.get(language, 0) + loc
            )
        
        return result
    
    def _count_file_loc(self, file_path: Path) -> int:
        """Count non-blank, non-comment lines in a file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return 0
        
        loc = 0
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not self._is_comment(stripped):
                loc += 1
        
        return loc
    
    def _is_comment(self, line: str) -> bool:
        """Check if line is a comment."""
        comment_prefixes = ["#", "//", "/*", "*", "'''", '"""', "--", ";"]
        return any(line.startswith(prefix) for prefix in comment_prefixes)
    
    def _is_vendor(self, relative_path: str) -> bool:
        """Check if file is vendor/third-party code."""
        path_lower = relative_path.lower().replace("\\", "/")
        
        for pattern in VENDOR_PATTERNS:
            if pattern.endswith("/"):
                if path_lower.startswith(pattern) or f"/{pattern}" in path_lower:
                    return True
            else:
                if pattern in path_lower:
                    return True
        
        return False
    
    def _is_generated(self, relative_path: str, file_path: Path) -> bool:
        """Check if file is generated code."""
        path_lower = relative_path.lower()
        
        # Check patterns
        for pattern in GENERATED_PATTERNS:
            if pattern.startswith("*"):
                suffix = pattern[1:]
                if path_lower.endswith(suffix):
                    return True
            elif pattern.endswith("/"):
                if path_lower.startswith(pattern) or f"/{pattern}" in path_lower:
                    return True
        
        # Check for generated file markers in content
        try:
            first_lines = file_path.read_text(encoding="utf-8", errors="ignore")[:500]
            generated_markers = [
                "generated",
                "auto-generated",
                "do not edit",
                "do not modify",
                "@generated",
                "// Code generated",
            ]
            first_lines_lower = first_lines.lower()
            if any(marker in first_lines_lower for marker in generated_markers):
                return True
        except Exception:
            pass
        
        return False
    
    def _is_test_file(self, relative_path: str) -> bool:
        """Check if file is a test file."""
        path_lower = relative_path.lower()
        
        test_indicators = [
            "test_",
            "_test.",
            ".test.",
            ".spec.",
            "_spec.",
            "/tests/",
            "/test/",
            "/__tests__/",
        ]
        
        return any(indicator in path_lower for indicator in test_indicators)
