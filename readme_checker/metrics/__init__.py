"""Smart metrics for README-Police V3.

This module provides intelligent code metrics that exclude
vendor code, generated files, and provide meaningful context.
"""

from readme_checker.metrics.loc import (
    SmartLOCCounter,
    LOCResult,
    VENDOR_PATTERNS,
    GENERATED_PATTERNS,
)
from readme_checker.metrics.todos import (
    TodoAnalyzer,
    TodoItem,
    TodoPriority,
    TodoSummary,
)
from readme_checker.metrics.scoring import (
    WeightedTrustScorer,
    TrustScore,
    SEVERITY_WEIGHTS,
)

__all__ = [
    "SmartLOCCounter",
    "LOCResult",
    "VENDOR_PATTERNS",
    "GENERATED_PATTERNS",
    "TodoAnalyzer",
    "TodoItem",
    "TodoPriority",
    "TodoSummary",
    "WeightedTrustScorer",
    "TrustScore",
    "SEVERITY_WEIGHTS",
]
