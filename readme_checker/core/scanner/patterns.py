"""
正则表达式模式定义

环境变量和系统依赖的提取模式。
"""

import re

# 环境变量提取模式
ENV_VAR_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        (re.compile(r'os\.getenv\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'os\.environ\s*\[\s*["\'](\w+)["\']'), 1),
        (re.compile(r'os\.environ\.get\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        (re.compile(r'process\.env\.(\w+)'), 1),
        (re.compile(r'process\.env\s*\[\s*["\'](\w+)["\']'), 1),
    ],
    "go": [
        (re.compile(r'os\.Getenv\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'os\.LookupEnv\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "c": [
        (re.compile(r'\bgetenv\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'std::getenv\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "java": [
        (re.compile(r'System\.getenv\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'System\.getProperty\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "rust": [
        (re.compile(r'std::env::var\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'\benv::var\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'std::env::var_os\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'\benv::var_os\s*\(\s*["\'](\w+)["\']'), 1),
    ],
}

# 系统依赖提取模式
SYSTEM_DEP_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        (re.compile(r'subprocess\.(?:run|call|Popen)\s*\(\s*\[?\s*["\'](\w+)["\']'), 1),
        (re.compile(r'os\.system\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'shutil\.which\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        # child_process.exec 要放在 exec 前面，避免重复匹配
        (re.compile(r'child_process\.exec(?:Sync)?\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'(?<!child_process\.)exec(?:Sync)?\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'spawn(?:Sync)?\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "go": [
        (re.compile(r'exec\.Command\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "c": [
        (re.compile(r'\bsystem\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'\bpopen\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'\bexecl?\s*\(\s*["\'][^"\']*?(\w+)["\']'), 1),
    ],
    "java": [
        (re.compile(r'\.exec\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'ProcessBuilder\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "rust": [
        (re.compile(r'Command::new\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'process::Command::new\s*\(\s*["\'](\w+)["\']'), 1),
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
    ".c": "c",
    ".cpp": "c",
    ".cc": "c",
    ".cxx": "c",
    ".h": "c",
    ".hpp": "c",
    ".hxx": "c",
    ".java": "java",
    ".rs": "rust",
}

# 常见的系统工具（用于过滤）
# 注意：这里只包含真正需要用户安装的外部工具
# 不包含语言运行时（python, node, java 等）因为这些是项目本身的依赖
COMMON_SYSTEM_TOOLS: set[str] = {
    # 多媒体处理
    "ffmpeg", "ffprobe", "imagemagick", "convert",
    # 图形/可视化
    "graphviz", "dot",
    # 容器/编排
    "docker", "kubectl", "terraform", "ansible",
    # 通用工具
    "git", "curl", "wget", "tar", "zip", "unzip",
    # 编译工具
    "gcc", "g++", "clang", "make", "cmake",
    # 数据库客户端
    "mysql", "psql", "redis-cli", "mongo", "sqlite3",
}
