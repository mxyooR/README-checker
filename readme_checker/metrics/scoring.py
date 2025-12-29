"""Weighted trust scoring.

Calculates trust scores with severity weighting.
"""

from dataclasses import dataclass, field
from typing import Literal


# Severity weights for scoring
SEVERITY_WEIGHTS: dict[str, float] = {
    "error": 1.0,      # Critical issues
    "warning": 0.5,    # Important but not critical
    "info": 0.1,       # Informational
}

# Category weights (some issues are more important than others)
CATEGORY_WEIGHTS: dict[str, float] = {
    "ecosystem": 1.0,       # Missing config files
    "command": 0.9,         # Missing scripts
    "module": 0.8,          # Missing modules
    "path": 0.7,            # Missing files
    "build_script": 0.6,    # Missing build scripts
    "build_artifact": 0.2,  # Build artifacts (expected to be missing)
    "hype": 0.4,            # Over-hyped claims
    "todo": 0.3,            # TODO issues
}


@dataclass
class TrustScore:
    """Trust score result."""
    score: float  # 0.0 - 100.0
    grade: str    # A, B, C, D, F
    total_issues: int
    critical_issues: int
    warning_issues: int
    info_issues: int
    breakdown: dict[str, float] = field(default_factory=dict)
    comparative_context: str = ""


class WeightedTrustScorer:
    """Calculate weighted trust scores."""
    
    def __init__(self, base_score: float = 100.0):
        """
        Initialize scorer.
        
        Args:
            base_score: Starting score (default 100)
        """
        self.base_score = base_score
    
    def calculate(
        self,
        violations: list[dict],
        total_claims: int = 0,
    ) -> TrustScore:
        """
        Calculate trust score from violations.
        
        Args:
            violations: List of violation dicts with 'category' and 'severity'
            total_claims: Total number of claims checked (for context)
        
        Returns:
            TrustScore with weighted calculation
        """
        result = TrustScore(
            score=self.base_score,
            grade="A",
            total_issues=len(violations),
            critical_issues=0,
            warning_issues=0,
            info_issues=0,
        )
        
        if not violations:
            result.comparative_context = "Perfect score! All claims verified."
            return result
        
        # Count by severity
        deductions: dict[str, float] = {}
        
        for violation in violations:
            category = violation.get("category", "unknown")
            severity = violation.get("severity", "warning")
            
            # Count by severity
            if severity == "error":
                result.critical_issues += 1
            elif severity == "warning":
                result.warning_issues += 1
            else:
                result.info_issues += 1
            
            # Calculate deduction
            severity_weight = SEVERITY_WEIGHTS.get(severity, 0.5)
            category_weight = CATEGORY_WEIGHTS.get(category, 0.5)
            deduction = severity_weight * category_weight * 10  # Base deduction of 10 points
            
            # Track by category
            deductions[category] = deductions.get(category, 0) + deduction
        
        # Apply deductions
        total_deduction = sum(deductions.values())
        result.score = max(0, self.base_score - total_deduction)
        result.breakdown = deductions
        
        # Assign grade
        result.grade = self._score_to_grade(result.score)
        
        # Generate context
        result.comparative_context = self._generate_context(result, total_claims)
        
        return result
    
    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_context(self, result: TrustScore, total_claims: int) -> str:
        """Generate comparative context message."""
        if result.score >= 90:
            return "Excellent! README is highly accurate."
        elif result.score >= 80:
            return "Good. Minor issues found, but overall reliable."
        elif result.score >= 70:
            return "Fair. Some claims need attention."
        elif result.score >= 60:
            return "Below average. Several issues need fixing."
        else:
            return "Poor. README has significant accuracy issues."
