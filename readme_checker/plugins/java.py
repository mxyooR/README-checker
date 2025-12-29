"""Java ecosystem plugin.

Detects and verifies Java/Maven/Gradle projects.
"""

from pathlib import Path
import re

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    VerificationResult,
    PluginRegistry,
)


class JavaPlugin(EcosystemPlugin):
    """Plugin for Java ecosystem (Maven/Gradle)."""
    
    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="java",
            config_files=[
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
            ],
            package_manager="maven/gradle",
            common_commands=[
                "mvn",
                "mvn clean",
                "mvn install",
                "mvn package",
                "mvn test",
                "gradle",
                "gradle build",
                "gradle test",
                "./gradlew",
                "./mvnw",
            ],
        )
    
    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a Java project."""
        indicators = [
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
        ]
        return any((repo_path / f).exists() for f in indicators)
    
    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify Maven/Gradle commands."""
        cmd_lower = command.lower().strip()
        
        # Maven commands
        if cmd_lower.startswith(("mvn ", "./mvnw ")):
            return self._verify_maven(command, repo_path)
        
        # Gradle commands
        if cmd_lower.startswith(("gradle ", "./gradlew ", "gradlew ")):
            return self._verify_gradle(command, repo_path)
        
        return None
    
    def _verify_maven(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Maven command."""
        pom_path = repo_path / "pom.xml"
        
        # Check for wrapper
        if command.strip().startswith("./mvnw"):
            wrapper_path = repo_path / "mvnw"
            if not wrapper_path.exists():
                return VerificationResult(
                    claim=command,
                    status="missing",
                    message="Maven wrapper (mvnw) not found",
                    severity="warning",
                    suggestion="Run 'mvn wrapper:wrapper' to generate wrapper",
                )
        
        if not pom_path.exists():
            return VerificationResult(
                claim=command,
                status="missing",
                message="pom.xml not found",
                severity="warning",
            )
        
        return VerificationResult(
            claim=command,
            status="verified",
            message="Maven project (pom.xml exists)",
            severity="info",
        )
    
    def _verify_gradle(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Gradle command."""
        gradle_files = [
            "build.gradle",
            "build.gradle.kts",
        ]
        
        # Check for wrapper
        if command.strip().startswith(("./gradlew", "gradlew")):
            wrapper_path = repo_path / "gradlew"
            if not wrapper_path.exists():
                return VerificationResult(
                    claim=command,
                    status="missing",
                    message="Gradle wrapper (gradlew) not found",
                    severity="warning",
                    suggestion="Run 'gradle wrapper' to generate wrapper",
                )
        
        if not any((repo_path / f).exists() for f in gradle_files):
            return VerificationResult(
                claim=command,
                status="missing",
                message="build.gradle not found",
                severity="warning",
            )
        
        # Extract task name if present
        parts = command.strip().split()
        if len(parts) >= 2:
            task = parts[-1]
            # Common Gradle tasks that are always available
            builtin_tasks = {
                "build", "clean", "test", "check", "assemble",
                "jar", "war", "bootRun", "bootJar", "tasks",
                "dependencies", "help", "init", "wrapper",
            }
            if task in builtin_tasks:
                return VerificationResult(
                    claim=command,
                    status="verified",
                    message=f"Gradle built-in task '{task}'",
                    severity="info",
                )
        
        return VerificationResult(
            claim=command,
            status="verified",
            message="Gradle project (build.gradle exists)",
            severity="info",
        )
    
    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for Java project."""
        files = []
        if (repo_path / "pom.xml").exists():
            files.append("pom.xml")
        if (repo_path / "build.gradle").exists():
            files.append("build.gradle")
        if (repo_path / "build.gradle.kts").exists():
            files.append("build.gradle.kts")
        return files or ["pom.xml"]


# Auto-register plugin
PluginRegistry.register(JavaPlugin())
