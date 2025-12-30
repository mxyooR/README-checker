"""
Rich 终端报告器 - 使用 Rich 库输出彩色终端格式

风格参考：代码质量分析工具，带分数、评级、进度条和趣味评语
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

from readme_checker.core.validator import ValidationResult, Issue


# 评级系统
RATINGS = [
    (90, "🏆 文档大师", "完美！你的文档比代码还靠谱", "green"),
    (80, "⭐ 优秀文档", "很棒！只差一点点就完美了", "green"),
    (70, "✅ 良好文档", "不错，但还有提升空间", "cyan"),
    (60, "📝 及格文档", "勉强能用，建议抽空改改", "yellow"),
    (40, "⚠️ 问题文档", "有点问题，用户可能会骂你", "yellow"),
    (20, "❌ 糟糕文档", "问题很多，赶紧修吧", "red"),
    (0, "💀 灾难文档", "这文档是来搞笑的吗？", "red"),
]

# 检查项权重
WEIGHTS = {
    "links": 0.20,        # 链接验证
    "code_blocks": 0.10,  # 代码块验证
    "env_vars": 0.25,     # 环境变量
    "sys_deps": 0.15,     # 系统依赖
    "commands": 0.15,     # 命令验证
    "metadata": 0.15,     # 元数据一致性
}


class RichReporter:
    """Rich 终端报告器 - 带分数和评级"""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def report(self, result: ValidationResult, target: str) -> None:
        """生成 Rich 格式报告"""
        # 计算各项分数
        scores = self._calculate_scores(result)
        total_score = self._calculate_total_score(scores)
        rating = self._get_rating(total_score)
        
        # 打印分隔线
        self.console.print()
        self.console.print("─" * 80, style="dim")
        self.console.print(
            "📋 README-Checker 文档质量分析报告 📋",
            style="bold cyan",
            justify="center"
        )
        self.console.print("─" * 80, style="dim")
        
        # 总分和评级
        self._print_score_panel(total_score, rating, target)
        
        # 详细指标
        self._print_metrics(scores)
        
        # 问题详情
        if result.issues:
            self._print_issues_ranking(result.issues)
        
        # 总结
        self._print_conclusion(total_score, rating, result)
    
    def _calculate_scores(self, result: ValidationResult) -> dict[str, dict]:
        """计算各项检查的分数"""
        # 按问题代码分组统计
        code_counts: dict[str, dict[str, int]] = {}
        for issue in result.issues:
            if issue.code not in code_counts:
                code_counts[issue.code] = {"errors": 0, "warnings": 0}
            if issue.severity == "error":
                code_counts[issue.code]["errors"] += 1
            else:
                code_counts[issue.code]["warnings"] += 1
        
        scores = {}
        
        # 链接检查 (每个错误扣20分，警告扣5分)
        link_errors = code_counts.get("DEAD_LINK", {}).get("errors", 0)
        link_errors += code_counts.get("INVALID_ANCHOR", {}).get("errors", 0)
        link_warnings = code_counts.get("ABSOLUTE_URL", {}).get("warnings", 0)
        link_score = max(0, 100 - link_errors * 20 - link_warnings * 5)
        scores["links"] = {
            "score": link_score,
            "errors": link_errors,
            "warnings": link_warnings,
            "label": "链接验证",
            "icon": "🔗",
        }
        
        # 代码块检查
        block_errors = code_counts.get("INVALID_JSON", {}).get("errors", 0)
        block_errors += code_counts.get("INVALID_YAML", {}).get("errors", 0)
        block_warnings = code_counts.get("MISSING_LANG_TAG", {}).get("warnings", 0)
        block_score = max(0, 100 - block_errors * 15 - block_warnings * 5)
        scores["code_blocks"] = {
            "score": block_score,
            "errors": block_errors,
            "warnings": block_warnings,
            "label": "代码块语法",
            "icon": "📝",
        }
        
        # 环境变量检查 (每个未文档化扣15分)
        env_errors = code_counts.get("MISSING_ENV_VAR", {}).get("errors", 0)
        env_score = max(0, 100 - env_errors * 15)
        scores["env_vars"] = {
            "score": env_score,
            "errors": env_errors,
            "warnings": 0,
            "label": "环境变量",
            "icon": "🔐",
        }
        
        # 系统依赖检查
        dep_warnings = code_counts.get("MISSING_SYS_DEP", {}).get("warnings", 0)
        dep_score = max(0, 100 - dep_warnings * 10)
        scores["sys_deps"] = {
            "score": dep_score,
            "errors": 0,
            "warnings": dep_warnings,
            "label": "系统依赖",
            "icon": "🔧",
        }
        
        # 命令验证
        cmd_warnings = code_counts.get("INVALID_COMMAND", {}).get("warnings", 0)
        cmd_score = max(0, 100 - cmd_warnings * 15)
        scores["commands"] = {
            "score": cmd_score,
            "errors": 0,
            "warnings": cmd_warnings,
            "label": "命令验证",
            "icon": "💻",
        }
        
        # 元数据检查
        meta_warnings = code_counts.get("VERSION_MISMATCH", {}).get("warnings", 0)
        meta_warnings += code_counts.get("LICENSE_MISMATCH", {}).get("warnings", 0)
        meta_score = max(0, 100 - meta_warnings * 20)
        scores["metadata"] = {
            "score": meta_score,
            "errors": 0,
            "warnings": meta_warnings,
            "label": "元数据一致性",
            "icon": "📊",
        }
        
        return scores
    
    def _calculate_total_score(self, scores: dict[str, dict]) -> float:
        """计算加权总分"""
        total = 0.0
        for key, weight in WEIGHTS.items():
            if key in scores:
                total += scores[key]["score"] * weight
        return round(total, 2)
    
    def _get_rating(self, score: float) -> tuple[str, str, str]:
        """根据分数获取评级"""
        for threshold, title, desc, color in RATINGS:
            if score >= threshold:
                return title, desc, color
        return RATINGS[-1][1], RATINGS[-1][2], RATINGS[-1][3]
    
    def _print_score_panel(self, score: float, rating: tuple, target: str) -> None:
        """打印分数面板"""
        title, desc, color = rating
        
        # 分数进度条
        bar_width = 30
        filled = int(score / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        content = Text()
        content.append(f"总分: ", style="bold")
        content.append(f"{score:.1f}", style=f"bold {color}")
        content.append(f" / 100\n", style="dim")
        content.append(f"[{bar}]\n\n", style=color)
        content.append(f"评级: ", style="bold")
        content.append(f"{title}\n", style=f"bold {color}")
        content.append(f"{desc}\n\n", style="dim")
        content.append(f"目标: {target}", style="dim")
        
        self.console.print(Panel(
            content,
            title="[bold]📊 文档质量评分[/bold]",
            border_style=color,
        ))
    
    def _print_metrics(self, scores: dict[str, dict]) -> None:
        """打印详细指标"""
        self.console.print()
        self.console.print("[bold]◆ 检查项详情[/bold]")
        self.console.print()
        
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("检查项", style="cyan", width=20)
        table.add_column("分数", justify="right", width=12)
        table.add_column("进度", width=25)
        table.add_column("状态", width=20)
        
        for key in ["links", "code_blocks", "env_vars", "sys_deps", "commands", "metadata"]:
            if key not in scores:
                continue
            
            data = scores[key]
            score = data["score"]
            
            # 进度条
            bar_width = 20
            filled = int(score / 100 * bar_width)
            
            if score >= 80:
                bar_color = "green"
                status_icon = "✓✓"
            elif score >= 60:
                bar_color = "cyan"
                status_icon = "✓"
            elif score >= 40:
                bar_color = "yellow"
                status_icon = "○"
            else:
                bar_color = "red"
                status_icon = "⚠"
            
            bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * (bar_width - filled)}[/dim]"
            
            # 状态描述
            if data["errors"] > 0:
                status = f"[red]{data['errors']} 错误[/red]"
            elif data["warnings"] > 0:
                status = f"[yellow]{data['warnings']} 警告[/yellow]"
            else:
                status = "[green]通过[/green]"
            
            table.add_row(
                f"{data['icon']} {data['label']}",
                f"[bold]{score:.0f}[/bold] 分",
                bar,
                f"{status_icon} {status}",
            )
        
        self.console.print(table)
    
    def _print_issues_ranking(self, issues: list[Issue]) -> None:
        """打印问题排名"""
        self.console.print()
        self.console.print("[bold]◆ 问题详情[/bold]")
        self.console.print()
        
        # 按严重程度排序
        sorted_issues = sorted(
            issues,
            key=lambda x: (0 if x.severity == "error" else 1, x.file_path, x.line_number or 0)
        )
        
        for i, issue in enumerate(sorted_issues[:10], 1):  # 最多显示10个
            if issue.severity == "error":
                icon = "❌"
                style = "red"
            else:
                icon = "⚠️"
                style = "yellow"
            
            location = f"{issue.file_path}"
            if issue.line_number:
                location += f":{issue.line_number}"
            
            self.console.print(f"  {i}. [{style}]{icon} {issue.message}[/{style}]")
            self.console.print(f"     [dim]{location}[/dim]")
            if issue.suggestion:
                self.console.print(f"     [dim]→ {issue.suggestion}[/dim]")
            self.console.print()
        
        if len(issues) > 10:
            self.console.print(f"  [dim]... 还有 {len(issues) - 10} 个问题未显示[/dim]")
    
    def _print_conclusion(self, score: float, rating: tuple, result: ValidationResult) -> None:
        """打印总结"""
        title, desc, color = rating
        error_count = result.stats.get("errors", 0)
        warning_count = result.stats.get("warnings", 0)
        
        self.console.print()
        self.console.print("[bold]◆ 总结[/bold]")
        self.console.print()
        
        if error_count == 0 and warning_count == 0:
            self.console.print(Panel(
                f"[bold green]{title}[/bold green]\n"
                f"[dim]{desc}[/dim]\n\n"
                "[green]👍 完美！文档与代码完全一致，你是文档界的卷王！[/green]",
                border_style="green",
            ))
        else:
            tips = self._get_improvement_tips(score, result)
            self.console.print(Panel(
                f"[bold {color}]{title}[/bold {color}]\n"
                f"[dim]{desc}[/dim]\n\n"
                f"发现 [red]{error_count}[/red] 个错误，[yellow]{warning_count}[/yellow] 个警告\n\n"
                f"[dim]改进建议：{tips}[/dim]",
                border_style=color,
            ))
        
        self.console.print()
    
    def _get_improvement_tips(self, score: float, result: ValidationResult) -> str:
        """根据问题生成改进建议"""
        tips = []
        
        # 统计问题类型
        code_counts: dict[str, int] = {}
        for issue in result.issues:
            code_counts[issue.code] = code_counts.get(issue.code, 0) + 1
        
        if code_counts.get("MISSING_ENV_VAR", 0) > 0:
            tips.append("在 README 或 .env.example 中记录环境变量")
        if code_counts.get("DEAD_LINK", 0) > 0 or code_counts.get("INVALID_ANCHOR", 0) > 0:
            tips.append("修复失效的链接和锚点")
        if code_counts.get("INVALID_COMMAND", 0) > 0:
            tips.append("确保 README 中的命令真正可用")
        if code_counts.get("MISSING_SYS_DEP", 0) > 0:
            tips.append("记录系统依赖的安装方法")
        
        return "；".join(tips) if tips else "继续保持！"
