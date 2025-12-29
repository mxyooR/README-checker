"""Go ecosystem plugin.

Detects and verifies Go projects.
"""

from pathlib import Path

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    VerificationResult,
    PluginRegistry,
)


class GoPlugin(EcosystemPlugin):
    """Plugin for Go ecosystem."""
    
    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="go",
            config_files=["go.mod", "go.sum"],
            package_manager="go",
            common_commands=[
                "go build",
                "go run",
                "go test",
                "go mod",
                "go get",
                "go install",
            ],
        )
    
    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a Go project."""
        return (repo_path / "go.mod").exists()
    
    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify Go commands."""
        cmd_lower = command.lower().strip()
        
        if not cmd_lower.startswith("go "):
            return None
        
        parts = command.strip().split()
        if len(parts) < 2:
            return None
        
        subcommand = parts[1]
        
        # go run <file.go> or go run .
        if subcommand == "run" and len(parts) >= 3:
            target = parts[2]
            if target == ".":
                # Check for main.go or any .go file
                if list(repo_path.glob("*.go")):
                    return VerificationResult(
                        claim=command,
                        status="verified",
                        message="Go files found in current directory",
                        severity="info",
                    )
            elif target.endswith(".go"):
                if (repo_path / target).exists():
                    return VerificationResult(
                        claim=command,
                        status="verified",
                        message=f"Go file '{target}' found",
                        severity="info",
                    )
                return VerificationResult(
                    claim=command,
                    status="missing",
                    message=f"Go file '{target}' not found",
                    severity="warning",
                )
        
        # go build, go test, go mod - generally valid if go.mod exists
        if subcommand in ("build", "test", "mod", "get", "install", "fmt", "vet"):
            if (repo_path / "go.mod").exists():
                return VerificationResult(
                    claim=command,
                    status="verified",
                    message=f"go {subcommand} command (go.mod exists)",
                    severity="info",
                )
            return VerificationResult(
                claim=command,
                status="missing",
                message="go.mod not found",
                severity="warning",
            )
        
        return None
    
    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for Go project."""
        return ["go.mod"]


# Auto-register plugin
PluginRegistry.register(GoPlugin())
