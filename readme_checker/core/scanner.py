"""
代码扫描器模块 - 扫描代码库提取环境变量和系统依赖

扫描代码文件，提取：
1. 环境变量引用（os.getenv, process.env 等）
2. 系统依赖调用（subprocess.run, exec 等）
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EnvVarUsage:
    """
    环境变量使用记录
    
    Attributes:
        name: 环境变量名称
        file_path: 源文件路径
        line_number: 行号
        pattern: 匹配的模式
    """
    name: str
    file_path: str
    line_number: int
    pattern: str


@dataclass
class SystemDependency:
    """
    系统依赖使用记录
    
    Attributes:
        tool_name: 工具名称
        file_path: 源文件路径
        line_number: 行号
        invocation: 调用方式
    """
    tool_name: str
    file_path: str
    line_number: int
    invocation: str


@dataclass
class ScanResult:
    """
    扫描结果
    
    Attributes:
        env_vars: 环境变量使用列表
        system_deps: 系统依赖列表
    """
    env_vars: list[EnvVarUsage] = field(default_factory=list)
    system_deps: list[SystemDependency] = field(default_factory=list)


# 环境变量提取模式
ENV_VAR_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        # os.getenv("KEY") or os.getenv('KEY')
        (re.compile(r'os\.getenv\s*\(\s*["\'](\w+)["\']'), 1),
        # os.environ["KEY"] or os.environ['KEY']
        (re.compile(r'os\.environ\s*\[\s*["\'](\w+)["\']'), 1),
        # os.environ.get("KEY")
        (re.compile(r'os\.environ\.get\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        # process.env.KEY
        (re.compile(r'process\.env\.(\w+)'), 1),
        # process.env["KEY"] or process.env['KEY']
        (re.compile(r'process\.env\s*\[\s*["\'](\w+)["\']'), 1),
    ],
    "go": [
        # os.Getenv("KEY")
        (re.compile(r'os\.Getenv\s*\(\s*["\'](\w+)["\']'), 1),
        # os.LookupEnv("KEY")
        (re.compile(r'os\.LookupEnv\s*\(\s*["\'](\w+)["\']'), 1),
    ],
}

# 系统依赖提取模式
SYSTEM_DEP_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        # subprocess.run(["ffmpeg", ...]) or subprocess.run("ffmpeg", ...)
        (re.compile(r'subprocess\.(?:run|call|Popen)\s*\(\s*\[?\s*["\'](\w+)["\']'), 1),
        # os.system("ffmpeg ...")
        (re.compile(r'os\.system\s*\(\s*["\'](\w+)'), 1),
        # shutil.which("ffmpeg")
        (re.compile(r'shutil\.which\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        # exec("ffmpeg ...") or execSync("ffmpeg ...")
        (re.compile(r'exec(?:Sync)?\s*\(\s*["\'](\w+)'), 1),
        # spawn("ffmpeg", [...])
        (re.compile(r'spawn\s*\(\s*["\'](\w+)["\']'), 1),
        # child_process.exec("ffmpeg")
        (re.compile(r'child_process\.exec\s*\(\s*["\'](\w+)'), 1),
    ],
    "go": [
        # exec.Command("ffmpeg", ...)
        (re.compile(r'exec\.Command\s*\(\s*["\'](\w+)["\']'), 1),
    ],
}

# 文件扩展名到语言的映射
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".jsx": "javascript",
    ".tsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
}

# 常见的系统工具（用于过滤）
COMMON_SYSTEM_TOOLS: set[str] = {
    "ffmpeg", "ffprobe", "imagemagick", "convert", "graphviz", "dot",
    "docker", "kubectl", "terraform", "ansible",
    "git", "curl", "wget", "tar", "zip", "unzip",
    "gcc", "g++", "clang", "make", "cmake",
    "python", "python3", "node", "npm", "yarn",
    "java", "javac", "mvn", "gradle",
    "ruby", "gem", "bundle",
    "go", "cargo", "rustc",
    "mysql", "psql", "redis-cli", "mongo",
}


def _is_comment_line(line: str, language: str) -> bool:
    """判断是否为注释行"""
    stripped = line.strip()
    if language == "python":
        return stripped.startswith('#')
    elif language in ("javascript", "go"):
        return stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*')
    return False


def extract_env_vars(content: str, file_path: str, language: str) -> list[EnvVarUsage]:
    """
    从代码中提取环境变量引用
    
    Args:
        content: 文件内容
        file_path: 文件路径
        language: 编程语言
    
    Returns:
        环境变量使用列表
    """
    env_vars: list[EnvVarUsage] = []
    
    patterns = ENV_VAR_PATTERNS.get(language, [])
    if not patterns:
        return env_vars
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过注释行
        if _is_comment_line(line, language):
            continue
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(line):
                var_name = match.group(group_idx)
                env_vars.append(EnvVarUsage(
                    name=var_name,
                    file_path=file_path,
                    line_number=line_num,
                    pattern=pattern.pattern,
                ))
    
    return env_vars


def extract_system_deps(content: str, file_path: str, language: str) -> list[SystemDependency]:
    """
    从代码中提取系统依赖调用
    
    Args:
        content: 文件内容
        file_path: 文件路径
        language: 编程语言
    
    Returns:
        系统依赖列表
    """
    deps: list[SystemDependency] = []
    
    patterns = SYSTEM_DEP_PATTERNS.get(language, [])
    if not patterns:
        return deps
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过注释行
        if _is_comment_line(line, language):
            continue
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(line):
                tool_name = match.group(group_idx)
                # 只记录常见的系统工具
                if tool_name.lower() in COMMON_SYSTEM_TOOLS:
                    deps.append(SystemDependency(
                        tool_name=tool_name,
                        file_path=file_path,
                        line_number=line_num,
                        invocation=line.strip()[:100],
                    ))
    
    return deps


def scan_code_files(
    repo_path: Path,
    extensions: Optional[list[str]] = None,
) -> ScanResult:
    """
    扫描代码文件
    
    Args:
        repo_path: 仓库根目录
        extensions: 要扫描的文件扩展名（默认为所有支持的扩展名）
    
    Returns:
        扫描结果
    """
    result = ScanResult()
    
    if extensions is None:
        extensions = list(EXTENSION_TO_LANGUAGE.keys())
    
    # 要忽略的目录
    ignore_dirs = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', 'target', 'vendor',
    }
    
    for file_path in repo_path.rglob('*'):
        if not file_path.is_file():
            continue
        
        # 检查是否在忽略目录中
        if any(part in ignore_dirs for part in file_path.parts):
            continue
        
        # 检查扩展名
        if file_path.suffix.lower() not in extensions:
            continue
        
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if not language:
            continue
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        
        rel_path = str(file_path.relative_to(repo_path))
        
        # 提取环境变量
        env_vars = extract_env_vars(content, rel_path, language)
        result.env_vars.extend(env_vars)
        
        # 提取系统依赖
        deps = extract_system_deps(content, rel_path, language)
        result.system_deps.extend(deps)
    
    return result


def format_env_var(env_var: EnvVarUsage) -> str:
    """
    将 EnvVarUsage 格式化为字符串
    
    Args:
        env_var: EnvVarUsage 对象
    
    Returns:
        格式化的字符串
    """
    return f"{env_var.name} ({env_var.file_path}:{env_var.line_number})"
