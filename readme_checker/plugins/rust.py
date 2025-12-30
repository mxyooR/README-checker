"""Rust ecosystem plugin.

Detects and verifies Rust/Cargo projects.
"""

import re
from pathlib import Path

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    ProjectMetadata,
    VerificationResult,
    PluginRegistry,
)

# Try to import tomllib for Cargo.toml parsing
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore


class RustPlugin(EcosystemPlugin):
    """Plugin for Rust ecosystem (Cargo)."""

    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="rust",
            config_files=[
                "Cargo.toml",
                "Cargo.lock",
            ],
            package_manager="cargo",
            common_commands=[
                "cargo build",
                "cargo run",
                "cargo test",
                "cargo check",
                "cargo fmt",
                "cargo clippy",
                "cargo doc",
                "cargo publish",
                "rustc",
                "rustup",
            ],
        )

    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a Rust project."""
        return (repo_path / "Cargo.toml").exists()

    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify Rust/Cargo commands."""
        cmd_lower = command.lower().strip()
        parts = command.strip().split()

        if not parts:
            return None

        cmd = parts[0]

        # Cargo commands
        if cmd == "cargo":
            return self._verify_cargo(command, repo_path)

        # rustc commands
        if cmd == "rustc":
            return self._verify_rustc(command, repo_path)

        # rustup commands
        if cmd == "rustup":
            return VerificationResult(
                claim=command,
                status="verified",
                message="Rust toolchain management command",
                severity="info",
            )

        return None

    def _verify_cargo(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Cargo command."""
        cargo_toml = repo_path / "Cargo.toml"

        if not cargo_toml.exists():
            return VerificationResult(
                claim=command,
                status="missing",
                message="Cargo.toml not found",
                severity="warning",
            )

        parts = command.strip().split()
        if len(parts) < 2:
            return VerificationResult(
                claim=command,
                status="verified",
                message="Cargo command (Cargo.toml exists)",
                severity="info",
            )

        subcommand = parts[1]

        # Built-in cargo commands
        builtin_commands = {
            "build", "run", "test", "check", "clean", "doc",
            "new", "init", "add", "remove", "update", "search",
            "publish", "install", "uninstall", "bench", "tree",
            "fmt", "clippy", "fix", "audit", "outdated",
        }

        if subcommand in builtin_commands:
            return VerificationResult(
                claim=command,
                status="verified",
                message=f"Cargo built-in command '{subcommand}'",
                severity="info",
            )

        # cargo run --bin <name> or cargo run --example <name>
        if subcommand == "run":
            return self._verify_cargo_run(command, parts, repo_path)

        return VerificationResult(
            claim=command,
            status="verified",
            message="Cargo command (Cargo.toml exists)",
            severity="info",
        )

    def _verify_cargo_run(
        self, command: str, parts: list[str], repo_path: Path
    ) -> VerificationResult:
        """Verify cargo run command with --bin or --example."""
        # Check for --bin or --example flags
        try:
            if "--bin" in parts:
                idx = parts.index("--bin")
                if idx + 1 < len(parts):
                    bin_name = parts[idx + 1]
                    # Check if binary exists in Cargo.toml or src/bin/
                    if self._check_binary_exists(bin_name, repo_path):
                        return VerificationResult(
                            claim=command,
                            status="verified",
                            message=f"Binary '{bin_name}' found",
                            severity="info",
                        )
                    return VerificationResult(
                        claim=command,
                        status="missing",
                        message=f"Binary '{bin_name}' not found in Cargo.toml or src/bin/",
                        severity="warning",
                    )

            if "--example" in parts:
                idx = parts.index("--example")
                if idx + 1 < len(parts):
                    example_name = parts[idx + 1]
                    example_path = repo_path / "examples" / f"{example_name}.rs"
                    if example_path.exists():
                        return VerificationResult(
                            claim=command,
                            status="verified",
                            message=f"Example '{example_name}' found",
                            severity="info",
                        )
                    return VerificationResult(
                        claim=command,
                        status="missing",
                        message=f"Example '{example_name}' not found in examples/",
                        severity="warning",
                    )
        except (ValueError, IndexError):
            pass

        return VerificationResult(
            claim=command,
            status="verified",
            message="Cargo run command",
            severity="info",
        )

    def _check_binary_exists(self, bin_name: str, repo_path: Path) -> bool:
        """Check if a binary target exists."""
        # Check src/bin/<name>.rs
        bin_path = repo_path / "src" / "bin" / f"{bin_name}.rs"
        if bin_path.exists():
            return True

        # Check Cargo.toml [[bin]] sections
        if tomllib:
            cargo_toml = repo_path / "Cargo.toml"
            if cargo_toml.exists():
                try:
                    content = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
                    bins = content.get("bin", [])
                    for b in bins:
                        if b.get("name") == bin_name:
                            return True
                except Exception:
                    pass

        return False

    def _verify_rustc(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify rustc command."""
        parts = command.strip().split()

        # Check if compiling a specific file
        for part in parts:
            if part.endswith(".rs"):
                rs_file = repo_path / part
                if rs_file.exists():
                    return VerificationResult(
                        claim=command,
                        status="verified",
                        message=f"Rust file '{part}' found",
                        severity="info",
                    )
                return VerificationResult(
                    claim=command,
                    status="missing",
                    message=f"Rust file '{part}' not found",
                    severity="warning",
                )

        return VerificationResult(
            claim=command,
            status="verified",
            message="Rust compiler command",
            severity="info",
        )

    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for Rust project."""
        files = []
        if (repo_path / "Cargo.toml").exists():
            files.append("Cargo.toml")
        if (repo_path / "Cargo.lock").exists():
            files.append("Cargo.lock")
        return files or ["Cargo.toml"]

    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        从 Rust 项目提取元数据

        从 Cargo.toml 提取 name, version, license
        """
        cargo_toml = repo_path / "Cargo.toml"
        if not cargo_toml.exists():
            return ProjectMetadata(source_file="")

        if tomllib is None:
            # Fallback to regex parsing
            return self._extract_from_cargo_regex(cargo_toml)

        try:
            content = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        except Exception:
            return self._extract_from_cargo_regex(cargo_toml)

        package = content.get("package", {})
        name = package.get("name")
        version = package.get("version")
        license_str = package.get("license")

        # Handle workspace
        if not name and "workspace" in content:
            workspace = content.get("workspace", {})
            # Try to get from workspace.package
            ws_package = workspace.get("package", {})
            version = version or ws_package.get("version")
            license_str = license_str or ws_package.get("license")

        return ProjectMetadata(
            name=name,
            version=version,
            license=license_str,
            source_file=str(cargo_toml),
        )

    def _extract_from_cargo_regex(self, path: Path) -> ProjectMetadata:
        """使用正则从 Cargo.toml 提取元数据（fallback）"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ProjectMetadata(source_file=str(path))

        # Extract name
        name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        name = name_match.group(1) if name_match else None

        # Extract version
        version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        version = version_match.group(1) if version_match else None

        # Extract license
        license_match = re.search(r'^license\s*=\s*"([^"]+)"', content, re.MULTILINE)
        license_str = license_match.group(1) if license_match else None

        return ProjectMetadata(
            name=name,
            version=version,
            license=license_str,
            source_file=str(path),
        )


# Auto-register plugin
PluginRegistry.register(RustPlugin())
