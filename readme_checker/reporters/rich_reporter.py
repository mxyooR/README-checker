"""
Rich Terminal Reporter - Colorful terminal output using Rich library

Style: Code quality analysis tool with scores, ratings, progress bars and fun comments
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from readme_checker.core.validator import ValidationResult, Issue


# Rating system
RATINGS = [
    (90, "🏆 Doc Master", "Perfect! Your docs are more reliable than your code", "green"),
    (80, "⭐ Excellent", "Great job! Just a tiny bit away from perfection", "green"),
    (70, "✅ Good", "Not bad, but there's room for improvement", "cyan"),
    (60, "📝 Passable", "Barely usable, consider fixing when you have time", "yellow"),
    (40, "⚠️ Problematic", "Some issues here, users might complain", "yellow"),
    (20, "❌ Poor", "Many problems, fix them ASAP", "red"),
    (0, "💀 Disaster", "Is this documentation a joke?", "red"),
]

# Check weights
WEIGHTS = {
    "links": 0.20,        # Link validation
    "code_blocks": 0.10,  # Code block validation
    "env_vars": 0.25,     # Environment variables
    "sys_deps": 0.15,     # System dependencies
    "commands": 0.15,     # Command verification
    "metadata": 0.15,     # Metadata consistency
}


class RichReporter:
    """Rich Terminal Reporter - with scores and ratings"""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def report(self, result: ValidationResult, target: str) -> None:
        """Generate Rich format report"""
        # Calculate scores
        scores = self._calculate_scores(result)
        total_score = self._calculate_total_score(scores)
        rating = self._get_rating(total_score)
        
        # Print separator
        self.console.print()
        self.console.print("─" * 80, style="dim")
        self.console.print(
            "📋 README-Checker Documentation Quality Report 📋",
            style="bold cyan",
            justify="center"
        )
        self.console.print("─" * 80, style="dim")
        
        # Score and rating
        self._print_score_panel(total_score, rating, target)
        
        # Detailed metrics
        self._print_metrics(scores)
        
        # Issue details
        if result.issues:
            self._print_issues_ranking(result.issues)
        
        # Conclusion
        self._print_conclusion(total_score, rating, result)
    
    def _calculate_scores(self, result: ValidationResult) -> dict[str, dict]:
        """Calculate scores for each check"""
        # Group issues by code
        code_counts: dict[str, dict[str, int]] = {}
        for issue in result.issues:
            if issue.code not in code_counts:
                code_counts[issue.code] = {"errors": 0, "warnings": 0}
            if issue.severity == "error":
                code_counts[issue.code]["errors"] += 1
            else:
                code_counts[issue.code]["warnings"] += 1
        
        scores = {}
        
        # Link check (each error -20, warning -5)
        link_errors = code_counts.get("DEAD_LINK", {}).get("errors", 0)
        link_errors += code_counts.get("INVALID_ANCHOR", {}).get("errors", 0)
        link_warnings = code_counts.get("ABSOLUTE_URL", {}).get("warnings", 0)
        link_score = max(0, 100 - link_errors * 20 - link_warnings * 5)
        scores["links"] = {
            "score": link_score,
            "errors": link_errors,
            "warnings": link_warnings,
            "label": "Links",
            "icon": "🔗",
        }
        
        # Code block check
        block_errors = code_counts.get("INVALID_JSON", {}).get("errors", 0)
        block_errors += code_counts.get("INVALID_YAML", {}).get("errors", 0)
        block_warnings = code_counts.get("MISSING_LANG_TAG", {}).get("warnings", 0)
        block_score = max(0, 100 - block_errors * 15 - block_warnings * 5)
        scores["code_blocks"] = {
            "score": block_score,
            "errors": block_errors,
            "warnings": block_warnings,
            "label": "Code Blocks",
            "icon": "📝",
        }
        
        # Environment variable check (each undocumented -15)
        env_errors = code_counts.get("MISSING_ENV_VAR", {}).get("errors", 0)
        env_score = max(0, 100 - env_errors * 15)
        scores["env_vars"] = {
            "score": env_score,
            "errors": env_errors,
            "warnings": 0,
            "label": "Env Vars",
            "icon": "🔐",
        }
        
        # System dependency check
        dep_warnings = code_counts.get("MISSING_SYS_DEP", {}).get("warnings", 0)
        dep_score = max(0, 100 - dep_warnings * 10)
        scores["sys_deps"] = {
            "score": dep_score,
            "errors": 0,
            "warnings": dep_warnings,
            "label": "System Deps",
            "icon": "🔧",
        }
        
        # Command verification
        cmd_warnings = code_counts.get("INVALID_COMMAND", {}).get("warnings", 0)
        cmd_score = max(0, 100 - cmd_warnings * 15)
        scores["commands"] = {
            "score": cmd_score,
            "errors": 0,
            "warnings": cmd_warnings,
            "label": "Commands",
            "icon": "💻",
        }
        
        # Metadata check
        meta_warnings = code_counts.get("VERSION_MISMATCH", {}).get("warnings", 0)
        meta_warnings += code_counts.get("LICENSE_MISMATCH", {}).get("warnings", 0)
        meta_score = max(0, 100 - meta_warnings * 20)
        scores["metadata"] = {
            "score": meta_score,
            "errors": 0,
            "warnings": meta_warnings,
            "label": "Metadata",
            "icon": "📊",
        }
        
        return scores
    
    def _calculate_total_score(self, scores: dict[str, dict]) -> float:
        """Calculate weighted total score"""
        total = 0.0
        for key, weight in WEIGHTS.items():
            if key in scores:
                total += scores[key]["score"] * weight
        return round(total, 2)
    
    def _get_rating(self, score: float) -> tuple[str, str, str]:
        """Get rating based on score"""
        for threshold, title, desc, color in RATINGS:
            if score >= threshold:
                return title, desc, color
        return RATINGS[-1][1], RATINGS[-1][2], RATINGS[-1][3]
    
    def _print_score_panel(self, score: float, rating: tuple, target: str) -> None:
        """Print score panel"""
        title, desc, color = rating
        
        # Score progress bar
        bar_width = 30
        filled = int(score / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        content = Text()
        content.append(f"Score: ", style="bold")
        content.append(f"{score:.1f}", style=f"bold {color}")
        content.append(f" / 100\n", style="dim")
        content.append(f"[{bar}]\n\n", style=color)
        content.append(f"Rating: ", style="bold")
        content.append(f"{title}\n", style=f"bold {color}")
        content.append(f"{desc}\n\n", style="dim")
        content.append(f"Target: {target}", style="dim")
        
        self.console.print(Panel(
            content,
            title="[bold]📊 Documentation Quality Score[/bold]",
            border_style=color,
        ))
    
    def _print_metrics(self, scores: dict[str, dict]) -> None:
        """Print detailed metrics"""
        self.console.print()
        self.console.print("[bold]◆ Check Details[/bold]")
        self.console.print()
        
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Check", style="cyan", width=20)
        table.add_column("Score", justify="right", width=12)
        table.add_column("Progress", width=25)
        table.add_column("Status", width=20)
        
        for key in ["links", "code_blocks", "env_vars", "sys_deps", "commands", "metadata"]:
            if key not in scores:
                continue
            
            data = scores[key]
            score = data["score"]
            
            # Progress bar
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
            
            # Status description
            if data["errors"] > 0:
                status = f"[red]{data['errors']} error(s)[/red]"
            elif data["warnings"] > 0:
                status = f"[yellow]{data['warnings']} warning(s)[/yellow]"
            else:
                status = "[green]Passed[/green]"
            
            table.add_row(
                f"{data['icon']} {data['label']}",
                f"[bold]{score:.0f}[/bold] pts",
                bar,
                f"{status_icon} {status}",
            )
        
        self.console.print(table)
    
    def _print_issues_ranking(self, issues: list[Issue]) -> None:
        """Print issues ranking"""
        self.console.print()
        self.console.print("[bold]◆ Issues Found[/bold]")
        self.console.print()
        
        # Sort by severity
        sorted_issues = sorted(
            issues,
            key=lambda x: (0 if x.severity == "error" else 1, x.file_path, x.line_number or 0)
        )
        
        for i, issue in enumerate(sorted_issues[:10], 1):  # Show max 10
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
            self.console.print(f"  [dim]... and {len(issues) - 10} more issues[/dim]")
    
    def _print_conclusion(self, score: float, rating: tuple, result: ValidationResult) -> None:
        """Print conclusion"""
        title, desc, color = rating
        error_count = result.stats.get("errors", 0)
        warning_count = result.stats.get("warnings", 0)
        
        self.console.print()
        self.console.print("[bold]◆ Summary[/bold]")
        self.console.print()
        
        if error_count == 0 and warning_count == 0:
            self.console.print(Panel(
                f"[bold green]{title}[/bold green]\n"
                f"[dim]{desc}[/dim]\n\n"
                "[green]👍 Perfect! Documentation is fully consistent with codebase![/green]",
                border_style="green",
            ))
        else:
            tips = self._get_improvement_tips(score, result)
            self.console.print(Panel(
                f"[bold {color}]{title}[/bold {color}]\n"
                f"[dim]{desc}[/dim]\n\n"
                f"Found [red]{error_count}[/red] error(s), [yellow]{warning_count}[/yellow] warning(s)\n\n"
                f"[dim]Tips: {tips}[/dim]",
                border_style=color,
            ))
        
        self.console.print()
    
    def _get_improvement_tips(self, score: float, result: ValidationResult) -> str:
        """Generate improvement tips based on issues"""
        tips = []
        
        # Count issue types
        code_counts: dict[str, int] = {}
        for issue in result.issues:
            code_counts[issue.code] = code_counts.get(issue.code, 0) + 1
        
        if code_counts.get("MISSING_ENV_VAR", 0) > 0:
            tips.append("Document env vars in README or .env.example")
        if code_counts.get("DEAD_LINK", 0) > 0 or code_counts.get("INVALID_ANCHOR", 0) > 0:
            tips.append("Fix broken links and anchors")
        if code_counts.get("INVALID_COMMAND", 0) > 0:
            tips.append("Ensure README commands actually work")
        if code_counts.get("MISSING_SYS_DEP", 0) > 0:
            tips.append("Document system dependency installation")
        
        return "; ".join(tips) if tips else "Keep up the good work!"
