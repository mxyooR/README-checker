"""
声明提取器模块 - 从解析后的 README 中提取可验证的声明

提取三类声明：
1. 生态系统声明（npm, pip, docker 等构建工具）
2. 路径声明（文件链接、图片引用）
3. 夸大声明（Enterprise, Production-ready 等词汇）
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from readme_checker.parser import ParsedReadme, CodeBlock, Link


# ============================================================
# 配置常量
# ============================================================

# 生态系统规则：关键词 -> 期望的配置文件列表
ECOSYSTEM_RULES: dict[str, list[str]] = {
    "npm": ["package.json"],
    "yarn": ["package.json"],
    "pip": ["requirements.txt", "pyproject.toml"],
    "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
    "make": ["Makefile"],
    "cargo": ["Cargo.toml"],
}

# 生态系统关键词：用于在文本中匹配
ECOSYSTEM_KEYWORDS: dict[str, list[str]] = {
    "npm": ["npm install", "npm run", "npm start", "npm test"],
    "yarn": ["yarn install", "yarn add", "yarn start", "yarn test"],
    "pip": ["pip install", "pip3 install"],
    "docker": ["docker build", "docker run", "docker-compose", "docker compose", "container"],
    "make": ["make build", "make install", "make test", "make clean"],
    "cargo": ["cargo build", "cargo run", "cargo test"],
}

# 夸大词汇列表
HYPE_WORDS: list[str] = [
    "enterprise",
    "production-ready",
    "production ready",
    "massive",
    "complex",
    "scalable",
    "robust",
    "comprehensive",
    "full-featured",
    "industrial-strength",
    "battle-tested",
]

# 完整性声明词汇
COMPLETENESS_CLAIMS: list[str] = [
    "feature complete",
    "feature-complete",
    "production ready",
    "production-ready",
    "stable",
    "mature",
    "battle-tested",
]

# Python 模块调用正则表达式
# 匹配: python -m module_name, python3 -m package.submodule
MODULE_PATTERNS: list[re.Pattern] = [
    re.compile(r'python\s+-m\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', re.IGNORECASE),
    re.compile(r'python3\s+-m\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', re.IGNORECASE),
]


# ============================================================
# 数据模型
# ============================================================

@dataclass
class EcosystemClaim:
    """
    生态系统声明 - README 中提到的构建工具
    
    Attributes:
        tool: 工具名称（npm, pip, docker 等）
        expected_files: 期望存在的配置文件列表
        keyword: 匹配到的关键词
        line_number: 关键词所在行号（如果可确定）
    """
    tool: str
    expected_files: list[str]
    keyword: str
    line_number: Optional[int] = None


@dataclass
class PathClaim:
    """
    路径声明 - README 中引用的文件路径
    
    Attributes:
        path: 文件路径
        line_number: 所在行号
        claim_type: 声明类型（image, link, command）
        source_text: 原始文本（用于错误报告）
    """
    path: str
    line_number: int
    claim_type: str  # "image", "link", "command"
    source_text: str = ""


@dataclass
class HypeClaim:
    """
    夸大声明 - README 中的夸大词汇
    
    Attributes:
        word: 匹配到的夸大词汇
        line_number: 所在行号（如果可确定）
    """
    word: str
    line_number: Optional[int] = None


@dataclass
class CompletenessClaim:
    """
    完整性声明 - README 中声称项目已完成的词汇
    
    Attributes:
        claim: 匹配到的完整性声明
        line_number: 所在行号（如果可确定）
    """
    claim: str
    line_number: Optional[int] = None


@dataclass
class ModuleClaim:
    """
    Python 模块调用声明 - README 中使用 python -m 形式调用的模块
    
    Attributes:
        module_path: 模块路径（如 "mypackage.submodule"）
        python_version: Python 版本（"python" 或 "python3"）
        line_number: 所在行号
        source_text: 原始命令文本
    """
    module_path: str
    python_version: str  # "python" or "python3"
    line_number: int
    source_text: str = ""


@dataclass
class ExtractedClaims:
    """
    提取的所有声明
    
    Attributes:
        ecosystem_claims: 生态系统声明列表
        path_claims: 路径声明列表
        hype_claims: 夸大声明列表
        completeness_claims: 完整性声明列表
        module_claims: Python 模块调用声明列表
    """
    ecosystem_claims: list[EcosystemClaim] = field(default_factory=list)
    path_claims: list[PathClaim] = field(default_factory=list)
    hype_claims: list[HypeClaim] = field(default_factory=list)
    completeness_claims: list[CompletenessClaim] = field(default_factory=list)
    module_claims: list[ModuleClaim] = field(default_factory=list)


# ============================================================
# 提取函数
# ============================================================

def _extract_ecosystem_claims(text: str) -> list[EcosystemClaim]:
    """
    从文本中提取生态系统声明
    
    Args:
        text: README 的纯文本内容
    
    Returns:
        生态系统声明列表
    """
    claims: list[EcosystemClaim] = []
    text_lower = text.lower()
    found_tools: set[str] = set()  # 避免重复
    
    for tool, keywords in ECOSYSTEM_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower and tool not in found_tools:
                found_tools.add(tool)
                claims.append(EcosystemClaim(
                    tool=tool,
                    expected_files=ECOSYSTEM_RULES[tool],
                    keyword=keyword,
                ))
                break  # 每个工具只记录一次
    
    return claims


def _extract_path_claims_from_links(links: list[Link]) -> list[PathClaim]:
    """
    从链接列表中提取路径声明
    
    只提取本地路径（以 ./ 或 ../ 开头，或不包含 :// 的相对路径）
    
    Args:
        links: 解析出的链接列表
    
    Returns:
        路径声明列表
    """
    claims: list[PathClaim] = []
    
    for link in links:
        path = link.path
        
        # 跳过外部链接（http://, https://, mailto: 等）
        if "://" in path or path.startswith("mailto:") or path.startswith("#"):
            continue
        
        # 本地路径
        claim_type = "image" if link.is_image else "link"
        claims.append(PathClaim(
            path=path,
            line_number=link.line_number,
            claim_type=claim_type,
            source_text=f"{'!' if link.is_image else ''}[{link.text}]({path})",
        ))
    
    return claims


def _extract_path_claims_from_code_blocks(code_blocks: list[CodeBlock]) -> list[PathClaim]:
    """
    从代码块中提取脚本路径声明
    
    识别 bash/shell 代码块中的脚本调用命令
    
    Args:
        code_blocks: 解析出的代码块列表
    
    Returns:
        路径声明列表
    """
    claims: list[PathClaim] = []
    
    # 匹配脚本调用的正则表达式
    # 匹配: python script.py, bash ./script.sh, node app.js 等
    script_patterns = [
        r'python[3]?\s+([^\s|>&;]+\.py)',  # python script.py
        r'bash\s+([^\s|>&;]+)',             # bash script.sh
        r'sh\s+([^\s|>&;]+)',               # sh script.sh
        r'\./([^\s|>&;]+)',                 # ./script.sh
        r'node\s+([^\s|>&;]+\.js)',         # node app.js
    ]
    
    for block in code_blocks:
        # 只处理 bash/shell 相关的代码块
        lang = block.language.lower()
        if lang not in ("bash", "shell", "sh", "zsh", "console", ""):
            continue
        
        for line in block.content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            for pattern in script_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    # 清理路径
                    path = match.strip()
                    if path:
                        claims.append(PathClaim(
                            path=path,
                            line_number=block.line_number,
                            claim_type="command",
                            source_text=line,
                        ))
    
    return claims


def _extract_hype_claims(text: str) -> list[HypeClaim]:
    """
    从文本中提取夸大声明
    
    Args:
        text: README 的纯文本内容
    
    Returns:
        夸大声明列表
    """
    claims: list[HypeClaim] = []
    text_lower = text.lower()
    
    for word in HYPE_WORDS:
        if word.lower() in text_lower:
            claims.append(HypeClaim(word=word))
    
    return claims


def _extract_completeness_claims(text: str) -> list[CompletenessClaim]:
    """
    从文本中提取完整性声明
    
    Args:
        text: README 的纯文本内容
    
    Returns:
        完整性声明列表
    """
    claims: list[CompletenessClaim] = []
    text_lower = text.lower()
    
    for claim in COMPLETENESS_CLAIMS:
        if claim.lower() in text_lower:
            claims.append(CompletenessClaim(claim=claim))
    
    return claims


def _extract_module_claims(code_blocks: list[CodeBlock]) -> list[ModuleClaim]:
    """
    从代码块中提取 Python 模块调用声明
    
    识别 bash/shell 代码块中的 python -m 和 python3 -m 命令
    
    Args:
        code_blocks: 解析出的代码块列表
    
    Returns:
        模块调用声明列表
    """
    claims: list[ModuleClaim] = []
    
    for block in code_blocks:
        # 只处理 bash/shell 相关的代码块
        lang = block.language.lower()
        if lang not in ("bash", "shell", "sh", "zsh", "console", ""):
            continue
        
        for line in block.content.split('\n'):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('#'):
                continue
            
            for pattern in MODULE_PATTERNS:
                match = pattern.search(line_stripped)
                if match:
                    module_path = match.group(1)
                    # 判断是 python 还是 python3
                    python_version = "python3" if "python3" in line_stripped.lower() else "python"
                    
                    claims.append(ModuleClaim(
                        module_path=module_path,
                        python_version=python_version,
                        line_number=block.line_number,
                        source_text=line_stripped,
                    ))
    
    return claims


def module_path_to_filesystem_paths(module_path: str) -> list[str]:
    """
    将 Python 模块路径转换为可能的文件系统路径
    
    例如:
    - "mymodule" -> ["mymodule.py", "mymodule/__init__.py"]
    - "package.submodule" -> ["package/submodule.py", "package/submodule/__init__.py"]
    
    Args:
        module_path: Python 模块路径（如 "mypackage.submodule"）
    
    Returns:
        可能的文件系统路径列表
    """
    # 将点号转换为目录分隔符
    path_parts = module_path.split('.')
    base_path = '/'.join(path_parts)
    
    return [
        f"{base_path}.py",              # 作为单个 .py 文件
        f"{base_path}/__init__.py",     # 作为包目录
    ]


def extract_claims(parsed: ParsedReadme) -> ExtractedClaims:
    """
    从解析后的 README 中提取所有可验证的声明
    
    Args:
        parsed: 解析后的 README 对象
    
    Returns:
        ExtractedClaims 对象，包含所有提取的声明
    """
    # 合并文本内容：纯文本 + 原始内容（确保不遗漏）
    full_text = parsed.text_content + " " + parsed.raw_content
    
    return ExtractedClaims(
        ecosystem_claims=_extract_ecosystem_claims(full_text),
        path_claims=(
            _extract_path_claims_from_links(parsed.links) +
            _extract_path_claims_from_code_blocks(parsed.code_blocks)
        ),
        hype_claims=_extract_hype_claims(full_text),
        completeness_claims=_extract_completeness_claims(full_text),
        module_claims=_extract_module_claims(parsed.code_blocks),
    )
