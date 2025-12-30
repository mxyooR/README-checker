"""
Scanner 模块 - 扫描代码库提取环境变量和系统依赖

拆分自原 scanner.py，模块化结构：
- models.py: 数据类定义
- patterns.py: 正则表达式模式
- python_ast.py: Python AST 解析
- js_ast.py: JavaScript AST 解析
- dotenv.py: .env 文件解析
- package_managers.py: 包管理器检测
- core.py: 主扫描函数
"""

from readme_checker.core.scanner.models import (
    EnvVarUsage,
    UnresolvedRef,
    SystemDependency,
    ScanResult,
)
from readme_checker.core.scanner.core import (
    scan_code_files,
    extract_env_vars,
    extract_system_deps,
    extract_env_vars_smart,
    format_env_var,
)
from readme_checker.core.scanner.dotenv import (
    DotEnvEntry,
    parse_dotenv_file,
    parse_dotenv_content,
    collect_documented_env_vars,
    get_documented_env_var_names,
    DOTENV_FILE_PATTERNS,
)
from readme_checker.core.scanner.package_managers import (
    PackageManagerPattern,
    PACKAGE_MANAGERS,
    extract_documented_packages,
    is_package_documented,
    get_documented_package_managers,
)
from readme_checker.core.scanner.python_ast import (
    extract_env_vars_ast,
    extract_config_library_env_vars,
)

__all__ = [
    # Models
    "EnvVarUsage",
    "UnresolvedRef", 
    "SystemDependency",
    "ScanResult",
    # Core
    "scan_code_files",
    "extract_env_vars",
    "extract_system_deps",
    "extract_env_vars_smart",
    "format_env_var",
    # DotEnv
    "DotEnvEntry",
    "parse_dotenv_file",
    "parse_dotenv_content",
    "collect_documented_env_vars",
    "get_documented_env_var_names",
    "DOTENV_FILE_PATTERNS",
    # Package Managers
    "PackageManagerPattern",
    "PACKAGE_MANAGERS",
    "extract_documented_packages",
    "is_package_documented",
    "get_documented_package_managers",
    # Python AST
    "extract_env_vars_ast",
    "extract_config_library_env_vars",
]
