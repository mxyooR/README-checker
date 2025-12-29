"""File filtering for README-Police V3.

This module provides pathspec-based gitignore filtering using
the mature pathspec library.
"""

from readme_checker.filters.pathspec_filter import (
    PathspecFilter,
    DEFAULT_IGNORE_PATTERNS,
)

__all__ = [
    "PathspecFilter",
    "DEFAULT_IGNORE_PATTERNS",
]
