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
    """Registry for ecosystem plugins.
    
    支持自动发现和注册插件，遵循开闭原则。
    插件通过以下方式注册：
    1. 在模块加载时调用 PluginRegistry.register()
    2. 通过 entry_points 机制（第三方插件）
    """
    
    _plugins: dict[str, EcosystemPlugin] = {}  # name -> plugin
    _initialized: bool = False
    
    @classmethod
    def register(cls, plugin: EcosystemPlugin) -> None:
        """Register a plugin by its ecosystem name (prevents duplicates)."""
        name = plugin.info.name
        if name not in cls._plugins:
            cls._plugins[name] = plugin
    
    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a plugin by name."""
        cls._plugins.pop(name, None)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins."""
        cls._plugins.clear()
        cls._initialized = False
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure all built-in plugins are loaded."""
        if cls._initialized:
            return
        cls._initialized = True
        
        # 动态导入所有内置插件模块，触发它们的自动注册
        import importlib
        plugin_modules = [
            "readme_checker.plugins.python",
            "readme_checker.plugins.nodejs",
            "readme_checker.plugins.golang",
            "readme_checker.plugins.java",
            "readme_checker.plugins.rust",
            "readme_checker.plugins.cpp",
        ]
        for module_name in plugin_modules:
            try:
                importlib.import_module(module_name)
            except ImportError:
                pass  # 插件加载失败，跳过
    
    @classmethod
    def get_plugin(cls, name: str) -> EcosystemPlugin | None:
        """Get a plugin by ecosystem name."""
        cls._ensure_initialized()
        return cls._plugins.get(name)
    
    @classmethod
    def detect_ecosystem(cls, repo_path: Path) -> EcosystemPlugin | None:
        """Detect and return the first matching plugin for a repository."""
        cls._ensure_initialized()
        for plugin in cls._plugins.values():
            if plugin.detect(repo_path):
                return plugin
        return None
    
    @classmethod
    def detect_all_ecosystems(cls, repo_path: Path) -> list[EcosystemPlugin]:
        """Detect all applicable plugins for a repository (multi-language projects)."""
        cls._ensure_initialized()
        return [p for p in cls._plugins.values() if p.detect(repo_path)]
    
    @classmethod
    def get_all_plugins(cls) -> list[EcosystemPlugin]:
        """Get all registered plugins."""
        cls._ensure_initialized()
        return list(cls._plugins.values())
    
    @classmethod
    def get_available_types(cls) -> list[str]:
        """Get list of available plugin type names."""
        cls._ensure_initialized()
        return list(cls._plugins.keys())
