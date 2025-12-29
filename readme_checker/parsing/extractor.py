"""
声明提取器模块 - 从解析后的 README 中提取可验证的声明

提取三类声明：
1. 生态系统声明（npm, pip, docker 等构建工具）
2. 路径声明（文件链接、图片引用）
3. 夸大声明（Enterprise, Production-ready 等词汇）

V3 增强：
- 语义分析：理解否定句/条件句
- 健壮命令提取：使用 shlex 处理复杂命令
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from readme_checker.parsing.markdown import ParsedReadme, CodeBlock, Link

# V3: Import semantic analysis and command extraction
try:
    from readme_checker.nlp.intent import classify_intent, Intent, ClassifiedInstruction
    from readme_checker.parsing.commands import extract_commands, ExtractedCommand
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    Intent = None  # type: ignore
    ClassifiedInstruction = None  # type: ignore
    ExtractedCommand = None  # type: ignore


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
MODULE_PATTERNS: list[re.Pattern] = [
    re.compile(r'python\s+-m\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', re.IGNORECASE),
    re.compile(r'python3\s+-m\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', re.IGNORECASE),
]


# ============================================================
# 数据模型
# ============================================================

@dataclass
class EcosystemClaim:
    """生态系统声明 - README 中提到的构建工具"""
    tool: str
    expected_files: list[str]
    keyword: str
    line_number: Optional[int] = None


@dataclass
class PathClaim:
    """路径声明 - README 中引用的文件路径"""
    path: str
    line_number: int
    claim_type: str  # "image", "link", "command"
    source_text: str = ""


@dataclass
class HypeClaim:
    """夸大声明 - README 中的夸大词汇"""
    word: str
    line_number: Optional[int] = None


@dataclass
class CompletenessClaim:
    """完整性声明 - README 中声称项目已完成的词汇"""
    claim: str
    line_number: Optional[int] = None


@dataclass
class ModuleClaim:
    """Python 模块调用声明"""
    module_path: str
    python_version: str
    line_number: int
    source_text: str = ""


@dataclass
class ExtractedClaims:
    """提取的所有声明"""
    ecosystem_claims: list[EcosystemClaim] = field(default_factory=list)
    path_claims: list[PathClaim] = field(default_factory=list)
    hype_claims: list[HypeClaim] = field(default_factory=list)
    completeness_claims: list[CompletenessClaim] = field(default_factory=list)
    module_claims: list[ModuleClaim] = field(default_factory=list)
    classified_commands: list["ClassifiedInstruction"] = field(default_factory=list)


# ============================================================
# 提取函数
# ============================================================

def _extract_ecosystem_claims(text: str) -> list[EcosystemClaim]:
    """从文本中提取生态系统声明"""
    claims: list[EcosystemClaim] = []
    text_lower = text.lower()
    found_tools: set[str] = set()
    
    for tool, keywords in ECOSYSTEM_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower and tool not in found_tools:
                found_tools.add(tool)
                claims.append(EcosystemClaim(
                    tool=tool,
                    expected_files=ECOSYSTEM_RULES[tool],
                    keyword=keyword,
                ))
                break
    
    return claims


def _extract_path_claims_from_links(links: list[Link]) -> list[PathClaim]:
    """从链接列表中提取路径声明"""
    claims: list[PathClaim] = []
    
    for link in links:
        path = link.path
        if "://" in path or path.startswith("mailto:") or path.startswith("#"):
            continue
        
        claim_type = "image" if link.is_image else "link"
        claims.append(PathClaim(
            path=path,
            line_number=link.line_number,
            claim_type=claim_type,
            source_text=f"{'!' if link.is_image else ''}[{link.text}]({path})",
        ))
    
    return claims


def _extract_path_claims_from_code_blocks(code_blocks: list[CodeBlock]) -> list[PathClaim]:
    """从代码块中提取脚本路径声明"""
    claims: list[PathClaim] = []
    
    script_patterns = [
        r'python[3]?\s+([^\s|>&;]+\.py)',
        r'bash\s+([^\s|>&;]+)',
        r'sh\s+([^\s|>&;]+)',
        r'\./([^\s|>&;]+)',
        r'node\s+([^\s|>&;]+\.js)',
    ]
    
    for block in code_blocks:
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
    """从文本中提取夸大声明"""
    claims: list[HypeClaim] = []
    text_lower = text.lower()
    
    for word in HYPE_WORDS:
        if word.lower() in text_lower:
            claims.append(HypeClaim(word=word))
    
    return claims


def _extract_completeness_claims(text: str) -> list[CompletenessClaim]:
    """从文本中提取完整性声明"""
    claims: list[CompletenessClaim] = []
    text_lower = text.lower()
    
    for claim in COMPLETENESS_CLAIMS:
        if claim.lower() in text_lower:
            claims.append(CompletenessClaim(claim=claim))
    
    return claims


def _extract_module_claims(code_blocks: list[CodeBlock]) -> list[ModuleClaim]:
    """从代码块中提取 Python 模块调用声明"""
    claims: list[ModuleClaim] = []
    
    for block in code_blocks:
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
                    python_version = "python3" if "python3" in line_stripped.lower() else "python"
                    claims.append(ModuleClaim(
                        module_path=module_path,
                        python_version=python_version,
                        line_number=block.line_number,
                        source_text=line_stripped,
                    ))
    
    return claims


def module_path_to_filesystem_paths(module_path: str) -> list[str]:
    """将 Python 模块路径转换为可能的文件系统路径"""
    path_parts = module_path.split('.')
    base_path = '/'.join(path_parts)
    
    return [
        f"{base_path}.py",
        f"{base_path}/__init__.py",
    ]


def extract_claims(parsed: ParsedReadme) -> ExtractedClaims:
    """从解析后的 README 中提取所有可验证的声明"""
    full_text = parsed.text_content + " " + parsed.raw_content
    
    claims = ExtractedClaims(
        ecosystem_claims=_extract_ecosystem_claims(full_text),
        path_claims=(
            _extract_path_claims_from_links(parsed.links) +
            _extract_path_claims_from_code_blocks(parsed.code_blocks)
        ),
        hype_claims=_extract_hype_claims(full_text),
        completeness_claims=_extract_completeness_claims(full_text),
        module_claims=_extract_module_claims(parsed.code_blocks),
    )
    
    if SEMANTIC_AVAILABLE:
        claims.classified_commands = _extract_classified_commands(
            parsed.code_blocks, 
            parsed.raw_content
        )
    
    return claims


def _extract_classified_commands(
    code_blocks: list[CodeBlock],
    raw_content: str,
) -> list["ClassifiedInstruction"]:
    """V3: 提取带语义分类的命令"""
    if not SEMANTIC_AVAILABLE:
        return []
    
    classified: list[ClassifiedInstruction] = []
    
    for block in code_blocks:
        lang = block.language.lower()
        if lang not in ("bash", "shell", "sh", "zsh", "console", ""):
            continue
        
        commands = extract_commands(block.content, lang)
        
        for cmd in commands:
            context = _get_command_context(raw_content, cmd.raw_text, block.line_number)
            instruction = classify_intent(
                text=context,
                command=cmd.raw_text,
                line_number=block.line_number + cmd.line_number,
            )
            classified.append(instruction)
    
    return classified


def _get_command_context(raw_content: str, command: str, line_number: int) -> str:
    """获取命令周围的上下文文本"""
    lines = raw_content.split('\n')
    start = max(0, line_number - 4)
    end = min(len(lines), line_number + 3)
    context_lines = lines[start:end]
    return '\n'.join(context_lines)
