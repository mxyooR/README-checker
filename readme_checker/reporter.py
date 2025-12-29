"""
报告生成器模块 - 生成漂亮的终端报告

使用 Rich 库输出彩色表格、进度条和状态图标。
报错信息要皮一点！
"""

import random
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from readme_checker.verifier import VerificationResult, Violation
from readme_checker.scorer import ScoreBreakdown
from readme_checker.analyzer import CodeStats


# ============================================================
# 配置常量 - 皮一点的消息模板
# ============================================================

PLAYFUL_MESSAGES: dict[str, list[str]] = {
    "ecosystem": [
        "Uh-oh! README promises '{keyword}', but {file} is playing hide and seek.",
        "Plot twist: {file} exists only in the README's imagination.",
        "The README said there'd be {file}. The README lied. 🤥",
        "'{keyword}' mentioned, but {file}? Nowhere to be found!",
    ],
    "path": [
        "This link leads to... nowhere. It's a portal to the void. 🕳️",
        "404: {path} not found. Also not found: attention to detail.",
        "The file {path} ghosted us. No goodbye, nothing. 👻",
        "{path} is missing! Did it run away from home?",
    ],
    "command": [
        "README says run '{command}', but the script doesn't exist. Awkward. 😬",
        "'{command}' - a command that leads to disappointment.",
        "This tutorial is fiction. {path} is not a real file.",
        "Phantom command detected! {path} is imaginary.",
    ],
    "hype": [
        "Claims to be '{words}' with {loc} lines of code? Sure, Jan. 💅",
        "Big words, tiny codebase. This project talks the talk but barely walks.",
        "'{words}' - that's a lot of confidence for {loc} LOC.",
        "Over-hyped alert! 🚨 {loc} lines ≠ '{words}'",
    ],
    "todo": [
        "Says '{claims}' but has {count} TODOs. That's not how completion works. 🙄",
        "'{claims}' with {count} TODOs? More like 'Production Maybe'.",
        "Half-baked alert! {count} TODOs hiding behind '{claims}'.",
        "TODO count: {count}. Completeness claim: '{claims}'. Math doesn't check out.",
    ],
}

# 最终评价消息
VERDICT_MESSAGES: dict[str, list[str]] = {
    "trustworthy": [
        "This README is honest! A rare find. 🌟",
        "Documentation matches reality. Respect! 👏",
        "What you see is what you get. Trustworthy! ✅",
    ],
    "suspicious": [
        "Hmm... something's off here. Proceed with caution. 🤔",
        "This README has some explaining to do...",
        "Not terrible, but not great either. Trust issues detected.",
    ],
    "liar": [
        "🚨 LIAR DETECTED! This README is fiction.",
        "This project might be abandoned or fake. 💀",
        "The README and reality had a messy breakup.",
        "Trust Score: Yikes. 💩",
    ],
}


# ============================================================
# 消息格式化函数
# ============================================================

def _format_playful_message(violation: Violation) -> str:
    """
    为违规生成皮一点的消息
    
    Args:
        violation: 违规记录
    
    Returns:
        格式化后的消息
    """
    templates = PLAYFUL_MESSAGES.get(violation.category, [violation.message])
    template = random.choice(templates)
    
    # 根据违规类型填充模板
    details = violation.details
    
    try:
        if violation.category == "ecosystem":
            return template.format(
                keyword=details.get("keyword", "?"),
                file=" or ".join(details.get("expected_files", ["?"])),
            )
        elif violation.category == "path":
            return template.format(path=details.get("path", "?"))
        elif violation.category == "command":
            return template.format(
                command=details.get("source_text", "?")[:50],
                path=details.get("path", "?"),
            )
        elif violation.category == "hype":
            return template.format(
                words=", ".join(details.get("hype_words", ["?"])),
                loc=details.get("loc", "?"),
            )
        elif violation.category == "todo":
            return template.format(
                claims=", ".join(details.get("completeness_claims", ["?"])),
                count=details.get("todo_count", "?"),
            )
    except (KeyError, IndexError):
        pass
    
    return violation.message


def _get_status_icon(passed: bool, has_warnings: bool = False) -> str:
    """
    获取状态图标
    
    Args:
        passed: 是否通过
        has_warnings: 是否有警告
    
    Returns:
        状态图标
    """
    if passed:
        return "✅"
    elif has_warnings:
        return "⚠️"
    else:
        return "❌"


# ============================================================
# 报告生成函数
# ============================================================

def generate_report(
    target: str,
    result: VerificationResult,
    score: ScoreBreakdown,
    stats: Optional[CodeStats] = None,
    console: Optional[Console] = None,
) -> None:
    """
    生成并打印终端报告
    
    Args:
        target: 检查目标（路径或 URL）
        result: 验证结果
        score: 评分明细
        stats: 代码统计（可选）
        console: Rich Console 实例（可选，用于测试）
    """
    if console is None:
        console = Console()
    
    # 标题
    title_color = "green" if score.rating == "trustworthy" else (
        "yellow" if score.rating == "suspicious" else "red"
    )
    
    console.print()
    console.print(Panel(
        f"[bold]🔍 README-Checker Report[/bold]\n[dim]Target: {target}[/dim]",
        border_style=title_color,
    ))
    
    # 检查结果表格
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")
    
    # 生态系统检查
    eco_violations = [v for v in result.violations if v.category == "ecosystem"]
    eco_passed = len(eco_violations) == 0
    eco_detail = f"{len(eco_violations)} issues" if eco_violations else "All config files present"
    table.add_row(
        "Ecosystem",
        _get_status_icon(eco_passed),
        eco_detail,
    )
    
    # 路径检查
    path_violations = [v for v in result.violations if v.category == "path"]
    path_passed = len(path_violations) == 0
    path_detail = f"{len(path_violations)} broken links" if path_violations else "All links valid"
    table.add_row(
        "File Links",
        _get_status_icon(path_passed, has_warnings=True),
        path_detail,
    )
    
    # 命令检查
    cmd_violations = [v for v in result.violations if v.category == "command"]
    cmd_passed = len(cmd_violations) == 0
    cmd_detail = f"{len(cmd_violations)} phantom commands" if cmd_violations else "All scripts exist"
    table.add_row(
        "Commands",
        _get_status_icon(cmd_passed),
        cmd_detail,
    )
    
    # 夸大检查
    hype_violations = [v for v in result.violations if v.category == "hype"]
    hype_passed = len(hype_violations) == 0
    hype_detail = "Over-hyped!" if hype_violations else "Description matches scale"
    table.add_row(
        "Hype Check",
        _get_status_icon(hype_passed, has_warnings=True),
        hype_detail,
    )
    
    # TODO 检查
    todo_violations = [v for v in result.violations if v.category == "todo"]
    todo_passed = len(todo_violations) == 0
    todo_detail = "Too many TODOs!" if todo_violations else "Completeness OK"
    table.add_row(
        "TODO Trap",
        _get_status_icon(todo_passed, has_warnings=True),
        todo_detail,
    )
    
    console.print(table)
    
    # 违规详情
    if result.violations:
        console.print()
        console.print("[bold red]Issues Found:[/bold red]")
        for v in result.violations:
            msg = _format_playful_message(v)
            line_info = f" (line {v.line_number})" if v.line_number else ""
            console.print(f"  • {msg}{line_info}")
    
    # 代码统计
    if stats:
        console.print()
        console.print(f"[dim]📊 Code Stats: {stats.total_loc} LOC, {stats.total_files} files, {stats.todo_count} TODOs[/dim]")
    
    # 最终评分
    console.print()
    score_color = "green" if score.rating == "trustworthy" else (
        "yellow" if score.rating == "suspicious" else "red"
    )
    
    verdict = random.choice(VERDICT_MESSAGES[score.rating])
    
    console.print(Panel(
        f"[bold {score_color}]Trust Score: {score.total_score}/100[/bold {score_color}]\n"
        f"[{score_color}]{score.rating_description}[/{score_color}]\n\n"
        f"[italic]{verdict}[/italic]",
        border_style=score_color,
    ))
    console.print()
