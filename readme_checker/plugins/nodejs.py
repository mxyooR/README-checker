"""Node.js ecosystem plugin.

Detects and verifies Node.js/npm/yarn projects.
"""

import json
from pathlib import Path

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    ProjectMetadata,
    VerificationResult,
    PluginRegistry,
)


class NodeJsPlugin(EcosystemPlugin):
    """Plugin for Node.js ecosystem."""
    
    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="nodejs",
            config_files=["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
            package_manager="npm",
            common_commands=[
                "npm install",
                "npm run",
                "npm start",
                "npm test",
                "npm build",
                "yarn",
                "yarn add",
                "yarn run",
                "pnpm install",
            ],
        )
    
    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a Node.js project."""
        return (repo_path / "package.json").exists()
    
    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify npm/yarn commands."""
        cmd_lower = command.lower().strip()
        
        # Check if this is an npm/yarn command
        if not any(cmd_lower.startswith(prefix) for prefix in ["npm ", "yarn ", "pnpm ", "npx "]):
            return None
        
        # Load package.json
        pkg_path = repo_path / "package.json"
        if not pkg_path.exists():
            return VerificationResult(
                claim=command,
                status="missing",
                message="package.json not found",
                severity="error",
            )
        
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except Exception as e:
            return VerificationResult(
                claim=command,
                status="missing",
                message=f"Failed to parse package.json: {e}",
                severity="error",
            )
        
        scripts = pkg.get("scripts", {})
        
        # Extract script name from command
        script_name = self._extract_script_name(command)
        if script_name is None:
            return VerificationResult(
                claim=command,
                status="verified",
                message="Command verified (no script reference)",
                severity="info",
            )
        
        # Check if script exists
        if script_name in scripts:
            return VerificationResult(
                claim=command,
                status="verified",
                message=f"Script '{script_name}' found in package.json",
                severity="info",
            )
        
        # Built-in npm commands that don't need scripts
        builtin_commands = {"install", "ci", "update", "outdated", "audit", "init", "publish"}
        if script_name in builtin_commands:
            return VerificationResult(
                claim=command,
                status="verified",
                message=f"Built-in npm command '{script_name}'",
                severity="info",
            )
        
        return VerificationResult(
            claim=command,
            status="missing",
            message=f"Script '{script_name}' not found in package.json",
            severity="warning",
            suggestion=f"Add '{script_name}' to scripts in package.json",
        )
    
    def _extract_script_name(self, command: str) -> str | None:
        """Extract script name from npm/yarn command."""
        parts = command.strip().split()
        if len(parts) < 2:
            return None
        
        # npm run <script>
        if parts[0] == "npm" and len(parts) >= 3 and parts[1] == "run":
            return parts[2]
        
        # npm <builtin> (start, test, etc.)
        if parts[0] == "npm" and len(parts) >= 2:
            return parts[1]
        
        # yarn <script> or yarn run <script>
        if parts[0] == "yarn":
            if len(parts) >= 3 and parts[1] == "run":
                return parts[2]
            if len(parts) >= 2:
                return parts[1]
        
        # pnpm run <script>
        if parts[0] == "pnpm" and len(parts) >= 3 and parts[1] == "run":
            return parts[2]
        
        return None
    
    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for Node.js project."""
        return ["package.json"]
    
    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """从 package.json 提取元数据"""
        pkg_path = repo_path / "package.json"
        if not pkg_path.exists():
            return ProjectMetadata(source_file="")
        
        try:
            content = json.loads(pkg_path.read_text(encoding="utf-8"))
        except Exception:
            return ProjectMetadata(source_file=str(pkg_path))
        
        return ProjectMetadata(
            name=content.get("name"),
            version=content.get("version"),
            license=content.get("license"),
            source_file=str(pkg_path),
        )


# Auto-register plugin
PluginRegistry.register(NodeJsPlugin())
