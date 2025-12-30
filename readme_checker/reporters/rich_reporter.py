"""
Rich 终端报告器 - 使用 Rich 库输出彩色终端格式
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from readme_checker.core.validator import ValidationResult, Issue


class RichReporter:
    """Rich 终端报告器"""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def report(self, result: ValidationResult, target: str) -> None:
        """生成 Rich 格式报告"""
        error_count = result.stats.get("errors", 0)
        warning_count = result.stats.get("warnings", 0)
        
        # 标题颜色
        if error_count > 0:
            title_color = "red"
        elif warning_count > 0:
            title_color = "yellow"
        else:
            title_color = "green"
        
        self.console.print()
        self.console.print(Panel(
            f"[bold]🔍 README-Checker Report[/bold]\n[dim]Target: {target}[/dim]",
            border_style=title_color,
        ))
        
        # 检查结果表格
        self._print_summary_table(result)
        
        # 问题详情
        if result.issues:
            self._print_issues(result.issues)
        
        # 总结
        self._print_conclusion(error_count, warning_count, title_color)
    
    def _print_summary_table(self, result: ValidationResult) -> None:
        """打印摘要表格"""
        table = Table(show_header=True, header_style="bold")
        table.add_column("Check", style="cyan")
        table.add_column("Status")
        table.add_column("Details", style="dim")
        
        # 按问题代码分组统计
        code_counts: dict[str, dict[str, int]] = {}
        for issue in result.issues:
            if issue.code not in code_counts:
                code_counts[issue.code] = {"errors": 0, "warnings": 0}
            if issue.severity == "error":
                code_counts[issue.code]["errors"] += 1
            else:
                code_counts[issue.code]["warnings"] += 1
        
        # 链接检查
        link_errors = code_counts.get("DEAD_LINK", {}).get("errors", 0)
        link_errors += code_counts.get("INVALID_ANCHOR", {}).get("errors", 0)
        link_warnings = code_counts.get("ABSOLUTE_URL", {}).get("warnings", 0)
        link_passed = link_errors == 0
        link_detail = f"{link_errors} broken" if link_errors else "All valid"
        if link_warnings:
            link_detail += f", {link_warnings} warnings"
        table.add_row("Links", self._status_icon(link_passed, link_warnings > 0), link_detail)
        
        # 代码块检查
        block_errors = code_counts.get("INVALID_JSON", {}).get("errors", 0)
        block_errors += code_counts.get("INVALID_YAML", {}).get("errors", 0)
        block_warnings = code_counts.get("MISSING_LANG_TAG", {}).get("warnings", 0)
        block_passed = block_errors == 0 and block_warnings == 0
        block_detail = "All valid" if block_passed else f"{block_errors} errors, {block_warnings} warnings"
        table.add_row("Code Blocks", self._status_icon(block_passed, block_warnings > 0), block_detail)
        
        # 环境变量检查
        env_errors = code_counts.get("MISSING_ENV_VAR", {}).get("errors", 0)
        env_passed = env_errors == 0
        env_detail = f"{env_errors} undocumented" if env_errors else "All documented"
        table.add_row("Env Vars", self._status_icon(env_passed), env_detail)
        
        # 系统依赖检查
        dep_warnings = code_counts.get("MISSING_SYS_DEP", {}).get("warnings", 0)
        dep_passed = dep_warnings == 0
        dep_detail = f"{dep_warnings} undocumented" if dep_warnings else "All documented"
        table.add_row("System Deps", self._status_icon(dep_passed, dep_warnings > 0), dep_detail)
        
        # 元数据检查
        meta_warnings = code_counts.get("VERSION_MISMATCH", {}).get("warnings", 0)
        meta_warnings += code_counts.get("LICENSE_MISMATCH", {}).get("warnings", 0)
        meta_passed = meta_warnings == 0
        meta_detail = f"{meta_warnings} mismatches" if meta_warnings else "Consistent"
        table.add_row("Metadata", self._status_icon(meta_passed, meta_warnings > 0), meta_detail)
        
        self.console.print(table)
    
    def _print_issues(self, issues: list[Issue]) -> None:
        """打印问题详情"""
        self.console.print()
        self.console.print("[bold]Issues Found:[/bold]")
        
        for issue in issues:
            style = self._severity_style(issue.severity)
            location = f"{issue.file_path}"
            if issue.line_number:
                location += f":{issue.line_number}"
            
            self.console.print(
                f"  [{style}]• [{issue.severity.upper()}] {issue.message}[/{style}]"
            )
            self.console.print(f"    [dim]{location}[/dim]")
            if issue.suggestion:
                self.console.print(f"    [dim]→ {issue.suggestion}[/dim]")
    
    def _print_conclusion(self, errors: int, warnings: int, color: str) -> None:
        """打印总结"""
        self.console.print()
        
        if errors == 0 and warnings == 0:
            self.console.print(Panel(
                "[bold green]✅ All checks passed![/bold green]\n"
                "[dim]Documentation is consistent with codebase.[/dim]",
                border_style="green",
            ))
        else:
            summary = f"[bold {color}]{errors} error(s), {warnings} warning(s)[/bold {color}]"
            self.console.print(Panel(summary, border_style=color))
        
        self.console.print()
    
    @staticmethod
    def _status_icon(passed: bool, has_warnings: bool = False) -> str:
        """获取状态图标"""
        if passed and not has_warnings:
            return "✅"
        elif has_warnings and passed:
            return "⚠️"
        else:
            return "❌"
    
    @staticmethod
    def _severity_style(severity: str) -> str:
        """获取严重程度样式"""
        return {
            "error": "red",
            "warning": "yellow",
            "info": "dim",
        }.get(severity, "white")
