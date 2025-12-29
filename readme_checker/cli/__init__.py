"""
CLI Layer - 命令行接口层

提供命令行入口和报告生成功能。
"""

from readme_checker.cli.app import app, check, version
from readme_checker.cli.reporter import generate_report

__all__ = [
    "app",
    "check", 
    "version",
    "generate_report",
]
