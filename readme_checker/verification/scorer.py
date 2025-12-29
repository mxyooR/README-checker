"""
信任评分器模块 - 根据违规情况计算信任分数

评分规则：
- 基础分 100 分
- 每个违规扣除相应分数
- 最终分数限制在 0-100 范围内
"""

from dataclasses import dataclass
from typing import Optional

from readme_checker.verification.verifier import VerificationResult, Violation

# V3: Import weighted scorer
try:
    from readme_checker.metrics.scoring import WeightedTrustScorer, TrustScore
    WEIGHTED_SCORER_AVAILABLE = True
except ImportError:
    WEIGHTED_SCORER_AVAILABLE = False
    WeightedTrustScorer = None  # type: ignore
    TrustScore = None  # type: ignore


# ============================================================
# 配置常量
# ============================================================

SCORING_WEIGHTS: dict[str, int] = {
    "ecosystem": -15,
    "path": -10,
    "command": -10,
    "hype": -5,
    "todo": -5,
}

SCORE_THRESHOLDS: dict[str, int] = {
    "trustworthy": 80,
    "suspicious": 50,
    "liar": 0,
}

RATING_DESCRIPTIONS: dict[str, str] = {
    "trustworthy": "Trustworthy ✅",
    "suspicious": "Suspicious 🤨",
    "liar": "Liar Detected 🚨",
}

RATING_EMOJIS: dict[str, str] = {
    "trustworthy": "✅",
    "suspicious": "🤨",
    "liar": "💩",
}


# ============================================================
# 数据模型
# ============================================================

@dataclass
class ScoreBreakdown:
    """评分明细"""
    base_score: int = 100
    ecosystem_penalty: int = 0
    path_penalty: int = 0
    command_penalty: int = 0
    hype_penalty: int = 0
    todo_penalty: int = 0
    total_score: int = 100
    rating: str = "trustworthy"
    rating_description: str = "Trustworthy ✅"


# ============================================================
# 评分函数
# ============================================================

def _count_violations_by_category(violations: list[Violation]) -> dict[str, int]:
    """按类别统计违规数量"""
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.category] = counts.get(v.category, 0) + 1
    return counts


def _get_rating(score: int) -> str:
    """根据分数获取评级"""
    if score >= SCORE_THRESHOLDS["trustworthy"]:
        return "trustworthy"
    elif score >= SCORE_THRESHOLDS["suspicious"]:
        return "suspicious"
    else:
        return "liar"


def calculate_score(result: VerificationResult) -> ScoreBreakdown:
    """计算信任分数"""
    breakdown = ScoreBreakdown()
    
    counts = _count_violations_by_category(result.violations)
    
    breakdown.ecosystem_penalty = counts.get("ecosystem", 0) * SCORING_WEIGHTS["ecosystem"]
    breakdown.path_penalty = counts.get("path", 0) * SCORING_WEIGHTS["path"]
    breakdown.command_penalty = counts.get("command", 0) * SCORING_WEIGHTS["command"]
    breakdown.hype_penalty = counts.get("hype", 0) * SCORING_WEIGHTS["hype"]
    breakdown.todo_penalty = counts.get("todo", 0) * SCORING_WEIGHTS["todo"]
    
    total_penalty = (
        breakdown.ecosystem_penalty +
        breakdown.path_penalty +
        breakdown.command_penalty +
        breakdown.hype_penalty +
        breakdown.todo_penalty
    )
    
    breakdown.total_score = max(0, min(100, breakdown.base_score + total_penalty))
    breakdown.rating = _get_rating(breakdown.total_score)
    breakdown.rating_description = RATING_DESCRIPTIONS[breakdown.rating]
    
    return breakdown


# ============================================================
# V3: Weighted Scoring Functions
# ============================================================

def calculate_score_v3(result: VerificationResult) -> "TrustScore":
    """V3: 使用加权评分器计算信任分数"""
    if not WEIGHTED_SCORER_AVAILABLE:
        breakdown = calculate_score(result)
        return type('TrustScore', (), {
            'score': float(breakdown.total_score),
            'grade': 'A' if breakdown.total_score >= 90 else 'B' if breakdown.total_score >= 80 else 'C' if breakdown.total_score >= 70 else 'D' if breakdown.total_score >= 60 else 'F',
            'total_issues': len(result.violations),
            'critical_issues': sum(1 for v in result.violations if v.severity == 'error'),
            'warning_issues': sum(1 for v in result.violations if v.severity == 'warning'),
            'info_issues': sum(1 for v in result.violations if v.severity == 'info'),
            'breakdown': {},
            'comparative_context': breakdown.rating_description,
        })()
    
    scorer = WeightedTrustScorer()
    
    violations_dicts = [
        {
            'category': v.category,
            'severity': v.severity,
            'message': v.message,
        }
        for v in result.violations
    ]
    
    total_claims = (
        result.stats.get('ecosystem_claims', 0) +
        result.stats.get('path_claims', 0) +
        result.stats.get('module_claims', 0)
    )
    
    return scorer.calculate(violations_dicts, total_claims)
