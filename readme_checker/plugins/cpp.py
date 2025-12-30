"""C/C++ ecosystem plugin.

Detects and verifies C/C++ projects (CMake, Make, Meson).
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


class CppPlugin(EcosystemPlugin):
    """Plugin for C/C++ ecosystem (CMake, Make, Meson)."""

    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="cpp",
            config_files=[
                "CMakeLists.txt",
                "Makefile",
                "meson.build",
                "configure.ac",
                "vcpkg.json",
                "conanfile.txt",
                "conanfile.py",
            ],
            package_manager="cmake/make",
            common_commands=[
                "cmake",
                "make",
                "make install",
                "mkdir build",
                "ninja",
                "meson",
                "gcc",
                "g++",
                "clang",
                "clang++",
            ],
        )

    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a C/C++ project."""
        indicators = [
            "CMakeLists.txt",
            "Makefile",
            "meson.build",
            "configure.ac",
            "vcpkg.json",
        ]
        return any((repo_path / f).exists() for f in indicators)

    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify C/C++ build commands."""
        cmd_lower = command.lower().strip()
        parts = command.strip().split()

        if not parts:
            return None

        cmd = parts[0]

        # CMake commands
        if cmd == "cmake":
            return self._verify_cmake(command, repo_path)

        # Make commands
        if cmd == "make":
            return self._verify_make(command, repo_path)

        # Meson commands
        if cmd == "meson":
            return self._verify_meson(command, repo_path)

        # Ninja commands
        if cmd == "ninja":
            return self._verify_ninja(command, repo_path)

        # GCC/Clang commands
        if cmd in ("gcc", "g++", "clang", "clang++"):
            return VerificationResult(
                claim=command,
                status="verified",
                message=f"Compiler command ({cmd})",
                severity="info",
            )

        # mkdir build (common pattern)
        if cmd == "mkdir" and len(parts) >= 2 and "build" in parts[1]:
            return VerificationResult(
                claim=command,
                status="verified",
                message="Create build directory",
                severity="info",
            )

        return None

    def _verify_cmake(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify CMake command."""
        cmake_file = repo_path / "CMakeLists.txt"

        if not cmake_file.exists():
            return VerificationResult(
                claim=command,
                status="missing",
                message="CMakeLists.txt not found",
                severity="warning",
            )

        return VerificationResult(
            claim=command,
            status="verified",
            message="CMake project (CMakeLists.txt exists)",
            severity="info",
        )

    def _verify_make(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Make command."""
        makefile_names = ["Makefile", "makefile", "GNUmakefile"]

        # Check for Makefile
        has_makefile = any((repo_path / f).exists() for f in makefile_names)

        # Also check for CMake (which generates Makefile)
        has_cmake = (repo_path / "CMakeLists.txt").exists()

        if not has_makefile and not has_cmake:
            return VerificationResult(
                claim=command,
                status="missing",
                message="Makefile or CMakeLists.txt not found",
                severity="warning",
            )

        # Extract target if present
        parts = command.strip().split()
        if len(parts) >= 2:
            target = parts[-1]
            if not target.startswith("-"):
                # Common make targets
                common_targets = {
                    "all", "clean", "install", "test", "check",
                    "build", "release", "debug", "dist", "distclean",
                }
                if target in common_targets:
                    return VerificationResult(
                        claim=command,
                        status="verified",
                        message=f"Common make target '{target}'",
                        severity="info",
                    )

        return VerificationResult(
            claim=command,
            status="verified",
            message="Make command (Makefile exists)" if has_makefile else "Make command (CMake project)",
            severity="info",
        )

    def _verify_meson(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Meson command."""
        meson_file = repo_path / "meson.build"

        if not meson_file.exists():
            return VerificationResult(
                claim=command,
                status="missing",
                message="meson.build not found",
                severity="warning",
            )

        return VerificationResult(
            claim=command,
            status="verified",
            message="Meson project (meson.build exists)",
            severity="info",
        )

    def _verify_ninja(self, command: str, repo_path: Path) -> VerificationResult:
        """Verify Ninja command."""
        # Ninja is usually used with CMake or Meson
        has_cmake = (repo_path / "CMakeLists.txt").exists()
        has_meson = (repo_path / "meson.build").exists()

        if not has_cmake and not has_meson:
            return VerificationResult(
                claim=command,
                status="missing",
                message="No CMakeLists.txt or meson.build found for Ninja",
                severity="warning",
            )

        return VerificationResult(
            claim=command,
            status="verified",
            message="Ninja build (CMake/Meson project)",
            severity="info",
        )

    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for C/C++ project."""
        files = []
        if (repo_path / "CMakeLists.txt").exists():
            files.append("CMakeLists.txt")
        if (repo_path / "Makefile").exists():
            files.append("Makefile")
        if (repo_path / "meson.build").exists():
            files.append("meson.build")
        if (repo_path / "vcpkg.json").exists():
            files.append("vcpkg.json")
        return files or ["CMakeLists.txt"]

    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        从 C/C++ 项目提取元数据

        优先级：CMakeLists.txt > vcpkg.json > meson.build
        """
        # 尝试 CMakeLists.txt
        cmake_path = repo_path / "CMakeLists.txt"
        if cmake_path.exists():
            meta = self._extract_from_cmake(cmake_path)
            if meta.version or meta.name:
                return meta

        # 尝试 vcpkg.json
        vcpkg_path = repo_path / "vcpkg.json"
        if vcpkg_path.exists():
            meta = self._extract_from_vcpkg(vcpkg_path)
            if meta.version or meta.name:
                return meta

        # 尝试 meson.build
        meson_path = repo_path / "meson.build"
        if meson_path.exists():
            meta = self._extract_from_meson(meson_path)
            if meta.version or meta.name:
                return meta

        # 检测 license
        license_str = self._detect_license(repo_path)
        if license_str:
            return ProjectMetadata(license=license_str, source_file="LICENSE")

        return ProjectMetadata(source_file="")

    def _extract_from_cmake(self, path: Path) -> ProjectMetadata:
        """从 CMakeLists.txt 提取元数据"""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ProjectMetadata(source_file=str(path))

        # project(name VERSION x.y.z)
        project_match = re.search(
            r'project\s*\(\s*(\w+)(?:\s+VERSION\s+([0-9.]+))?',
            content,
            re.IGNORECASE
        )

        name = None
        version = None

        if project_match:
            name = project_match.group(1)
            version = project_match.group(2)

        # 单独的 set(PROJECT_VERSION "x.y.z")
        if not version:
            version_match = re.search(
                r'set\s*\(\s*(?:PROJECT_VERSION|VERSION)\s+["\']?([0-9.]+)["\']?\s*\)',
                content,
                re.IGNORECASE
            )
            if version_match:
                version = version_match.group(1)

        return ProjectMetadata(
            name=name,
            version=version,
            license=self._detect_license(path.parent),
            source_file=str(path),
        )

    def _extract_from_vcpkg(self, path: Path) -> ProjectMetadata:
        """从 vcpkg.json 提取元数据"""
        import json

        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ProjectMetadata(source_file=str(path))

        name = content.get("name")
        version = content.get("version") or content.get("version-string")
        license_str = content.get("license")

        return ProjectMetadata(
            name=name,
            version=version,
            license=license_str,
            source_file=str(path),
        )

    def _extract_from_meson(self, path: Path) -> ProjectMetadata:
        """从 meson.build 提取元数据"""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ProjectMetadata(source_file=str(path))

        # project('name', 'cpp', version: 'x.y.z')
        project_match = re.search(
            r"project\s*\(\s*['\"](\w+)['\"].*?version\s*:\s*['\"]([^'\"]+)['\"]",
            content,
            re.IGNORECASE | re.DOTALL
        )

        name = None
        version = None

        if project_match:
            name = project_match.group(1)
            version = project_match.group(2)
        else:
            # 简单匹配 project('name', ...)
            simple_match = re.search(
                r"project\s*\(\s*['\"](\w+)['\"]",
                content
            )
            if simple_match:
                name = simple_match.group(1)

        return ProjectMetadata(
            name=name,
            version=version,
            license=self._detect_license(path.parent),
            source_file=str(path),
        )

    def _detect_license(self, repo_path: Path) -> str | None:
        """检测 LICENSE 文件中的许可证类型"""
        license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]

        for lf in license_files:
            license_path = repo_path / lf
            if license_path.exists():
                try:
                    content = license_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                    content_upper = content.upper()

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
                        return "BSD"
                except Exception:
                    pass

        return None


# Auto-register plugin
PluginRegistry.register(CppPlugin())
