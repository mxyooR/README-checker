"""
Parsing Layer - 解析层

负责 Markdown 解析和声明提取。
"""

from readme_checker.parsing.markdown import (
    parse_readme,
    render_readme,
    ParsedReadme,
    CodeBlock,
    Link,
)
from readme_checker.parsing.extractor import (
    extract_claims,
    ExtractedClaims,
    EcosystemClaim,
    PathClaim,
    HypeClaim,
    CompletenessClaim,
    ModuleClaim,
    module_path_to_filesystem_paths,
)
from readme_checker.parsing.commands import extract_commands, ExtractedCommand

__all__ = [
    # markdown
    "parse_readme",
    "render_readme",
    "ParsedReadme",
    "CodeBlock",
    "Link",
    # extractor
    "extract_claims",
    "ExtractedClaims",
    "EcosystemClaim",
    "PathClaim",
    "HypeClaim",
    "CompletenessClaim",
    "ModuleClaim",
    "module_path_to_filesystem_paths",
    # commands
    "extract_commands",
    "ExtractedCommand",
]
