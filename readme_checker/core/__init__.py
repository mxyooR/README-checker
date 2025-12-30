"""
Core Layer - 核心层

包含 Markdown 解析器、代码扫描器和验证器。
"""

from readme_checker.core.parser import (
    parse_markdown,
    generate_header_id,
    format_link,
    format_header,
    format_code_block,
    Link,
    Header,
    CodeBlock,
    ParsedMarkdown,
)
from readme_checker.core.validator import (
    Validator,
    Issue,
    ValidationResult,
)
from readme_checker.core.scanner import (
    scan_code_files,
    extract_env_vars,
    extract_system_deps,
    format_env_var,
    EnvVarUsage,
    SystemDependency,
    ScanResult,
)

__all__ = [
    # parser
    "parse_markdown",
    "generate_header_id",
    "format_link",
    "format_header",
    "format_code_block",
    "Link",
    "Header",
    "CodeBlock",
    "ParsedMarkdown",
    # validator
    "Validator",
    "Issue",
    "ValidationResult",
    # scanner
    "scan_code_files",
    "extract_env_vars",
    "extract_system_deps",
    "format_env_var",
    "EnvVarUsage",
    "SystemDependency",
    "ScanResult",
]
