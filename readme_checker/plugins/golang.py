"""Go ecosystem plugin.

Detects and verifies Go projects.
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
    
    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        从 Go 项目提取元数据
        
        从 go.mod 提取模块名和 Go 版本
        """
        go_mod_path = repo_path / "go.mod"
        if not go_mod_path.exists():
            return ProjectMetadata(source_file="")
        
        try:
            content = go_mod_path.read_text(encoding="utf-8")
        except Exception:
            return ProjectMetadata(source_file=str(go_mod_path))
        
        # 提取模块名: module github.com/user/repo
        module_match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
        module_name = module_match.group(1) if module_match else None
        
        # 提取 Go 版本: go 1.21
        go_version_match = re.search(r'^go\s+(\d+\.\d+(?:\.\d+)?)', content, re.MULTILINE)
        go_version = go_version_match.group(1) if go_version_match else None
        
        # 尝试从 VERSION 文件或 version.go 提取版本号
        version = self._extract_version(repo_path)
        
        # 尝试提取 license
        license_str = self._detect_license(repo_path)
        
        return ProjectMetadata(
            name=module_name,
            version=version or go_version,  # 如果没有项目版本，返回 Go 版本
            license=license_str,
            source_file=str(go_mod_path),
        )
    
    def _extract_version(self, repo_path: Path) -> str | None:
        """尝试从常见位置提取版本号"""
        # 检查 VERSION 文件
        version_file = repo_path / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        
        # 检查 version.go 或 version/version.go
        version_go_paths = [
            repo_path / "version.go",
            repo_path / "version" / "version.go",
            repo_path / "internal" / "version" / "version.go",
            repo_path / "pkg" / "version" / "version.go",
        ]
        
        for vpath in version_go_paths:
            if vpath.exists():
                try:
                    content = vpath.read_text(encoding="utf-8")
                    # 匹配 Version = "1.2.3" 或 const Version = "1.2.3"
                    match = re.search(
                        r'(?:var|const)\s+[Vv]ersion\s*=\s*["\']([^"\']+)["\']',
                        content
                    )
                    if match:
                        return match.group(1)
                except Exception:
                    pass
        
        return None
    
    def _detect_license(self, repo_path: Path) -> str | None:
        """检测 LICENSE 文件中的许可证类型"""
        license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
        
        for lf in license_files:
            license_path = repo_path / lf
            if license_path.exists():
                try:
                    content = license_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                    content_upper = content.upper()
                    
                    # 检测常见许可证
                    if "MIT LICENSE" in content_upper or "PERMISSION IS HEREBY GRANTED" in content_upper:
                        return "MIT"
                    if "APACHE LICENSE" in content_upper and "VERSION 2.0" in content_upper:
                        return "Apache-2.0"
                    if "GNU GENERAL PUBLIC LICENSE" in content_upper:
                        if "VERSION 3" in content_upper:
                            return "GPL-3.0"
                        if "VERSION 2" in content_upper:
                            return "GPL-2.0"
                    if "BSD" in content_upper:
                        if "3-CLAUSE" in content_upper or "THREE-CLAUSE" in content_upper:
                            return "BSD-3-Clause"
                        if "2-CLAUSE" in content_upper or "TWO-CLAUSE" in content_upper:
                            return "BSD-2-Clause"
                    if "ISC LICENSE" in content_upper:
                        return "ISC"
                    if "MOZILLA PUBLIC LICENSE" in content_upper:
                        return "MPL-2.0"
                except Exception:
                    pass
        
        return None


# Auto-register plugin
PluginRegistry.register(GoPlugin())
