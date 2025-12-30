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
        (re.compile(r'exec(?:Sync)?\s*\(\s*["\'](\w+)'), 1),
        (re.compile(r'spawn\s*\(\s*["\'](\w+)["\']'), 1),
        (re.compile(r'child_process\.exec\s*\(\s*["\'](\w+)'), 1),
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
