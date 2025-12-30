"""
CLI 入口模块 - 使用 Typer 构建命令行界面

静态文档审计工具的检查流程：
1. 解析 README
2. 扫描代码库
3. 执行验证
4. 生成报告
"""

import re
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
from readme_checker.core.validator import Issue
from readme_checker.plugins.python import PythonPlugin
from readme_checker.plugins.nodejs import NodeJsPlugin
from readme_checker.plugins.golang import GoPlugin
from readme_checker.plugins.java import JavaPlugin
from readme_checker.plugins.cpp import CppPlugin
from readme_checker.plugins.rust import RustPlugin
from readme_checker.reporters import RichReporter, JsonReporter

# 创建 Typer 应用实例
app = typer.Typer(
    name="checker",
    help="README-Checker: Static documentation linter for CI/CD.",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},  # 支持 -h
)

# Rich Console 用于输出（legacy_windows=False 支持 emoji）
console = Console(legacy_windows=False)


def detect_project_type(repo_path: Path) -> str | None:
    """检测项目类型"""
    if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
        return "python"
    if (repo_path / "package.json").exists():
        return "nodejs"
    if (repo_path / "go.mod").exists():
        return "go"
    if (repo_path / "Cargo.toml").exists():
        return "rust"
    if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
        return "java"
    if (repo_path / "CMakeLists.txt").exists() or (repo_path / "Makefile").exists() or (repo_path / "meson.build").exists():
        return "cpp"
    return None


def get_plugin(project_type: str | None):
    """获取对应的插件"""
    if project_type == "python":
        return PythonPlugin()
    if project_type == "nodejs":
        return NodeJsPlugin()
    if project_type == "go":
        return GoPlugin()
    if project_type == "java":
        return JavaPlugin()
    if project_type == "rust":
        return RustPlugin()
    if project_type == "cpp":
        return CppPlugin()
    return None


def find_readme(repo_path: Path) -> Path | None:
    """查找 README 文件"""
    candidates = ["README.md", "readme.md", "README.MD", "Readme.md"]
    for name in candidates:
        readme_path = repo_path / name
        if readme_path.exists():
            return readme_path
    return None


def extract_commands_from_readme(content: str) -> list[tuple[str, int]]:
    """
    从 README 中提取命令
    
    提取代码块中的 shell 命令（bash, sh, shell, console, terminal）
    
    Returns:
        [(command, line_number), ...]
    """
    commands: list[tuple[str, int]] = []
    
    # 匹配代码块
    code_block_pattern = re.compile(
        r'^```(bash|sh|shell|console|terminal|zsh)?\s*\n(.*?)^```',
        re.MULTILINE | re.DOTALL
    )
    
    lines = content.split('\n')
    current_pos = 0
    
    for match in code_block_pattern.finditer(content):
        block_content = match.group(2)
        # 计算行号
        line_num = content[:match.start()].count('\n') + 2
        
        for i, line in enumerate(block_content.split('\n')):
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            # 移除 $ 或 > 提示符
            if line.startswith('$ '):
                line = line[2:]
            elif line.startswith('> '):
                line = line[2:]
            
            # 只提取看起来像命令的行
            if any(line.startswith(cmd) for cmd in [
                'npm ', 'yarn ', 'pnpm ', 'npx ',
                'python ', 'python3 ', 'pip ', 'poetry ', 'pipenv ',
                'go ', 'cargo ', 'rustc ', 'rustup ',  # Go & Rust
                'make ', 'cmake ', 'ninja ', 'meson ',  # C/C++
                'gcc ', 'g++ ', 'clang ', 'clang++ ',  # Compilers
                'docker ', 'kubectl ',
                'mvn ', './mvnw ', 'gradle ', './gradlew ',  # Java
            ]):
                commands.append((line, line_num + i))
    
    return commands


def validate_commands(
    commands: list[tuple[str, int]],
    plugin,
    repo_path: Path,
    readme_path: str,
) -> list[Issue]:
    """
    验证 README 中的命令是否有效
    
    使用 plugin.verify_command() 检查命令
    """
    issues: list[Issue] = []
    
    if not plugin:
        return issues
    
    for cmd, line_num in commands:
        result = plugin.verify_command(cmd, repo_path)
        if result and result.status == "missing":
            issues.append(Issue(
                severity="warning",
                code="INVALID_COMMAND",
                message=f"Command may not work: {cmd}",
                file_path=readme_path,
                line_number=line_num,
                suggestion=result.suggestion or result.message,
            ))
    
    return issues


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
        file_count = 0
        
        def on_file_scanned(file_path: str, language: str) -> None:
            nonlocal file_count
            file_count += 1
            console.print(f"[dim]  ({language}) {file_path}[/dim]")
        
        scan_result = scan_code_files(repo_path, on_file=on_file_scanned)
        console.print(f"[dim]  Scanned {file_count} files[/dim]")
    else:
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
    
    # 命令验证（新功能）
    commands = extract_commands_from_readme(readme_content)
    if verbose and commands:
        console.print(f"[dim]  - {len(commands)} commands found in README[/dim]")
    cmd_issues = validate_commands(
        commands, plugin, repo_path, str(readme_path.relative_to(repo_path))
    )
    result.issues.extend(cmd_issues)

    
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
    result.stats["commands_found"] = len(commands)
    
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


def _version_callback(value: bool) -> None:
    """版本号回调函数"""
    if value:
        from readme_checker import __version__
        console.print(f"[bold]README-Checker[/bold] v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """
    README-Checker: Static documentation linter for CI/CD.
    
    Run 'checker check' to check current directory, or 'checker -h' for help.
    """
    # 如果没有子命令，默认运行 check（使用 ctx.invoke 正确传递参数）
    if ctx.invoked_subcommand is None:
        ctx.invoke(check, target=".", verbose=False, format="rich", repo_url=None)


if __name__ == "__main__":
    app()
