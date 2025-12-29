"""
CLI 入口模块 - 使用 Typer 构建命令行界面

完整的检查流程：
1. 加载仓库（本地或 GitHub）
2. 解析 README
3. 提取声明
4. 验证声明
5. 分析代码（LOC、TODO）
6. 计算评分
7. 生成报告
"""

from typing import Optional

import typer
from rich.console import Console

from readme_checker.repo import load_repository, cleanup_repository, CloneConfig
from readme_checker.resolver import resolve_analysis_context
from readme_checker.parser import parse_readme
from readme_checker.extractor import extract_claims
from readme_checker.verifier import verify_all
from readme_checker.analyzer import analyze_codebase, verify_hype, verify_todos
from readme_checker.gitignore import parse_gitignore
from readme_checker.scorer import calculate_score
from readme_checker.reporter import generate_report

# 创建 Typer 应用实例
app = typer.Typer(
    name="checker",
    help="README-Checker: Stop lies. Verify your docs. 🔍",
    add_completion=False,
)

# Rich Console 用于输出
console = Console()


@app.command()
def check(
    target: str = typer.Argument(
        ...,
        help="Path to local project or GitHub URL to check",
    ),
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Subdirectory to use as analysis root (for Monorepo support)",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        "-t",
        help="Clone timeout in seconds (for GitHub URLs)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Check a project's README for truthfulness.
    
    Examples:
        checker check ./my-project
        checker check https://github.com/user/repo
        checker check ./monorepo --root packages/frontend
        checker check https://github.com/user/repo --timeout 120
    """
    ctx = None
    
    try:
        # 1. 加载仓库
        if verbose:
            console.print(f"[dim]Loading repository: {target}[/dim]")
        
        # 配置克隆选项
        clone_config = CloneConfig(timeout=timeout)
        
        try:
            ctx = load_repository(target, clone_config)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        
        # 2. 解析分析上下文（支持 --root 选项）
        try:
            analysis_ctx = resolve_analysis_context(ctx.path, root)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        
        if verbose and root:
            console.print(f"[dim]Using analysis root: {analysis_ctx.analysis_root}[/dim]")
        
        # 检查是否找到 README
        if not analysis_ctx.readme_content:
            console.print("[yellow]Warning:[/yellow] No README.md found in repository")
            console.print("[dim]Nothing to check. Exiting.[/dim]")
            raise typer.Exit(0)
        
        if verbose:
            console.print(f"[dim]Found README: {analysis_ctx.readme_path}[/dim]")
        
        # 3. 解析 README
        if verbose:
            console.print("[dim]Parsing README...[/dim]")
        
        parsed = parse_readme(analysis_ctx.readme_content)
        
        if verbose:
            console.print(f"[dim]  - {len(parsed.code_blocks)} code blocks[/dim]")
            console.print(f"[dim]  - {len(parsed.links)} links/images[/dim]")
        
        # 4. 提取声明
        if verbose:
            console.print("[dim]Extracting claims...[/dim]")
        
        claims = extract_claims(parsed)
        
        if verbose:
            console.print(f"[dim]  - {len(claims.ecosystem_claims)} ecosystem claims[/dim]")
            console.print(f"[dim]  - {len(claims.path_claims)} path claims[/dim]")
            console.print(f"[dim]  - {len(claims.module_claims)} module claims[/dim]")
            console.print(f"[dim]  - {len(claims.hype_claims)} hype words[/dim]")
        
        # 5. 验证声明（使用 analysis_root）
        if verbose:
            console.print("[dim]Verifying claims...[/dim]")
        
        result = verify_all(claims, analysis_ctx.analysis_root)
        
        # 6. 分析代码（使用 gitignore）
        if verbose:
            console.print("[dim]Analyzing codebase...[/dim]")
        
        gitignore_rules = parse_gitignore(analysis_ctx.analysis_root)
        stats = analyze_codebase(analysis_ctx.analysis_root, gitignore_rules)
        
        if verbose:
            console.print(f"[dim]  - {stats.total_loc} lines of code[/dim]")
            console.print(f"[dim]  - {stats.todo_count} TODOs[/dim]")
        
        # 7. 夸大和 TODO 验证
        hype_violations = verify_hype(claims, stats)
        todo_violations = verify_todos(claims, stats)
        result.violations.extend(hype_violations)
        result.violations.extend(todo_violations)
        
        # 更新统计
        result.stats["loc"] = stats.total_loc
        result.stats["todo_count"] = stats.todo_count
        
        # 8. 计算评分
        score = calculate_score(result)
        
        # 9. 生成报告
        generate_report(target, result, score, stats, console)
        
        # 根据评分设置退出码
        if score.rating == "liar":
            raise typer.Exit(2)
        elif score.rating == "suspicious":
            raise typer.Exit(1)
        else:
            raise typer.Exit(0)
    
    finally:
        # 清理临时仓库
        if ctx:
            cleanup_repository(ctx)


@app.command()
def version() -> None:
    """Show the version of README-Checker."""
    from readme_checker import __version__
    console.print(f"[bold]README-Checker[/bold] v{__version__}")
    console.print("[dim]Stop lies. Verify your docs. 🔍[/dim]")


if __name__ == "__main__":
    app()
