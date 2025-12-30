"""
CLI 入口模块 - 使用 Typer 构建命令行界面

静态文档审计工具的检查流程：
1. 解析 README
2. 扫描代码库
3. 执行验证
4. 生成报告
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from readme_checker.core import (
    parse_markdown,
    scan_code_files,
    Validator,
    ValidationResult,
)
from readme_checker.plugins.python import PythonPlugin
from readme_checker.plugins.nodejs import NodeJsPlugin
from readme_checker.reporters import RichReporter, JsonReporter

# 创建 Typer 应用实例
app = typer.Typer(
    name="checker",
    help="README-Checker: Static documentation linter for CI/CD. 🔍",
    add_completion=False,
)

# Rich Console 用于输出
console = Console()


def detect_project_type(repo_path: Path) -> str | None:
    """检测项目类型"""
    if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
        return "python"
    if (repo_path / "package.json").exists():
        return "nodejs"
    if (repo_path / "go.mod").exists():
        return "go"
    if (repo_path / "pom.xml").exists():
        return "java"
    return None


def get_plugin(project_type: str | None):
    """获取对应的插件"""
    if project_type == "python":
        return PythonPlugin()
    if project_type == "nodejs":
        return NodeJsPlugin()
    return None


def find_readme(repo_path: Path) -> Path | None:
    """查找 README 文件"""
    candidates = ["README.md", "readme.md", "README.MD", "Readme.md"]
    for name in candidates:
        readme_path = repo_path / name
        if readme_path.exists():
            return readme_path
    return None


@app.command()
def check(
    target: str = typer.Argument(
        ".",
        help="Path to local project to check",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: rich (default) or json",
    ),
    repo_url: Optional[str] = typer.Option(
        None,
        "--repo-url",
        help="Repository URL pattern for absolute URL detection",
    ),
) -> None:
    """
    Check a project's README for consistency with codebase.
    
    Examples:
        checker check
        checker check ./my-project
        checker check --format json
        checker check -v --repo-url "github.com/user/repo"
    """
    repo_path = Path(target).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {target}")
        raise typer.Exit(1)
    
    if not repo_path.is_dir():
        console.print(f"[red]Error:[/red] Path is not a directory: {target}")
        raise typer.Exit(1)
    
    # 1. 查找 README
    readme_path = find_readme(repo_path)
    if not readme_path:
        console.print("[yellow]Warning:[/yellow] No README.md found")
        raise typer.Exit(0)
    
    if verbose:
        console.print(f"[dim]Found README: {readme_path.relative_to(repo_path)}[/dim]")
    
    # 2. 读取并解析 README
    try:
        readme_content = readme_path.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read README: {e}")
        raise typer.Exit(1)
    
    if verbose:
        console.print("[dim]Parsing README...[/dim]")
    
    parsed = parse_markdown(readme_content)
    
    if verbose:
        console.print(f"[dim]  - {len(parsed.links)} links[/dim]")
        console.print(f"[dim]  - {len(parsed.headers)} headers[/dim]")
        console.print(f"[dim]  - {len(parsed.code_blocks)} code blocks[/dim]")
    
    # 3. 扫描代码库
    if verbose:
        console.print("[dim]Scanning codebase...[/dim]")
    
    scan_result = scan_code_files(repo_path)
    
    if verbose:
        console.print(f"[dim]  - {len(scan_result.env_vars)} env var usages[/dim]")
        console.print(f"[dim]  - {len(scan_result.system_deps)} system deps[/dim]")
    
    # 4. 检测项目类型并提取元数据
    project_type = detect_project_type(repo_path)
    plugin = get_plugin(project_type)
    metadata = None
    
    if plugin:
        if verbose:
            console.print(f"[dim]Detected project type: {project_type}[/dim]")
        metadata = plugin.extract_metadata(repo_path)
    
    # 5. 执行验证
    if verbose:
        console.print("[dim]Running validations...[/dim]")
    
    validator = Validator(repo_path, repo_url_pattern=repo_url)
    
    # 基础验证
    result = validator.validate_all(parsed, str(readme_path.relative_to(repo_path)))
    
    # 环境变量验证
    env_example_path = repo_path / ".env.example"
    env_issues = validator.validate_env_vars(
        scan_result.env_vars,
        readme_content,
        env_example_path if env_example_path.exists() else None,
    )
    result.issues.extend(env_issues)
    
    # 系统依赖验证
    dep_issues = validator.validate_system_deps(
        scan_result.system_deps,
        readme_content,
    )
    result.issues.extend(dep_issues)
    
    # 元数据验证
    if metadata:
        version_issues = validator.validate_version(
            readme_content,
            metadata.version,
        )
        result.issues.extend(version_issues)
        
        license_file = repo_path / "LICENSE"
        license_content = None
        if license_file.exists():
            try:
                license_content = license_file.read_text(encoding="utf-8")
            except Exception:
                pass
        
        license_issues = validator.validate_license(
            readme_content,
            metadata.license,
            license_content,
        )
        result.issues.extend(license_issues)
    
    # 更新统计
    result.stats["total_issues"] = len(result.issues)
    result.stats["errors"] = sum(1 for i in result.issues if i.severity == "error")
    result.stats["warnings"] = sum(1 for i in result.issues if i.severity == "warning")
    result.stats["env_vars_found"] = len(scan_result.env_vars)
    result.stats["system_deps_found"] = len(scan_result.system_deps)
    
    # 6. 生成报告
    if format == "json":
        reporter = JsonReporter()
    else:
        reporter = RichReporter(console)
    
    reporter.report(result, target)
    
    # 7. 设置退出码
    if result.stats["errors"] > 0:
        raise typer.Exit(1)
    else:
        raise typer.Exit(0)


@app.command()
def version() -> None:
    """Show the version of README-Checker."""
    from readme_checker import __version__
    console.print(f"[bold]README-Checker[/bold] v{__version__}")
    console.print("[dim]Static documentation linter for CI/CD. 🔍[/dim]")


if __name__ == "__main__":
    app()
