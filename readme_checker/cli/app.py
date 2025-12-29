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
8. [V4] 动态命令验证（可选）
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from readme_checker.repo.loader import load_repository, cleanup_repository, CloneConfig
from readme_checker.repo.resolver import resolve_analysis_context
from readme_checker.parsing.markdown import parse_readme
from readme_checker.parsing.extractor import extract_claims
from readme_checker.verification.verifier import verify_all
from readme_checker.verification.analyzer import analyze_codebase, verify_hype, verify_todos
from readme_checker.repo.gitignore import parse_gitignore
from readme_checker.verification.scorer import calculate_score
from readme_checker.cli.reporter import generate_report

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
    dynamic: bool = typer.Option(
        False,
        "--dynamic",
        "-d",
        help="[V4] Enable dynamic command verification (actually run commands)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="[V4] Syntax validation only, no actual execution (requires --dynamic)",
    ),
    cmd_timeout: int = typer.Option(
        300,
        "--cmd-timeout",
        help="[V4] Command execution timeout in seconds (requires --dynamic)",
    ),
    allow_network: bool = typer.Option(
        False,
        "--allow-network",
        help="[V4] Allow network access during command execution (requires --dynamic)",
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
        
        # 9. [V4] 动态命令验证（可选）
        dynamic_report = None
        if dynamic:
            if verbose:
                console.print("[dim]Running dynamic verification...[/dim]")
            
            dynamic_report = _run_dynamic_verification(
                analysis_ctx.analysis_root,
                parsed,
                claims,
                dry_run=dry_run,
                cmd_timeout=cmd_timeout,
                allow_network=allow_network,
                verbose=verbose,
            )
            
            if dynamic_report and dynamic_report.has_failures:
                console.print(f"[yellow]Dynamic verification found {dynamic_report.failure_count} issue(s)[/yellow]")
        
        # 10. 生成报告
        generate_report(target, result, score, stats, console)
        
        # 显示动态验证结果
        if dynamic_report:
            _display_dynamic_report(dynamic_report, console, verbose)
        
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


def _run_dynamic_verification(
    repo_path: Path,
    parsed,
    claims,
    dry_run: bool = False,
    cmd_timeout: int = 300,
    allow_network: bool = False,
    verbose: bool = False,
):
    """Run dynamic verification on extracted commands."""
    from readme_checker.dynamic import (
        DynamicVerifier,
        DynamicVerificationConfig,
        FullVerificationReport,
        DynamicVerificationReport,
        IntentClassificationReport,
        BuildArtifactReport,
    )
    from readme_checker.nlp import NLPIntentClassifier, IntentType
    from readme_checker.build.config_parser import parse_all_configs
    from readme_checker.parsing.commands import extract_commands
    
    # Initialize components
    config = DynamicVerificationConfig(
        timeout=cmd_timeout,
        dry_run=dry_run,
        allow_network=allow_network,
    )
    verifier = DynamicVerifier(config)
    classifier = NLPIntentClassifier()
    
    report = FullVerificationReport()
    
    # 1. Parse build configs
    build_configs = parse_all_configs(repo_path)
    for cfg in build_configs:
        report.artifact_results.append(BuildArtifactReport.from_parsed_config(cfg))
    
    # 2. Extract and classify commands from code blocks
    for block in parsed.code_blocks:
        commands = extract_commands(block.content, block.language or "bash")
        
        for cmd in commands:
            # Get surrounding text for context
            context = block.content
            
            # Classify intent
            classified = classifier.classify(context, cmd.raw_text)
            report.intent_results.append(
                IntentClassificationReport.from_classified_command(classified)
            )
            
            # Only verify REQUIRED commands (skip OPTIONAL, DEPRECATED, etc.)
            if classified.intent == IntentType.REQUIRED:
                if verbose:
                    console.print(f"[dim]  Verifying: {cmd.raw_text[:50]}...[/dim]")
                
                result = verifier.verify_command(cmd.raw_text, repo_path)
                report.dynamic_results.append(
                    DynamicVerificationReport.from_execution_result(result)
                )
    
    return report


def _display_dynamic_report(report, console: Console, verbose: bool = False):
    """Display dynamic verification report."""
    from readme_checker.dynamic import FailureCategory
    
    console.print()
    console.print("[bold]Dynamic Verification Results[/bold]")
    console.print()
    
    # Show failures
    failures = [r for r in report.dynamic_results if r.category != FailureCategory.NONE]
    if failures:
        table = Table(title="Command Execution Results")
        table.add_column("Command", style="cyan", max_width=40)
        table.add_column("Status", style="red")
        table.add_column("Exit Code")
        table.add_column("Duration")
        
        for f in failures:
            status_style = {
                FailureCategory.DYNAMIC_FAILURE: "red",
                FailureCategory.TIMEOUT_FAILURE: "yellow",
                FailureCategory.SECURITY_BLOCKED: "magenta",
                FailureCategory.NETWORK_FAILURE: "blue",
            }.get(f.category, "red")
            
            table.add_row(
                f.command[:40] + "..." if len(f.command) > 40 else f.command,
                f"[{status_style}]{f.category.value}[/{status_style}]",
                str(f.exit_code) if f.exit_code is not None else "-",
                f"{f.duration_ms}ms",
            )
        
        console.print(table)
        
        # Show stderr for failures if verbose
        if verbose:
            for f in failures:
                if f.stderr:
                    console.print(f"\n[dim]stderr for '{f.command[:30]}...':[/dim]")
                    console.print(f"[red]{f.stderr[:500]}[/red]")
    else:
        console.print("[green]✓ All commands executed successfully[/green]")
    
    # Show commands needing review
    needs_review = [r for r in report.intent_results if r.needs_review]
    if needs_review:
        console.print()
        console.print(f"[yellow]⚠ {len(needs_review)} command(s) need manual review (low confidence)[/yellow]")
        if verbose:
            for r in needs_review:
                console.print(f"  [dim]- {r.command} (confidence: {r.confidence:.2f})[/dim]")
    
    # Show build artifact detection
    if report.artifact_results and verbose:
        console.print()
        console.print("[bold]Build Artifact Detection[/bold]")
        for a in report.artifact_results:
            source = "default" if a.is_default else "config"
            console.print(f"  [dim]{a.config_file}: {', '.join(a.output_paths)} ({source})[/dim]")
