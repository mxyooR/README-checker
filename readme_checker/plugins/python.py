"""Python ecosystem plugin.

Detects and verifies Python/pip/poetry projects.
"""

import re
import sys
from pathlib import Path

from readme_checker.plugins.base import (
    EcosystemInfo,
    EcosystemPlugin,
    ProjectMetadata,
    VerificationResult,
    PluginRegistry,
)

# Handle tomllib/tomli for different Python versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore


class PythonPlugin(EcosystemPlugin):
    """Plugin for Python ecosystem."""
    
    @property
    def info(self) -> EcosystemInfo:
        return EcosystemInfo(
            name="python",
            config_files=[
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "requirements.txt",
                "Pipfile",
            ],
            package_manager="pip",
            common_commands=[
                "pip install",
                "python",
                "python3",
                "pytest",
                "poetry install",
                "poetry run",
                "pipenv install",
            ],
        )
    
    def detect(self, repo_path: Path) -> bool:
        """Detect if project is a Python project."""
        indicators = [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
        ]
        return any((repo_path / f).exists() for f in indicators)
    
    def verify_command(self, command: str, repo_path: Path) -> VerificationResult | None:
        """Verify Python commands."""
        cmd_lower = command.lower().strip()
        
        # Check if this is a Python-related command
        python_prefixes = ["python ", "python3 ", "pip ", "poetry ", "pipenv ", "pytest "]
        if not any(cmd_lower.startswith(prefix) for prefix in python_prefixes):
            return None
        
        parts = command.strip().split()
        
        # python -m <module>
        if parts[0] in ("python", "python3") and len(parts) >= 3 and parts[1] == "-m":
            module_name = parts[2]
            return self._verify_module(module_name, repo_path)
        
        # python <script.py>
        if parts[0] in ("python", "python3") and len(parts) >= 2:
            script = parts[1]
            if script.endswith(".py"):
                return self._verify_script(script, repo_path)
        
        # poetry run <script>
        if parts[0] == "poetry" and len(parts) >= 3 and parts[1] == "run":
            script_name = parts[2]
            return self._verify_poetry_script(script_name, repo_path)
        
        # pip install - always valid
        if cmd_lower.startswith("pip install"):
            return VerificationResult(
                claim=command,
                status="verified",
                message="pip install command",
                severity="info",
            )
        
        return None
    
    def _verify_module(self, module_name: str, repo_path: Path) -> VerificationResult:
        """Verify a Python module exists."""
        # Convert module path to file path
        module_parts = module_name.split(".")
        
        # Check for package (directory with __init__.py)
        package_path = repo_path / "/".join(module_parts) / "__init__.py"
        if package_path.exists():
            return VerificationResult(
                claim=f"python -m {module_name}",
                status="verified",
                message=f"Module '{module_name}' found as package",
                severity="info",
            )
        
        # Check for module file
        module_path = repo_path / "/".join(module_parts[:-1] + [module_parts[-1] + ".py"])
        if module_path.exists():
            return VerificationResult(
                claim=f"python -m {module_name}",
                status="verified",
                message=f"Module '{module_name}' found",
                severity="info",
            )
        
        # Check root level
        root_module = repo_path / f"{module_parts[0]}.py"
        root_package = repo_path / module_parts[0] / "__init__.py"
        if root_module.exists() or root_package.exists():
            return VerificationResult(
                claim=f"python -m {module_name}",
                status="verified",
                message=f"Module '{module_name}' found at root",
                severity="info",
            )
        
        return VerificationResult(
            claim=f"python -m {module_name}",
            status="missing",
            message=f"Module '{module_name}' not found",
            severity="warning",
        )
    
    def _verify_script(self, script: str, repo_path: Path) -> VerificationResult:
        """Verify a Python script exists."""
        script_path = repo_path / script
        if script_path.exists():
            return VerificationResult(
                claim=f"python {script}",
                status="verified",
                message=f"Script '{script}' found",
                severity="info",
            )
        
        return VerificationResult(
            claim=f"python {script}",
            status="missing",
            message=f"Script '{script}' not found",
            severity="warning",
        )
    
    def _verify_poetry_script(self, script_name: str, repo_path: Path) -> VerificationResult:
        """Verify a poetry script exists in pyproject.toml."""
        if tomllib is None:
            return VerificationResult(
                claim=f"poetry run {script_name}",
                status="skipped",
                message="tomllib not available",
                severity="info",
            )
        
        pyproject_path = repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            return VerificationResult(
                claim=f"poetry run {script_name}",
                status="missing",
                message="pyproject.toml not found",
                severity="warning",
            )
        
        try:
            content = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            scripts = content.get("tool", {}).get("poetry", {}).get("scripts", {})
            
            if script_name in scripts:
                return VerificationResult(
                    claim=f"poetry run {script_name}",
                    status="verified",
                    message=f"Script '{script_name}' found in pyproject.toml",
                    severity="info",
                )
            
            # Also check [project.scripts]
            project_scripts = content.get("project", {}).get("scripts", {})
            if script_name in project_scripts:
                return VerificationResult(
                    claim=f"poetry run {script_name}",
                    status="verified",
                    message=f"Script '{script_name}' found in [project.scripts]",
                    severity="info",
                )
            
        except Exception:
            pass
        
        return VerificationResult(
            claim=f"poetry run {script_name}",
            status="missing",
            message=f"Script '{script_name}' not found in pyproject.toml",
            severity="warning",
        )
    
    def get_expected_files(self, repo_path: Path) -> list[str]:
        """Get expected files for Python project."""
        files = []
        if (repo_path / "pyproject.toml").exists():
            files.append("pyproject.toml")
        if (repo_path / "requirements.txt").exists():
            files.append("requirements.txt")
        if (repo_path / "setup.py").exists():
            files.append("setup.py")
        return files or ["pyproject.toml"]
    
    def extract_metadata(self, repo_path: Path) -> ProjectMetadata:
        """
        从 Python 项目提取元数据
        
        优先级：pyproject.toml > setup.py > setup.cfg
        """
        # 尝试 pyproject.toml
        pyproject_path = repo_path / "pyproject.toml"
        if pyproject_path.exists():
            meta = self._extract_from_pyproject(pyproject_path)
            if meta.version or meta.license:
                return meta
        
        # 尝试 setup.py
        setup_path = repo_path / "setup.py"
        if setup_path.exists():
            meta = self._extract_from_setup_py(setup_path)
            if meta.version or meta.license:
                return meta
        
        return ProjectMetadata(source_file="")
    
    def _extract_from_pyproject(self, path: Path) -> ProjectMetadata:
        """从 pyproject.toml 提取元数据"""
        if tomllib is None:
            return ProjectMetadata(source_file=str(path))
        
        try:
            content = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ProjectMetadata(source_file=str(path))
        
        # 尝试 [project] 部分 (PEP 621)
        project = content.get("project", {})
        name = project.get("name")
        version = project.get("version")
        license_info = project.get("license")
        
        # license 可能是字符串或字典
        if isinstance(license_info, dict):
            license_str = license_info.get("text") or license_info.get("file")
        else:
            license_str = license_info
        
        # 尝试 [tool.poetry] 部分
        if not version:
            poetry = content.get("tool", {}).get("poetry", {})
            name = name or poetry.get("name")
            version = poetry.get("version")
            license_str = license_str or poetry.get("license")
        
        return ProjectMetadata(
            name=name,
            version=version,
            license=license_str,
            source_file=str(path),
        )
    
    def _extract_from_setup_py(self, path: Path) -> ProjectMetadata:
        """从 setup.py 提取元数据（使用正则表达式）"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ProjectMetadata(source_file=str(path))
        
        # 提取 version
        version_match = re.search(
            r'version\s*=\s*["\']([^"\']+)["\']',
            content
        )
        version = version_match.group(1) if version_match else None
        
        # 提取 name
        name_match = re.search(
            r'name\s*=\s*["\']([^"\']+)["\']',
            content
        )
        name = name_match.group(1) if name_match else None
        
        # 提取 license
        license_match = re.search(
            r'license\s*=\s*["\']([^"\']+)["\']',
            content
        )
        license_str = license_match.group(1) if license_match else None
        
        return ProjectMetadata(
            name=name,
            version=version,
            license=license_str,
            source_file=str(path),
        )


# Auto-register plugin
PluginRegistry.register(PythonPlugin())
