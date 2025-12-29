"""Ecosystem plugin system for README-Police V3.

This module provides a plugin architecture for supporting different
language ecosystems (Node.js, Python, Go, Java, etc.).
"""

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    PluginRegistry,
    VerificationResult,
)

# Import plugins to auto-register them
from readme_checker.plugins import nodejs
from readme_checker.plugins import python
from readme_checker.plugins import golang
from readme_checker.plugins import java

__all__ = [
    "EcosystemInfo",
    "EcosystemPlugin",
    "PluginRegistry",
    "VerificationResult",
]
