"""
路径解析器模块 - 处理 Monorepo 场景下的路径解析

支持通过 --root 选项指定分析的子目录
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ============================================================
# 配置常量
# ============================================================

# README 文件名候选（按优先级）
README_CANDIDATES = [
    "README.md",
    "readme.md",
    "README.MD",
    "Readme.md",
    "README",
    "readme",
]


# ============================================================
# 数据模型
# ============================================================

@dataclass
class AnalysisContext:
    """
    分析上下文 - 包含根路径和分析根路径
    
    Attributes:
        repo_root: 仓库根目录路径
        analysis_root: 分析根目录路径（可能是子目录）
        readme_path: README 文件路径（如果存在）
        readme_content: README 文件内容
    """
    repo_root: Path
    analysis_root: Path
    readme_path: Optional[Path] = None
    readme_content: str = ""


# ============================================================
# 解析函数
# ============================================================

def _find_readme(directory: Path) -> Optional[Path]:
    """
    在目录中查找 README 文件
    
    Args:
        directory: 目录路径
    
    Returns:
        README 文件路径，如果未找到则返回 None
    """
    for candidate in README_CANDIDATES:
        readme_path = directory / candidate
        if readme_path.exists() and readme_path.is_file():
            return readme_path
    return None


def resolve_analysis_context(
    repo_path: Path,
    root_option: Optional[str] = None,
) -> AnalysisContext:
    """
    解析分析上下文
    
    Args:
        repo_path: 仓库路径（绝对路径）
        root_option: --root 选项值（可选，相对于 repo_path 的路径）
    
    Returns:
        AnalysisContext 对象
    
    Raises:
        ValueError: 如果 root_option 指定的路径不存在或无效
    """
    repo_root = repo_path.resolve()
    
    if root_option:
        # 解析 --root 选项
        analysis_root = (repo_root / root_option).resolve()
        
        # 验证路径存在
        if not analysis_root.exists():
            raise ValueError(f"Root path does not exist: {root_option}")
        
        # 验证是目录
        if not analysis_root.is_dir():
            raise ValueError(f"Root path is not a directory: {root_option}")
        
        # 验证在仓库内
        try:
            analysis_root.relative_to(repo_root)
        except ValueError:
            raise ValueError(f"Root path is outside repository: {root_option}")
    else:
        # 默认使用仓库根目录
        analysis_root = repo_root
    
    # 查找 README
    readme_path = _find_readme(analysis_root)
    readme_content = ""
    
    if readme_path:
        try:
            readme_content = readme_path.read_text(encoding="utf-8")
        except Exception:
            try:
                readme_content = readme_path.read_text(encoding="latin-1")
            except Exception:
                readme_content = ""
    
    return AnalysisContext(
        repo_root=repo_root,
        analysis_root=analysis_root,
        readme_path=readme_path,
        readme_content=readme_content,
    )


def resolve_relative_path(
    relative_path: str,
    context: AnalysisContext,
) -> Path:
    """
    解析 README 中的相对路径
    
    相对路径基于 analysis_root 解析
    
    Args:
        relative_path: 相对路径字符串
        context: 分析上下文
    
    Returns:
        解析后的绝对路径
    """
    # 移除开头的 ./
    if relative_path.startswith("./"):
        relative_path = relative_path[2:]
    
    return context.analysis_root / relative_path
