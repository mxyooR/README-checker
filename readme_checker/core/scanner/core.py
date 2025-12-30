"""
核心扫描函数

主要的代码扫描逻辑。
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from readme_checker.core.scanner.models import (
    EnvVarUsage,
    UnresolvedRef,
    SystemDependency,
    ScanResult,
)
from readme_checker.core.scanner.patterns import (
    ENV_VAR_PATTERNS,
    SYSTEM_DEP_PATTERNS,
    EXTENSION_TO_LANGUAGE,
    COMMON_SYSTEM_TOOLS,
)
from readme_checker.core.scanner.python_ast import (
    extract_env_vars_ast,
    extract_config_library_env_vars,
)
from readme_checker.core.scanner.js_ast import (
    extract_env_vars_js_ast,
    ESPRIMA_AVAILABLE,
)

logger = logging.getLogger(__name__)

# AST 文件大小限制 (10MB)
AST_FILE_SIZE_LIMIT = 10 * 1024 * 1024

# 进度回调类型
ProgressCallback = Callable[[str, str], None]


def _is_comment_line(line: str, language: str) -> bool:
    """判断是否为注释行"""
    stripped = line.strip()
    if language == "python":
        return stripped.startswith('#')
    elif language in ("javascript", "go", "java", "rust", "c"):
        return stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*')
    return False


def _strip_comments(line: str, language: str) -> str:
    """
    移除行内注释，返回有效代码部分
    
    处理：
    - Python: code # comment
    - C-style: code // comment
    - C-style: code /* comment */
    - 字符串内的注释符号不会被误判
    """
    if language == "python":
        # 简单处理：找到 # 但要避免字符串内的 #
        in_string = None
        for i, char in enumerate(line):
            if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                if in_string is None:
                    in_string = char
                elif in_string == char:
                    in_string = None
            elif char == '#' and in_string is None:
                return line[:i]
        return line
    
    elif language in ("javascript", "go", "java", "rust", "c"):
        # 处理 // 和 /* */ 注释，但要避免字符串内的
        result = []
        in_string = None
        in_block_comment = False
        i = 0
        while i < len(line):
            char = line[i]
            
            # 在块注释中
            if in_block_comment:
                if char == '*' and i + 1 < len(line) and line[i+1] == '/':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            
            # 检查字符串边界
            if char in ('"', "'", '`') and (i == 0 or line[i-1] != '\\'):
                if in_string is None:
                    in_string = char
                elif in_string == char:
                    in_string = None
                result.append(char)
            # 检查 // 注释
            elif char == '/' and i + 1 < len(line) and line[i+1] == '/' and in_string is None:
                break  # 行尾注释，直接结束
            # 检查 /* 块注释开始
            elif char == '/' and i + 1 < len(line) and line[i+1] == '*' and in_string is None:
                in_block_comment = True
                i += 2
                continue
            else:
                result.append(char)
            i += 1
        return ''.join(result)
    
    return line


def _remove_block_comments(content: str, language: str) -> str:
    """
    移除跨行块注释 /* ... */
    
    这个函数在逐行处理之前调用，用于处理跨行的块注释
    """
    if language not in ("javascript", "go", "java", "rust", "c"):
        return content
    
    result = []
    in_string = None
    in_block_comment = False
    i = 0
    
    while i < len(content):
        char = content[i]
        
        # 在块注释中
        if in_block_comment:
            if char == '*' and i + 1 < len(content) and content[i+1] == '/':
                in_block_comment = False
                i += 2
                continue
            # 保留换行符以维持行号
            if char == '\n':
                result.append(char)
            i += 1
            continue
        
        # 检查字符串边界（简化处理，不处理转义）
        if char in ('"', "'", '`'):
            if in_string is None:
                in_string = char
            elif in_string == char:
                in_string = None
            result.append(char)
        # 检查 /* 块注释开始
        elif char == '/' and i + 1 < len(content) and content[i+1] == '*' and in_string is None:
            in_block_comment = True
            i += 2
            continue
        else:
            result.append(char)
        i += 1
    
    return ''.join(result)


def extract_env_vars(content: str, file_path: str, language: str) -> list[EnvVarUsage]:
    """从代码中提取环境变量引用（正则模式）
    
    改进：
    - 移除跨行块注释 /* ... */
    - 跳过整行注释
    - 移除行内注释后再匹配
    - 避免注释中的误报
    """
    env_vars: list[EnvVarUsage] = []
    patterns = ENV_VAR_PATTERNS.get(language, [])
    if not patterns:
        return env_vars
    
    # 先移除跨行块注释
    cleaned_content = _remove_block_comments(content, language)
    
    lines = cleaned_content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过整行注释
        if _is_comment_line(line, language):
            continue
        
        # 移除行内注释，只匹配有效代码部分
        code_part = _strip_comments(line, language)
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(code_part):
                var_name = match.group(group_idx)
                env_vars.append(EnvVarUsage(
                    name=var_name,
                    file_path=file_path,
                    line_number=line_num,
                    column_number=match.start(),
                    pattern=pattern.pattern,
                ))
    return env_vars


def extract_system_deps(content: str, file_path: str, language: str) -> list[SystemDependency]:
    """从代码中提取系统依赖调用
    
    改进：
    - 移除跨行块注释 /* ... */
    - 跳过整行注释
    - 移除行内注释后再匹配
    - 去重：同一行同一工具只报告一次
    """
    deps: list[SystemDependency] = []
    patterns = SYSTEM_DEP_PATTERNS.get(language, [])
    if not patterns:
        return deps
    
    # 用于去重：(行号, 工具名)
    seen: set[tuple[int, str]] = set()
    
    # 先移除跨行块注释
    cleaned_content = _remove_block_comments(content, language)
    
    lines = cleaned_content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过整行注释
        if _is_comment_line(line, language):
            continue
        
        # 移除行内注释
        code_part = _strip_comments(line, language)
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(code_part):
                tool_name = match.group(group_idx)
                tool_lower = tool_name.lower()
                
                # 检查是否在工具列表中，并去重
                if tool_lower in COMMON_SYSTEM_TOOLS:
                    key = (line_num, tool_lower)
                    if key not in seen:
                        seen.add(key)
                        deps.append(SystemDependency(
                            tool_name=tool_name,
                            file_path=file_path,
                            line_number=line_num,
                            invocation=line.strip()[:100],
                        ))
    return deps


def extract_env_vars_smart(
    content: str,
    file_path: str,
    language: str,
    file_size: int = 0,
) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
    """智能提取环境变量 - AST 优先，正则回退"""
    unresolved: list[UnresolvedRef] = []
    
    # JavaScript/TypeScript
    if language == "javascript":
        if ESPRIMA_AVAILABLE and file_size <= AST_FILE_SIZE_LIMIT:
            js_env_vars, js_unresolved = extract_env_vars_js_ast(content, file_path)
            if js_env_vars or js_unresolved:
                return js_env_vars, js_unresolved
        return extract_env_vars(content, file_path, language), unresolved
    
    # 非 Python 直接用正则
    if language != "python":
        return extract_env_vars(content, file_path, language), unresolved
    
    # 大文件跳过 AST
    if file_size > AST_FILE_SIZE_LIMIT:
        logger.warning(f"File {file_path} exceeds {AST_FILE_SIZE_LIMIT} bytes, using regex fallback")
        return extract_env_vars(content, file_path, language), unresolved
    
    # Python AST 解析
    try:
        ast_env_vars, ast_unresolved = extract_env_vars_ast(content, file_path)
        unresolved.extend(ast_unresolved)
        config_env_vars = extract_config_library_env_vars(content, file_path)
        
        # 合并去重
        seen_names: set[str] = set()
        all_env_vars: list[EnvVarUsage] = []
        for ev in ast_env_vars + config_env_vars:
            key = (ev.name, ev.file_path, ev.line_number)
            if key not in seen_names:
                seen_names.add(key)
                all_env_vars.append(ev)
        return all_env_vars, unresolved
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}, using regex fallback: {e}")
        return extract_env_vars(content, file_path, language), unresolved
    except Exception as e:
        logger.warning(f"AST parsing failed for {file_path}, using regex fallback: {e}")
        return extract_env_vars(content, file_path, language), unresolved


def scan_code_files(
    repo_path: Path,
    extensions: Optional[list[str]] = None,
    use_ast: bool = True,
    on_file: Optional[ProgressCallback] = None,
) -> ScanResult:
    """扫描代码文件"""
    result = ScanResult()
    
    if extensions is None:
        extensions = list(EXTENSION_TO_LANGUAGE.keys())
    
    ignore_dirs = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', 'target', 'vendor',
    }
    
    def safe_walk(path: Path):
        try:
            for entry in path.iterdir():
                try:
                    if entry.is_dir():
                        if entry.name not in ignore_dirs:
                            yield from safe_walk(entry)
                    elif entry.is_file():
                        yield entry
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            return
    
    for file_path in safe_walk(repo_path):
        if file_path.suffix.lower() not in extensions:
            continue
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if not language:
            continue
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            file_size = file_path.stat().st_size
        except Exception:
            continue
        
        rel_path = str(file_path.relative_to(repo_path))
        
        if on_file:
            on_file(rel_path, language)
        
        if use_ast:
            env_vars, unresolved = extract_env_vars_smart(content, rel_path, language, file_size)
            result.env_vars.extend(env_vars)
            result.unresolved_refs.extend(unresolved)
        else:
            env_vars = extract_env_vars(content, rel_path, language)
            result.env_vars.extend(env_vars)
        
        deps = extract_system_deps(content, rel_path, language)
        result.system_deps.extend(deps)
    
    return result


def format_env_var(env_var: EnvVarUsage, ide_format: bool = False) -> str:
    """将 EnvVarUsage 格式化为字符串"""
    if ide_format:
        return f"{env_var.file_path}:{env_var.line_number}:{env_var.column_number}: {env_var.name}"
    return f"{env_var.name} ({env_var.file_path}:{env_var.line_number})"
