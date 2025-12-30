"""
DotEnv 文件解析

解析 .env.example 等文件，提取已文档化的环境变量。
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DotEnvEntry:
    """dotenv 文件条目"""
    name: str
    value: Optional[str] = None
    comment: Optional[str] = None
    line_number: int = 0
    file_path: str = ""


# .env 文件名模式
DOTENV_FILE_PATTERNS = [
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.development.example",
    ".env.production.example",
    ".env.local.example",
    ".env.test.example",
]


def parse_dotenv_file(file_path: Path) -> list[DotEnvEntry]:
    """解析 .env 文件"""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return []
    return parse_dotenv_content(content, str(file_path))


def parse_dotenv_content(content: str, file_path: str = "") -> list[DotEnvEntry]:
    """解析 .env 文件内容字符串"""
    entries: list[DotEnvEntry] = []
    
    line_pattern = re.compile(
        r'^(?:export\s+)?'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'\s*=\s*'
        r'(?:'
        r'"([^"]*)"'
        r"|'([^']*)'"
        r'|([^#\n]*?)'
        r')'
        r'(?:\s*#\s*(.*))?$'
    )
    comment_pattern = re.compile(r'^\s*#\s*(.*)$')
    pending_comment: Optional[str] = None
    
    for line_num, line in enumerate(content.split('\n'), 1):
        line = line.strip()
        if not line:
            pending_comment = None
            continue
        
        comment_match = comment_pattern.match(line)
        if comment_match and '=' not in line:
            pending_comment = comment_match.group(1).strip()
            continue
        
        match = line_pattern.match(line)
        if match:
            name = match.group(1)
            value = match.group(2) or match.group(3) or (match.group(4).strip() if match.group(4) else None)
            inline_comment = match.group(5)
            comment = inline_comment.strip() if inline_comment else pending_comment
            
            entries.append(DotEnvEntry(
                name=name,
                value=value,
                comment=comment,
                line_number=line_num,
                file_path=file_path,
            ))
            pending_comment = None
    
    return entries


def collect_documented_env_vars(repo_path: Path) -> dict[str, list[str]]:
    """收集所有文档来源中的环境变量"""
    documented: dict[str, list[str]] = {}
    for pattern in DOTENV_FILE_PATTERNS:
        env_file = repo_path / pattern
        if env_file.exists():
            entries = parse_dotenv_file(env_file)
            for entry in entries:
                if entry.name not in documented:
                    documented[entry.name] = []
                documented[entry.name].append(entry.file_path)
    return documented


def get_documented_env_var_names(repo_path: Path) -> set[str]:
    """获取所有文档化的环境变量名称"""
    documented = collect_documented_env_vars(repo_path)
    return set(documented.keys())
