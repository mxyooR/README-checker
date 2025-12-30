"""Ecosystem plugin system for README-Checker.

This module provides a plugin architecture for supporting different
language ecosystems (Node.js, Python, Go, Java, Rust, C++ etc.).

插件通过 PluginRegistry 自动发现和注册，无需手动 import。
"""

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    PluginRegistry,
    ProjectMetadata,
    VerificationResult,
)

__all__ = [
    "EcosystemInfo",
    "EcosystemPlugin",
    "PluginRegistry",
    "ProjectMetadata",
    "VerificationResult",
]
