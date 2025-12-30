"""
数据模型定义

包含扫描器使用的所有数据类。
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class EnvVarUsage:
    """
    环境变量使用记录
    
    Attributes:
        name: 环境变量名称
        file_path: 源文件路径
        line_number: 行号 (1-based)
        column_number: 列号 (0-based)
        pattern: 匹配的模式
        source_library: 来源配置库 (pydantic, decouple, django-environ 等)
        context: 上下文信息 (类名、函数名)
    """
    name: str
    file_path: str
    line_number: int
    column_number: int = 0
    pattern: str = ""
    source_library: Optional[str] = None
    context: Optional[str] = None


@dataclass
class UnresolvedRef:
    """
    无法解析的动态引用
    
    Attributes:
        file_path: 源文件路径
        line_number: 行号 (1-based)
        column_number: 列号 (0-based)
        expression: 原始表达式
        reason: 无法解析的原因
    """
    file_path: str
    line_number: int
    column_number: int
    expression: str
    reason: str


@dataclass
class SystemDependency:
    """
    系统依赖使用记录
    
    Attributes:
        tool_name: 工具名称
        file_path: 源文件路径
        line_number: 行号
        invocation: 调用方式
    """
    tool_name: str
    file_path: str
    line_number: int
    invocation: str


@dataclass
class ScanResult:
    """
    扫描结果
    
    Attributes:
        env_vars: 环境变量使用列表
        system_deps: 系统依赖列表
        unresolved_refs: 无法解析的动态引用列表
    """
    env_vars: list[EnvVarUsage] = field(default_factory=list)
    system_deps: list[SystemDependency] = field(default_factory=list)
    unresolved_refs: list[UnresolvedRef] = field(default_factory=list)
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        data = {
            "env_vars": [asdict(ev) for ev in self.env_vars],
            "system_deps": [asdict(sd) for sd in self.system_deps],
            "unresolved_refs": [asdict(ur) for ur in self.unresolved_refs],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ScanResult":
        """从 JSON 字符串反序列化"""
        data = json.loads(json_str)
        return cls(
            env_vars=[EnvVarUsage(**ev) for ev in data.get("env_vars", [])],
            system_deps=[SystemDependency(**sd) for sd in data.get("system_deps", [])],
            unresolved_refs=[UnresolvedRef(**ur) for ur in data.get("unresolved_refs", [])],
        )
