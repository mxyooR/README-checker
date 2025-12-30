"""Java ecosystem plugin.

Detects and verifies Java/Maven/Gradle projects.
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    ProjectMetadata,
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
    
    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        从 Java 项目提取元数据
        
        优先级：pom.xml > build.gradle > build.gradle.kts
        """
        # 尝试 Maven pom.xml
        pom_path = repo_path / "pom.xml"
        if pom_path.exists():
            meta = self._extract_from_pom(pom_path)
            if meta.version or meta.name:
                return meta
        
        # 尝试 Gradle build.gradle
        gradle_path = repo_path / "build.gradle"
        if gradle_path.exists():
            meta = self._extract_from_gradle(gradle_path)
            if meta.version or meta.name:
                return meta
        
        # 尝试 Gradle Kotlin DSL build.gradle.kts
        gradle_kts_path = repo_path / "build.gradle.kts"
        if gradle_kts_path.exists():
            meta = self._extract_from_gradle_kts(gradle_kts_path)
            if meta.version or meta.name:
                return meta
        
        return ProjectMetadata(source_file="")
    
    def _extract_from_pom(self, path: Path) -> ProjectMetadata:
        """从 pom.xml 提取元数据"""
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            
            # Maven POM 使用命名空间
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            
            # 尝试带命名空间的查找
            def find_text(tag: str) -> str | None:
                # 先尝试带命名空间
                elem = root.find(f"m:{tag}", ns)
                if elem is not None and elem.text:
                    return elem.text.strip()
                # 再尝试不带命名空间
                elem = root.find(tag)
                if elem is not None and elem.text:
                    return elem.text.strip()
                return None
            
            # 提取基本信息
            group_id = find_text("groupId")
            artifact_id = find_text("artifactId")
            version = find_text("version")
            name = find_text("name")
            
            # 如果没有 groupId，尝试从 parent 获取
            if not group_id:
                parent = root.find("m:parent", ns) or root.find("parent")
                if parent is not None:
                    group_elem = parent.find("m:groupId", ns) or parent.find("groupId")
                    if group_elem is not None and group_elem.text:
                        group_id = group_elem.text.strip()
            
            # 如果没有 version，尝试从 parent 获取
            if not version:
                parent = root.find("m:parent", ns) or root.find("parent")
                if parent is not None:
                    version_elem = parent.find("m:version", ns) or parent.find("version")
                    if version_elem is not None and version_elem.text:
                        version = version_elem.text.strip()
            
            # 提取 license
            license_str = None
            licenses = root.find("m:licenses", ns) or root.find("licenses")
            if licenses is not None:
                license_elem = licenses.find("m:license", ns) or licenses.find("license")
                if license_elem is not None:
                    license_name = license_elem.find("m:name", ns) or license_elem.find("name")
                    if license_name is not None and license_name.text:
                        license_str = license_name.text.strip()
            
            # 构建项目名称
            project_name = name or artifact_id
            if group_id and artifact_id:
                project_name = f"{group_id}:{artifact_id}"
            
            return ProjectMetadata(
                name=project_name,
                version=version,
                license=license_str,
                source_file=str(path),
            )
            
        except Exception:
            return ProjectMetadata(source_file=str(path))
    
    def _extract_from_gradle(self, path: Path) -> ProjectMetadata:
        """从 build.gradle (Groovy DSL) 提取元数据"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ProjectMetadata(source_file=str(path))
        
        # 提取 version
        # version '1.0.0' 或 version = '1.0.0' 或 version "1.0.0"
        version_match = re.search(
            r'^\s*version\s*[=]?\s*["\']([^"\']+)["\']',
            content,
            re.MULTILINE
        )
        version = version_match.group(1) if version_match else None
        
        # 提取 group
        group_match = re.search(
            r'^\s*group\s*[=]?\s*["\']([^"\']+)["\']',
            content,
            re.MULTILINE
        )
        group = group_match.group(1) if group_match else None
        
        # 尝试从 settings.gradle 获取项目名
        name = self._get_gradle_project_name(path.parent)
        
        # 构建完整名称
        if group and name:
            full_name = f"{group}:{name}"
        else:
            full_name = name or group
        
        # 检测 license
        license_str = self._detect_license(path.parent)
        
        return ProjectMetadata(
            name=full_name,
            version=version,
            license=license_str,
            source_file=str(path),
        )
    
    def _extract_from_gradle_kts(self, path: Path) -> ProjectMetadata:
        """从 build.gradle.kts (Kotlin DSL) 提取元数据"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ProjectMetadata(source_file=str(path))
        
        # 提取 version
        # version = "1.0.0"
        version_match = re.search(
            r'^\s*version\s*=\s*"([^"]+)"',
            content,
            re.MULTILINE
        )
        version = version_match.group(1) if version_match else None
        
        # 提取 group
        group_match = re.search(
            r'^\s*group\s*=\s*"([^"]+)"',
            content,
            re.MULTILINE
        )
        group = group_match.group(1) if group_match else None
        
        # 尝试从 settings.gradle.kts 获取项目名
        name = self._get_gradle_project_name(path.parent)
        
        # 构建完整名称
        if group and name:
            full_name = f"{group}:{name}"
        else:
            full_name = name or group
        
        # 检测 license
        license_str = self._detect_license(path.parent)
        
        return ProjectMetadata(
            name=full_name,
            version=version,
            license=license_str,
            source_file=str(path),
        )
    
    def _get_gradle_project_name(self, repo_path: Path) -> str | None:
        """从 settings.gradle 或 settings.gradle.kts 获取项目名"""
        settings_files = [
            repo_path / "settings.gradle",
            repo_path / "settings.gradle.kts",
        ]
        
        for settings_path in settings_files:
            if settings_path.exists():
                try:
                    content = settings_path.read_text(encoding="utf-8")
                    # rootProject.name = 'my-project' 或 rootProject.name = "my-project"
                    match = re.search(
                        r'rootProject\.name\s*=\s*["\']([^"\']+)["\']',
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
PluginRegistry.register(JavaPlugin())
