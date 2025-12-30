"""Ecosystem plugin base classes.

This module provides the plugin architecture for supporting
different language ecosystems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class EcosystemInfo:
    """Ecosystem information."""
    name: str
    config_files: list[str]
    package_manager: str | None = None
    common_commands: list[str] = field(default_factory=list)


@dataclass
class ProjectMetadata:
    """
    项目元数据
    
    Attributes:
        name: 项目名称
        version: 版本号
        license: 许可证类型
        source_file: 元数据来源文件
    """
    name: Optional[str] = None
    version: Optional[str] = None
    license: Optional[str] = None
    source_file: str = ""


@dataclass
class VerificationResult:
    """Verification result from a plugin."""
    claim: str
    status: Literal["verified", "missing", "build_artifact", "skipped", "optional"]
    message: str
    severity: Literal["error", "warning", "info"]
    suggestion: str | None = None


class EcosystemPlugin(ABC):
    """Base class for ecosystem plugins."""
    
    @property
    @abstractmethod
    def info(self) -> EcosystemInfo:
        """Return ecosystem information."""
        pass
    
    @abstractmethod
    def detect(self, repo_path: Path) -> bool:
        """Detect if project belongs to this ecosystem."""
        pass
    
    @abstractmethod
    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """
        Verify a command for this ecosystem.
        
        Returns None if this plugin doesn't handle the command.
        """
        pass
    
    @abstractmethod
    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get files expected to exist for this ecosystem."""
        pass
    
    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        提取项目元数据（版本号、许可证等）
        
        子类应重写此方法以提供具体实现。
        默认返回空元数据。
        
        Args:
            repo_path: 仓库根目录
        
        Returns:
            ProjectMetadata 对象
        """
        return ProjectMetadata()


class PluginRegistry:
    """Registry for ecosystem plugins."""
    
    _plugins: list[EcosystemPlugin] = []
    
    @classmethod
    def register(cls, plugin: EcosystemPlugin) -> None:
        """Register a plugin."""
        cls._plugins.append(plugin)
    
    @classmethod
    def unregister(cls, plugin: EcosystemPlugin) -> None:
        """Unregister a plugin."""
        if plugin in cls._plugins:
            cls._plugins.remove(plugin)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins."""
        cls._plugins.clear()
    
    @classmethod
    def detect_ecosystem(cls, repo_path: Path) -> list[EcosystemPlugin]:
        """Detect applicable plugins for a repository."""
        return [p for p in cls._plugins if p.detect(repo_path)]
    
    @classmethod
    def get_all_plugins(cls) -> list[EcosystemPlugin]:
        """Get all registered plugins."""
        return list(cls._plugins)
