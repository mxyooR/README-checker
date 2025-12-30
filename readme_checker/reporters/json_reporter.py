"""
JSON 报告器 - 输出 JSON 格式报告
"""

import json
import sys
from typing import TextIO

from readme_checker.core.validator import ValidationResult


class JsonReporter:
    """JSON 报告器"""
    
    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout
    
    def report(self, result: ValidationResult, target: str) -> None:
        """生成 JSON 格式报告"""
        report_data = {
            "target": target,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "file_path": issue.file_path,
                    "line_number": issue.line_number,
                    "suggestion": issue.suggestion,
                }
                for issue in result.issues
            ],
            "stats": result.stats,
            "summary": {
                "total_issues": len(result.issues),
                "errors": result.stats.get("errors", 0),
                "warnings": result.stats.get("warnings", 0),
                "passed": result.stats.get("errors", 0) == 0,
            },
        }
        
        json_str = json.dumps(report_data, indent=2, ensure_ascii=False)
        print(json_str, file=self.output)
