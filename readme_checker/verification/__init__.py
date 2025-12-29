"""
Verification Layer - 验证层

负责声明验证、代码分析和评分。
"""

from readme_checker.verification.verifier import (
    verify_all,
    verify_ecosystem,
    verify_paths,
    verify_modules,
    verify_build_scripts,
    verify_paths_with_artifacts,
    VerificationResult,
    Violation,
)
from readme_checker.verification.analyzer import (
    analyze_codebase,
    analyze_codebase_v3,
    analyze_todos_v3,
    verify_hype,
    verify_todos,
    CodeStats,
    TodoLocation,
)
from readme_checker.verification.scorer import (
    calculate_score,
    calculate_score_v3,
    ScoreBreakdown,
)

__all__ = [
    # verifier
    "verify_all",
    "verify_ecosystem",
    "verify_paths",
    "verify_modules",
    "verify_build_scripts",
    "verify_paths_with_artifacts",
    "VerificationResult",
    "Violation",
    # analyzer
    "analyze_codebase",
    "analyze_codebase_v3",
    "analyze_todos_v3",
    "verify_hype",
    "verify_todos",
    "CodeStats",
    "TodoLocation",
    # scorer
    "calculate_score",
    "calculate_score_v3",
    "ScoreBreakdown",
]
