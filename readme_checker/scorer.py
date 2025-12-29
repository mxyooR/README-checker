"""
信任评分器模块 - 根据违规情况计算信任分数

评分规则：
- 基础分 100 分
- 每个违规扣除相应分数
- 最终分数限制在 0-100 范围内

V3 增强：
- 加权评分：根据严重程度和类别加权
- 比较上下文：提供有意义的评分解释
"""

from dataclasses import dataclass
from typing import Optional

from readme_checker.verifier import VerificationResult, Violation

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

# 违规扣分权重
SCORING_WEIGHTS: dict[str, int] = {
    "ecosystem": -15,   # 缺少配置文件
    "path": -10,        # 断开的链接/图片
    "command": -10,     # 不存在的脚本
    "hype": -5,         # 夸大描述
    "todo": -5,         # TODO 陷阱
}

# 评级阈值
SCORE_THRESHOLDS: dict[str, int] = {
    "trustworthy": 80,  # >= 80 分：可信赖
    "suspicious": 50,   # 50-79 分：可疑
    "liar": 0,          # < 50 分：骗子
}

# 评级描述
RATING_DESCRIPTIONS: dict[str, str] = {
    "trustworthy": "Trustworthy ✅",
    "suspicious": "Suspicious 🤨",
    "liar": "Liar Detected 🚨",
}

# 评级 emoji
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
    """
    评分明细
    
    Attributes:
        base_score: 基础分（100）
        ecosystem_penalty: 生态系统违规扣分
        path_penalty: 路径违规扣分
        command_penalty: 命令违规扣分
        hype_penalty: 夸大描述扣分
        todo_penalty: TODO 陷阱扣分
        total_score: 最终得分（0-100）
        rating: 评级（trustworthy, suspicious, liar）
        rating_description: 评级描述
    """
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

def _count_violations_by_category(
    violations: list[Violation],
) -> dict[str, int]:
    """
    按类别统计违规数量
    
    Args:
        violations: 违规列表
    
    Returns:
        类别 -> 数量的映射
    """
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.category] = counts.get(v.category, 0) + 1
    return counts


def _get_rating(score: int) -> str:
    """
    根据分数获取评级
    
    Args:
        score: 信任分数
    
    Returns:
        评级字符串
    """
    if score >= SCORE_THRESHOLDS["trustworthy"]:
        return "trustworthy"
    elif score >= SCORE_THRESHOLDS["suspicious"]:
        return "suspicious"
    else:
        return "liar"


def calculate_score(result: VerificationResult) -> ScoreBreakdown:
    """
    计算信任分数
    
    Args:
        result: 验证结果
    
    Returns:
        ScoreBreakdown 对象，包含评分明细
    """
    breakdown = ScoreBreakdown()
    
    # 统计各类违规
    counts = _count_violations_by_category(result.violations)
    
    # 计算各类扣分
    breakdown.ecosystem_penalty = counts.get("ecosystem", 0) * SCORING_WEIGHTS["ecosystem"]
    breakdown.path_penalty = counts.get("path", 0) * SCORING_WEIGHTS["path"]
    breakdown.command_penalty = counts.get("command", 0) * SCORING_WEIGHTS["command"]
    breakdown.hype_penalty = counts.get("hype", 0) * SCORING_WEIGHTS["hype"]
    breakdown.todo_penalty = counts.get("todo", 0) * SCORING_WEIGHTS["todo"]
    
    # 计算总分
    total_penalty = (
        breakdown.ecosystem_penalty +
        breakdown.path_penalty +
        breakdown.command_penalty +
        breakdown.hype_penalty +
        breakdown.todo_penalty
    )
    
    # 限制在 0-100 范围内
    breakdown.total_score = max(0, min(100, breakdown.base_score + total_penalty))
    
    # 确定评级
    breakdown.rating = _get_rating(breakdown.total_score)
    breakdown.rating_description = RATING_DESCRIPTIONS[breakdown.rating]
    
    return breakdown


# ============================================================
# V3: Weighted Scoring Functions
# ============================================================

def calculate_score_v3(result: VerificationResult) -> "TrustScore":
    """
    V3: 使用加权评分器计算信任分数
    
    根据违规的严重程度和类别进行加权计算。
    
    Args:
        result: 验证结果
    
    Returns:
        TrustScore 对象
    """
    if not WEIGHTED_SCORER_AVAILABLE:
        # Fallback to legacy
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
    
    # Convert violations to dict format
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
