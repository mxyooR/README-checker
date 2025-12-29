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

from readme_checker.extractor import ExtractedClaims
from readme_checker.verifier import Violation
from readme_checker.gitignore import (
    GitignoreRules,
    parse_gitignore,
    should_ignore,
)


# ============================================================
# 配置常量
# ============================================================

# 支持的源代码文件扩展名
SOURCE_EXTENSIONS: set[str] = {
    ".py",      # Python
    ".js",      # JavaScript
    ".ts",      # TypeScript
    ".jsx",     # React JSX
    ".tsx",     # React TSX
    ".go",      # Go
    ".rs",      # Rust
    ".java",    # Java
    ".c",       # C
    ".cpp",     # C++
    ".h",       # C/C++ Header
    ".rb",      # Ruby
    ".php",     # PHP
}

# 单行注释前缀（按语言）
COMMENT_PREFIXES: list[str] = [
    "#",    # Python, Ruby, Shell
    "//",   # JavaScript, TypeScript, Go, Rust, Java, C/C++
]

# TODO 关键词模式
TODO_PATTERN = re.compile(
    r'\b(TODO|FIXME|HACK|XXX)\b',
    re.IGNORECASE
)

# 夸大检测阈值
HYPE_LOC_THRESHOLD = 100  # 少于 100 行代码视为"小项目"

# TODO 陷阱阈值
TODO_COUNT_THRESHOLD = 10  # 超过 10 个 TODO 视为"未完成"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TodoLocation:
    """
    TODO 位置记录
    
    Attributes:
        file: 文件路径
        line: 行号
        content: TODO 内容
    """
    file: str
    line: int
    content: str


@dataclass
class CodeStats:
    """
    代码统计结果
    
    Attributes:
        total_loc: 总代码行数（不含空行和注释）
        total_files: 源文件数量
        todo_count: TODO/FIXME/HACK 注释数量
        todo_locations: TODO 位置列表（最多保留 5 个示例）
    """
    total_loc: int = 0
    total_files: int = 0
    todo_count: int = 0
    todo_locations: list[TodoLocation] = field(default_factory=list)


# ============================================================
# 分析函数
# ============================================================

def _is_comment_line(line: str) -> bool:
    """
    判断是否为注释行
    
    Args:
        line: 代码行（已去除首尾空白）
    
    Returns:
        是否为注释行
    """
    for prefix in COMMENT_PREFIXES:
        if line.startswith(prefix):
            return True
    return False


def _is_blank_line(line: str) -> bool:
    """
    判断是否为空行
    
    Args:
        line: 代码行
    
    Returns:
        是否为空行
    """
    return len(line.strip()) == 0


def _count_file_loc(file_path: Path) -> tuple[int, list[TodoLocation]]:
    """
    统计单个文件的代码行数和 TODO
    
    Args:
        file_path: 文件路径
    
    Returns:
        (代码行数, TODO 位置列表)
    """
    loc = 0
    todos: list[TodoLocation] = []
    
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0, []
    
    for line_num, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        
        # 检查 TODO
        if TODO_PATTERN.search(line):
            todos.append(TodoLocation(
                file=str(file_path),
                line=line_num,
                content=stripped[:80],  # 截断过长的内容
            ))
        
        # 统计有效代码行
        if not _is_blank_line(line) and not _is_comment_line(stripped):
            loc += 1
    
    return loc, todos


def analyze_codebase(repo_path: Path, gitignore_rules: Optional[GitignoreRules] = None) -> CodeStats:
    """
    分析代码库，统计 LOC 和 TODO
    
    Args:
        repo_path: 仓库根目录路径
        gitignore_rules: Gitignore 规则集（可选，如果为 None 则自动解析）
    
    Returns:
        CodeStats 对象，包含统计结果
    """
    stats = CodeStats()
    
    # 如果没有提供规则，自动解析 .gitignore
    if gitignore_rules is None:
        gitignore_rules = parse_gitignore(repo_path)
    
    # 遍历所有源文件
    for file_path in repo_path.rglob("*"):
        # 跳过目录
        if not file_path.is_file():
            continue
        
        # 使用 gitignore 规则过滤文件
        if should_ignore(file_path, gitignore_rules, repo_path):
            continue
        
        # 检查文件扩展名
        if file_path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        
        # 统计文件
        loc, todos = _count_file_loc(file_path)
        stats.total_loc += loc
        stats.total_files += 1
        stats.todo_count += len(todos)
        
        # 保留最多 5 个 TODO 示例
        if len(stats.todo_locations) < 5:
            stats.todo_locations.extend(todos[:5 - len(stats.todo_locations)])
    
    return stats


def verify_hype(
    claims: ExtractedClaims,
    stats: CodeStats,
) -> list[Violation]:
    """
    验证夸大声明 - 检查代码量是否匹配描述
    
    Args:
        claims: 提取的声明
        stats: 代码统计结果
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    # 如果有夸大词汇且代码量少
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


def verify_todos(
    claims: ExtractedClaims,
    stats: CodeStats,
) -> list[Violation]:
    """
    验证 TODO 陷阱 - 检查是否声称完成但有大量 TODO
    
    Args:
        claims: 提取的声明
        stats: 代码统计结果
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    # 如果声称完成但有大量 TODO
    if claims.completeness_claims and stats.todo_count > TODO_COUNT_THRESHOLD:
        completeness_words = [c.claim for c in claims.completeness_claims]
        
        # 格式化 TODO 位置示例
        todo_examples = [
            f"{t.file}:{t.line}" for t in stats.todo_locations[:3]
        ]
        
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
