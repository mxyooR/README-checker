"""
Repository Layer - 仓库层

负责仓库加载、上下文解析和文件过滤。
"""

from readme_checker.repo.loader import (
    load_repository,
    cleanup_repository,
    CloneConfig,
    RepositoryContext,
)
from readme_checker.repo.resolver import resolve_analysis_context, AnalysisContext
from readme_checker.repo.gitignore import parse_gitignore, GitignoreRules, should_ignore
from readme_checker.repo.pathspec_filter import PathspecFilter, DEFAULT_IGNORE_PATTERNS

__all__ = [
    # loader
    "load_repository",
    "cleanup_repository", 
    "CloneConfig",
    "RepositoryContext",
    # resolver
    "resolve_analysis_context",
    "AnalysisContext",
    # gitignore
    "parse_gitignore",
    "GitignoreRules",
    "should_ignore",
    # pathspec_filter
    "PathspecFilter",
    "DEFAULT_IGNORE_PATTERNS",
]
