"""
仓库处理器模块 - 处理本地路径和 GitHub URL

支持：
1. 本地目录路径
2. GitHub 仓库 URL（自动克隆到临时目录）
3. 超时和重试机制
"""

import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError


# ============================================================
# 配置常量
# ============================================================

# GitHub URL 正则匹配
GITHUB_URL_PATTERN = re.compile(
    r'^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$'
)

# README 文件名候选（按优先级）
README_CANDIDATES = [
    "README.md",
    "readme.md",
    "README.MD",
    "Readme.md",
    "README",
    "readme",
]

# 克隆错误消息模板
CLONE_ERROR_MESSAGES: dict[str, str] = {
    "timeout": """
⏱️ Clone operation timed out after {timeout} seconds.

Possible causes:
- Slow network connection
- Large repository
- GitHub rate limiting

Suggestions:
- Try again with a longer timeout: --timeout 120
- Check your network connection
- Try cloning manually: git clone {url}
""",
    "network": """
🌐 Network error while cloning repository.

Possible causes:
- No internet connection
- GitHub is unreachable
- Repository doesn't exist or is private

Suggestions:
- Check your internet connection
- Verify the repository URL is correct
- If private, ensure you have access
""",
    "auth": """
🔐 Authentication required for this repository.

Possible causes:
- Repository is private
- Invalid credentials

Suggestions:
- Ensure you have access to the repository
- Check your Git credentials
""",
}


# ============================================================
# 数据模型
# ============================================================

@dataclass
class CloneConfig:
    """
    克隆配置
    
    Attributes:
        timeout: 超时时间（秒）
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        backoff_factor: 指数退避因子
    """
    timeout: int = 60
    max_retries: int = 2
    retry_delay: float = 2.0
    backoff_factor: float = 2.0


class CloneError(Exception):
    """克隆错误基类"""
    pass


class CloneTimeoutError(CloneError):
    """克隆超时错误"""
    pass


class CloneNetworkError(CloneError):
    """网络错误"""
    pass


class CloneAuthError(CloneError):
    """认证错误"""
    pass


@dataclass
class RepoContext:
    """
    仓库上下文 - 包含仓库路径和元信息
    
    Attributes:
        path: 仓库根目录路径
        readme_path: README 文件路径
        readme_content: README 文件内容
        is_temporary: 是否为临时克隆的仓库
        source_url: 原始 URL（如果是远程仓库）
    """
    path: Path
    readme_path: Optional[Path] = None
    readme_content: str = ""
    is_temporary: bool = False
    source_url: Optional[str] = None


# ============================================================
# 仓库加载函数
# ============================================================

def _find_readme(repo_path: Path) -> Optional[Path]:
    """
    在仓库中查找 README 文件
    
    Args:
        repo_path: 仓库根目录
    
    Returns:
        README 文件路径，如果未找到则返回 None
    """
    for candidate in README_CANDIDATES:
        readme_path = repo_path / candidate
        if readme_path.exists() and readme_path.is_file():
            return readme_path
    return None


def _is_github_url(target: str) -> bool:
    """
    判断是否为 GitHub URL
    
    Args:
        target: 目标字符串
    
    Returns:
        是否为 GitHub URL
    """
    return bool(GITHUB_URL_PATTERN.match(target))


def _format_clone_error_message(error: CloneError, url: str, timeout: int = 60) -> str:
    """
    格式化克隆错误消息
    
    Args:
        error: 克隆错误
        url: 仓库 URL
        timeout: 超时时间
    
    Returns:
        格式化的错误消息
    """
    if isinstance(error, CloneTimeoutError):
        return CLONE_ERROR_MESSAGES["timeout"].format(timeout=timeout, url=url)
    elif isinstance(error, CloneAuthError):
        return CLONE_ERROR_MESSAGES["auth"]
    else:
        return CLONE_ERROR_MESSAGES["network"]


def clone_with_retry(url: str, config: Optional[CloneConfig] = None) -> Path:
    """
    带重试机制的仓库克隆
    
    Args:
        url: GitHub 仓库 URL
        config: 克隆配置（可选）
    
    Returns:
        克隆后的本地路径
    
    Raises:
        CloneError: 克隆失败
    """
    if config is None:
        config = CloneConfig()
    
    last_error: Optional[Exception] = None
    delay = config.retry_delay
    
    for attempt in range(config.max_retries + 1):
        temp_dir = tempfile.mkdtemp(prefix="readme-checker-")
        
        try:
            # 克隆仓库（浅克隆，只获取最新版本）
            # 注意：GitPython 的 clone_from 不直接支持超时
            # 这里我们依赖 Git 命令本身的超时行为
            Repo.clone_from(
                url, 
                temp_dir, 
                depth=1,
                # 设置 Git 配置以控制超时
                env={
                    "GIT_HTTP_LOW_SPEED_LIMIT": "1000",  # 最低速度 1KB/s
                    "GIT_HTTP_LOW_SPEED_TIME": str(config.timeout),  # 超时时间
                }
            )
            return Path(temp_dir)
            
        except GitCommandError as e:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            error_str = str(e).lower()
            
            # 判断错误类型
            if "timeout" in error_str or "timed out" in error_str:
                last_error = CloneTimeoutError(str(e))
            elif "authentication" in error_str or "403" in error_str or "401" in error_str:
                last_error = CloneAuthError(str(e))
                # 认证错误不重试
                break
            else:
                last_error = CloneNetworkError(str(e))
            
            # 如果还有重试机会，等待后重试
            if attempt < config.max_retries:
                time.sleep(delay)
                delay *= config.backoff_factor
        
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            last_error = CloneNetworkError(str(e))
            
            if attempt < config.max_retries:
                time.sleep(delay)
                delay *= config.backoff_factor
    
    # 所有重试都失败
    if last_error:
        raise last_error
    raise CloneNetworkError("Unknown error during clone")


def _clone_repository(url: str, config: Optional[CloneConfig] = None) -> Path:
    """
    克隆 GitHub 仓库到临时目录（兼容旧接口）
    
    Args:
        url: GitHub 仓库 URL
        config: 克隆配置（可选）
    
    Returns:
        克隆后的本地路径
    
    Raises:
        ValueError: 克隆失败
    """
    try:
        return clone_with_retry(url, config)
    except CloneError as e:
        error_msg = _format_clone_error_message(e, url, config.timeout if config else 60)
        raise ValueError(error_msg)


def load_repository(target: str, clone_config: Optional[CloneConfig] = None) -> RepoContext:
    """
    加载仓库（本地路径或 GitHub URL）
    
    Args:
        target: 本地路径或 GitHub URL
        clone_config: 克隆配置（可选，仅用于远程仓库）
    
    Returns:
        RepoContext 对象
    
    Raises:
        ValueError: 路径无效或仓库加载失败
    """
    is_url = _is_github_url(target)
    
    if is_url:
        # 克隆远程仓库
        repo_path = _clone_repository(target, clone_config)
        is_temporary = True
        source_url = target
    else:
        # 本地路径
        repo_path = Path(target).resolve()
        is_temporary = False
        source_url = None
        
        if not repo_path.exists():
            raise ValueError(f"Path does not exist: {target}")
        if not repo_path.is_dir():
            raise ValueError(f"Path is not a directory: {target}")
    
    # 查找 README
    readme_path = _find_readme(repo_path)
    readme_content = ""
    
    if readme_path:
        try:
            readme_content = readme_path.read_text(encoding="utf-8")
        except Exception:
            try:
                readme_content = readme_path.read_text(encoding="latin-1")
            except Exception:
                readme_content = ""
    
    return RepoContext(
        path=repo_path,
        readme_path=readme_path,
        readme_content=readme_content,
        is_temporary=is_temporary,
        source_url=source_url,
    )


def cleanup_repository(ctx: RepoContext) -> None:
    """
    清理临时仓库
    
    Args:
        ctx: 仓库上下文
    """
    if ctx.is_temporary and ctx.path.exists():
        shutil.rmtree(ctx.path, ignore_errors=True)
