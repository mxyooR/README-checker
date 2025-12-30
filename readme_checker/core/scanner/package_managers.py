"""
包管理器检测

检测 README 或 Dockerfile 中的包安装命令。
"""

import re
from dataclasses import dataclass


@dataclass
class PackageManagerPattern:
    """包管理器模式定义"""
    name: str
    install_patterns: list[re.Pattern]


PACKAGE_MANAGERS: list[PackageManagerPattern] = [
    PackageManagerPattern(
        name="apt",
        install_patterns=[
            re.compile(r'apt(?:-get)?\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+apt(?:-get)?\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="brew",
        install_patterns=[
            re.compile(r'brew\s+install\s+(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="docker",
        install_patterns=[
            re.compile(r'RUN\s+apt-get\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'RUN\s+apk\s+add\s+(?:--no-cache\s+)?(.+)', re.IGNORECASE),
            re.compile(r'RUN\s+yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="nix",
        install_patterns=[
            re.compile(r'nix-env\s+-i\s+(.+)', re.IGNORECASE),
            re.compile(r'nix\s+profile\s+install\s+(.+)', re.IGNORECASE),
            re.compile(r'nix-shell\s+-p\s+(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="pacman",
        install_patterns=[
            re.compile(r'pacman\s+-S\s+(?:--noconfirm\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+pacman\s+-S\s+(?:--noconfirm\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="yum",
        install_patterns=[
            re.compile(r'yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="dnf",
        install_patterns=[
            re.compile(r'dnf\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+dnf\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
]


def extract_documented_packages(content: str) -> dict[str, set[str]]:
    """从 README 或 Dockerfile 内容中提取已文档化的包"""
    documented: dict[str, set[str]] = {}
    
    for pm in PACKAGE_MANAGERS:
        packages: set[str] = set()
        for pattern in pm.install_patterns:
            for match in pattern.finditer(content):
                pkg_str = match.group(1).strip()
                pkg_str = re.sub(r'\s+&&.*', '', pkg_str)
                pkg_str = re.sub(r'\s+\\$', '', pkg_str)
                pkg_str = re.sub(r'\s*#.*', '', pkg_str)
                for pkg in pkg_str.split():
                    if pkg.startswith('-'):
                        continue
                    pkg = re.sub(r'[=<>].*', '', pkg)
                    if pkg:
                        packages.add(pkg.lower())
        if packages:
            documented[pm.name] = packages
    
    return documented


def is_package_documented(package_name: str, documented_packages: dict[str, set[str]]) -> bool:
    """检查包是否在任何包管理器中被文档化"""
    pkg_lower = package_name.lower()
    for packages in documented_packages.values():
        if pkg_lower in packages:
            return True
    return False


def get_documented_package_managers(package_name: str, documented_packages: dict[str, set[str]]) -> list[str]:
    """获取文档化了指定包的包管理器列表"""
    pkg_lower = package_name.lower()
    managers = []
    for pm_name, packages in documented_packages.items():
        if pkg_lower in packages:
            managers.append(pm_name)
    return managers
