"""
CLI 入口模块 - 使用 Typer 构建命令行界面
"""

import typer

# 创建 Typer 应用实例
app = typer.Typer(
    name="checker",
    help="README-Checker: Stop lies. Verify your docs.",
    add_completion=False,
)


@app.command()
def check(
    target: str = typer.Argument(
        ...,
        help="Path to local project or GitHub URL to check",
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
    """
    # TODO: 实现完整的检查流程
    typer.echo(f"🔍 Checking: {target}")
    typer.echo("⚠️  Not implemented yet - coming soon!")


@app.command()
def version() -> None:
    """Show the version of README-Checker."""
    from readme_checker import __version__
    typer.echo(f"README-Checker v{__version__}")


if __name__ == "__main__":
    app()
