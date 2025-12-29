"""
Gitignore 解析器模块 - 解析 .gitignore 文件并提供文件过滤功能

用于在统计 LOC 和 TODO 时排除被忽略的文件
"""

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# 配置常量
# ============================================================

# 默认忽略模式（当无 .gitignore 时使用）
DEFAULT_IGNORE_PATTERNS: list[str] = [
    "node_modules/",
    "venv/",
    ".venv/",
    "env/",
    "__pycache__/",
    "dist/",
    "build/",
    ".git/",
    "*.pyc",
    "*.pyo",
    "*.egg-info/",
    ".eggs/",
    ".tox/",
    ".pytest_cache/",
    ".mypy_cache/",
    "*.so",
    "*.dylib",
    "*.dll",
    "coverage/",
    ".coverage",
    "htmlcov/",
    ".idea/",
    ".vscode/",
    "*.log",
    "*.tmp",
    "*.temp",
]


# ============================================================
# 数据模型
# ============================================================

@dataclass
class GitignoreRules:
    """
    Gitignore 规则集
    
    Attributes:
        patterns: 忽略模式列表
        negations: 否定模式列表（以 ! 开头的模式）
        source_file: 规则来源文件路径（如果有）
    """
    patterns: list[str] = field(default_factory=list)
    negations: list[str] = field(default_factory=list)
    source_file: Optional[Path] = None


# ============================================================
# 解析函数
# ============================================================

def parse_gitignore(repo_path: Path) -> GitignoreRules:
    """
    解析仓库中的 .gitignore 文件
    
    如果文件不存在，返回空规则集（调用方应使用默认模式）
    
    Args:
        repo_path: 仓库根目录路径
    
    Returns:
        GitignoreRules 对象
    """
    gitignore_path = repo_path / ".gitignore"
    
    if not gitignore_path.exists():
        return GitignoreRules()
    
    patterns: list[str] = []
    negations: list[str] = []
    
    try:
        content = gitignore_path.read_text(encoding="utf-8")
    except Exception:
        try:
            content = gitignore_path.read_text(encoding="latin-1")
        except Exception:
            return GitignoreRules()
    
    for line in content.split("\n"):
        line = line.strip()
        
        # 跳过空行和注释
        if not line or line.startswith("#"):
            continue
        
        # 处理否定模式
        if line.startswith("!"):
            negation = line[1:].strip()
            if negation:
                negations.append(negation)
        else:
            patterns.append(line)
    
    return GitignoreRules(
        patterns=patterns,
        negations=negations,
        source_file=gitignore_path,
    )


def _match_pattern(path_str: str, pattern: str) -> bool:
    """
    检查路径是否匹配单个 gitignore 模式
    
    Args:
        path_str: 相对路径字符串
        pattern: gitignore 模式
    
    Returns:
        是否匹配
    """
    # 处理目录模式（以 / 结尾）
    is_dir_pattern = pattern.endswith("/")
    if is_dir_pattern:
        pattern = pattern[:-1]
    
    # 处理根目录模式（以 / 开头）
    is_root_pattern = pattern.startswith("/")
    if is_root_pattern:
        pattern = pattern[1:]
    
    # 标准化路径分隔符
    path_str = path_str.replace("\\", "/")
    
    # 如果模式包含 /，则需要匹配完整路径
    if "/" in pattern:
        # 完整路径匹配
        if fnmatch.fnmatch(path_str, pattern):
            return True
        # 也尝试匹配路径的任意部分
        if fnmatch.fnmatch(path_str, f"*/{pattern}"):
            return True
    else:
        # 简单模式：匹配文件名或目录名
        parts = path_str.split("/")
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # 也尝试完整路径匹配
        if fnmatch.fnmatch(path_str, pattern):
            return True
        if fnmatch.fnmatch(path_str, f"**/{pattern}"):
            return True
    
    return False


def should_ignore(
    file_path: Path,
    rules: GitignoreRules,
    repo_root: Path,
) -> bool:
    """
    判断文件是否应被忽略
    
    Args:
        file_path: 文件的绝对路径
        rules: Gitignore 规则集
        repo_root: 仓库根目录路径
    
    Returns:
        是否应被忽略
    """
    # 计算相对路径
    try:
        rel_path = file_path.relative_to(repo_root)
        path_str = str(rel_path).replace("\\", "/")
    except ValueError:
        # 文件不在仓库内
        return False
    
    # 如果没有规则，使用默认模式
    patterns = rules.patterns if rules.patterns else DEFAULT_IGNORE_PATTERNS
    negations = rules.negations
    
    # 检查是否匹配忽略模式
    is_ignored = False
    for pattern in patterns:
        if _match_pattern(path_str, pattern):
            is_ignored = True
            break
    
    # 检查是否匹配否定模式（否定模式优先级更高）
    if is_ignored and negations:
        for negation in negations:
            if _match_pattern(path_str, negation):
                is_ignored = False
                break
    
    return is_ignored
