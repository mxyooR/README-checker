"""
代码分析器模块 - 统计代码行数和 TODO 注释

用于检测：
1. 夸大描述（代码量少但描述夸张）
2. TODO 陷阱（声称完成但有大量 TODO）
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from readme_checker.parsing.extractor import ExtractedClaims
from readme_checker.verification.verifier import Violation
from readme_checker.repo.pathspec_filter import PathspecFilter, DEFAULT_IGNORE_PATTERNS

# V3: Import smart metrics
try:
    from readme_checker.metrics.loc import SmartLOCCounter, LOCResult
    from readme_checker.metrics.todos import TodoAnalyzer, TodoSummary
    SMART_METRICS_AVAILABLE = True
except ImportError:
    SMART_METRICS_AVAILABLE = False
    SmartLOCCounter = None  # type: ignore
    LOCResult = None  # type: ignore
    TodoAnalyzer = None  # type: ignore
    TodoSummary = None  # type: ignore

# Legacy import for backward compatibility
try:
    from readme_checker.repo.gitignore import GitignoreRules, parse_gitignore, should_ignore
except ImportError:
    GitignoreRules = None  # type: ignore
    parse_gitignore = None  # type: ignore
    should_ignore = None  # type: ignore


# ============================================================
# 配置常量
# ============================================================

SOURCE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".java", ".c", ".cpp", ".h", ".rb", ".php",
}

COMMENT_PREFIXES: list[str] = ["#", "//"]

TODO_PATTERN = re.compile(r'\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)

HYPE_LOC_THRESHOLD = 100
TODO_COUNT_THRESHOLD = 10


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TodoLocation:
    """TODO 位置记录"""
    file: str
    line: int
    content: str


@dataclass
class CodeStats:
    """代码统计结果"""
    total_loc: int = 0
    total_files: int = 0
    todo_count: int = 0
    todo_locations: list[TodoLocation] = field(default_factory=list)


# ============================================================
# 分析函数
# ============================================================

def _is_comment_line(line: str) -> bool:
    """判断是否为注释行"""
    for prefix in COMMENT_PREFIXES:
        if line.startswith(prefix):
            return True
    return False


def _is_blank_line(line: str) -> bool:
    """判断是否为空行"""
    return len(line.strip()) == 0


def _count_file_loc(file_path: Path) -> tuple[int, list[TodoLocation]]:
    """统计单个文件的代码行数和 TODO"""
    loc = 0
    todos: list[TodoLocation] = []
    
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0, []
    
    for line_num, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        
        if TODO_PATTERN.search(line):
            todos.append(TodoLocation(
                file=str(file_path),
                line=line_num,
                content=stripped[:80],
            ))
        
        if not _is_blank_line(line) and not _is_comment_line(stripped):
            loc += 1
    
    return loc, todos


def analyze_codebase(
    repo_path: Path,
    gitignore_rules: Optional["GitignoreRules"] = None,
    pathspec_filter: Optional[PathspecFilter] = None,
) -> CodeStats:
    """分析代码库，统计 LOC 和 TODO"""
    stats = CodeStats()
    
    if pathspec_filter is None:
        pathspec_filter = PathspecFilter(repo_path)
    
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        
        if pathspec_filter.should_ignore(file_path):
            continue
        
        if file_path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        
        loc, todos = _count_file_loc(file_path)
        stats.total_loc += loc
        stats.total_files += 1
        stats.todo_count += len(todos)
        
        if len(stats.todo_locations) < 5:
            stats.todo_locations.extend(todos[:5 - len(stats.todo_locations)])
    
    return stats


def verify_hype(claims: ExtractedClaims, stats: CodeStats) -> list[Violation]:
    """验证夸大声明 - 检查代码量是否匹配描述"""
    violations: list[Violation] = []
    
    if claims.hype_claims and stats.total_loc < HYPE_LOC_THRESHOLD:
        hype_words = [c.word for c in claims.hype_claims]
        violations.append(Violation(
            category="hype",
            severity="warning",
            message=f"Over-hyped! Claims '{', '.join(hype_words)}' but only {stats.total_loc} lines of code",
            details={
                "hype_words": hype_words,
                "loc": stats.total_loc,
                "threshold": HYPE_LOC_THRESHOLD,
            },
        ))
    
    return violations


def verify_todos(claims: ExtractedClaims, stats: CodeStats) -> list[Violation]:
    """验证 TODO 陷阱 - 检查是否声称完成但有大量 TODO"""
    violations: list[Violation] = []
    
    if claims.completeness_claims and stats.todo_count > TODO_COUNT_THRESHOLD:
        completeness_words = [c.claim for c in claims.completeness_claims]
        todo_examples = [f"{t.file}:{t.line}" for t in stats.todo_locations[:3]]
        
        violations.append(Violation(
            category="todo",
            severity="warning",
            message=f"Half-baked! Claims '{', '.join(completeness_words)}' but has {stats.todo_count} TODOs",
            details={
                "completeness_claims": completeness_words,
                "todo_count": stats.todo_count,
                "threshold": TODO_COUNT_THRESHOLD,
                "examples": todo_examples,
            },
        ))
    
    return violations


# ============================================================
# V3: Smart Metrics Functions
# ============================================================

def analyze_codebase_v3(repo_path: Path) -> "LOCResult":
    """V3: 使用智能 LOC 计数器分析代码库"""
    if not SMART_METRICS_AVAILABLE:
        stats = analyze_codebase(repo_path)
        return type('LOCResult', (), {
            'total_loc': stats.total_loc,
            'source_loc': stats.total_loc,
            'test_loc': 0,
            'file_count': stats.total_files,
            'source_file_count': stats.total_files,
            'language_breakdown': {},
            'excluded_vendor_loc': 0,
            'excluded_generated_loc': 0,
        })()
    
    counter = SmartLOCCounter(repo_path)
    return counter.count()


def analyze_todos_v3(repo_path: Path) -> "TodoSummary":
    """V3: 使用 TODO 分析器分析代码库"""
    if not SMART_METRICS_AVAILABLE:
        stats = analyze_codebase(repo_path)
        return type('TodoSummary', (), {
            'total_count': stats.todo_count,
            'by_priority': {'TODO': stats.todo_count},
            'items': [],
            'weighted_score': 0.5,
        })()
    
    analyzer = TodoAnalyzer(repo_path)
    return analyzer.analyze()
