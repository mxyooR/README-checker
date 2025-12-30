"""
报告器基类 - 定义报告器接口
"""

from abc import ABC, abstractmethod
from typing import Protocol

from readme_checker.core.validator import ValidationResult


class Reporter(Protocol):
    """报告器协议"""
    
    def report(self, result: ValidationResult, target: str) -> None:
        """生成报告"""
        ...
