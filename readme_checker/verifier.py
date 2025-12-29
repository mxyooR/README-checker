"""
验证引擎模块 - 验证 README 中的声明是否与实际文件系统一致

执行三类验证：
1. 生态系统验证：检查配置文件是否存在
2. 路径验证：检查引用的文件是否存在
3. 命令验证：检查代码块中的脚本是否存在
4. 构建脚本验证：检查 npm run / make 等脚本是否在配置中定义
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from readme_checker.extractor import (
    ExtractedClaims,
    EcosystemClaim,
    PathClaim,
    ModuleClaim,
    module_path_to_filesystem_paths,
)
from readme_checker.build.detector import BuildConfig, detect_build_systems
from readme_checker.build.artifacts import ArtifactRegistry


# ============================================================
# 数据模型
# ============================================================

@dataclass
class Violation:
    """
    违规记录 - 表示一个验证失败的情况
    
    Attributes:
        category: 违规类别（ecosystem, path, command, hype, todo）
        severity: 严重程度（error, warning）
        message: 违规描述信息
        line_number: 相关行号（如果有）
        details: 额外详情（用于报告生成）
    """
    category: str  # "ecosystem", "path", "command", "hype", "todo"
    severity: str  # "error", "warning"
    message: str
    line_number: Optional[int] = None
    details: dict = field(default_factory=dict)


@dataclass
class VerificationResult:
    """
    验证结果 - 包含所有违规记录和统计信息
    
    Attributes:
        violations: 违规记录列表
        stats: 统计信息（LOC、TODO 数量等）
        checks_passed: 通过的检查类别
        checks_failed: 失败的检查类别
    """
    violations: list[Violation] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)


# ============================================================
# 验证函数
# ============================================================

def verify_ecosystem(
    claims: list[EcosystemClaim],
    repo_path: Path,
) -> list[Violation]:
    """
    验证生态系统声明 - 检查配置文件是否存在
    
    Args:
        claims: 生态系统声明列表
        repo_path: 仓库根目录路径
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    for claim in claims:
        # 检查期望的配置文件是否至少存在一个
        found = False
        for expected_file in claim.expected_files:
            if (repo_path / expected_file).exists():
                found = True
                break
        
        if not found:
            # 生成友好的文件列表描述
            if len(claim.expected_files) == 1:
                expected_desc = claim.expected_files[0]
            else:
                expected_desc = " or ".join(claim.expected_files)
            
            violations.append(Violation(
                category="ecosystem",
                severity="error",
                message=f"README mentions '{claim.keyword}', but {expected_desc} is missing",
                line_number=claim.line_number,
                details={
                    "tool": claim.tool,
                    "keyword": claim.keyword,
                    "expected_files": claim.expected_files,
                },
            ))
    
    return violations


def verify_paths(
    claims: list[PathClaim],
    repo_path: Path,
) -> list[Violation]:
    """
    验证路径声明 - 检查引用的文件是否存在
    
    Args:
        claims: 路径声明列表
        repo_path: 仓库根目录路径
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    for claim in claims:
        # 规范化路径
        path = claim.path
        
        # 移除开头的 ./ 
        if path.startswith("./"):
            path = path[2:]
        
        # 构建完整路径
        full_path = repo_path / path
        
        # 检查文件是否存在
        if not full_path.exists():
            # 根据类型选择不同的错误描述
            if claim.claim_type == "image":
                msg = f"Image not found: {claim.path}"
            elif claim.claim_type == "command":
                msg = f"Script not found: {claim.path}"
            else:
                msg = f"File not found: {claim.path}"
            
            violations.append(Violation(
                category="path" if claim.claim_type != "command" else "command",
                severity="error" if claim.claim_type == "command" else "warning",
                message=msg,
                line_number=claim.line_number,
                details={
                    "path": claim.path,
                    "claim_type": claim.claim_type,
                    "source_text": claim.source_text,
                },
            ))
    
    return violations


def verify_modules(
    claims: list[ModuleClaim],
    repo_path: Path,
) -> list[Violation]:
    """
    验证 Python 模块声明 - 检查 python -m 引用的模块是否存在
    
    模块可以是：
    - 单个 .py 文件（如 mymodule.py）
    - 包目录（包含 __init__.py 的目录）
    
    Args:
        claims: 模块声明列表
        repo_path: 仓库根目录路径
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    for claim in claims:
        # 获取可能的文件系统路径
        possible_paths = module_path_to_filesystem_paths(claim.module_path)
        
        # 检查是否至少有一个路径存在
        found = False
        for path in possible_paths:
            full_path = repo_path / path
            if full_path.exists():
                found = True
                break
        
        if not found:
            violations.append(Violation(
                category="module",
                severity="error",
                message=f"Module not found: {claim.module_path}",
                line_number=claim.line_number,
                details={
                    "module_path": claim.module_path,
                    "python_version": claim.python_version,
                    "source_text": claim.source_text,
                    "searched_paths": possible_paths,
                },
            ))
    
    return violations


def verify_all(
    claims: ExtractedClaims,
    repo_path: Path,
) -> VerificationResult:
    """
    执行所有验证检查
    
    Args:
        claims: 提取的所有声明
        repo_path: 仓库根目录路径
    
    Returns:
        VerificationResult 对象，包含所有违规记录
    """
    result = VerificationResult()
    
    # 1. 生态系统验证
    eco_violations = verify_ecosystem(claims.ecosystem_claims, repo_path)
    result.violations.extend(eco_violations)
    
    if eco_violations:
        result.checks_failed.append("ecosystem")
    elif claims.ecosystem_claims:
        result.checks_passed.append("ecosystem")
    
    # 2. 路径验证（包括链接和命令）
    path_violations = verify_paths(claims.path_claims, repo_path)
    result.violations.extend(path_violations)
    
    # 分类统计
    path_errors = [v for v in path_violations if v.category == "path"]
    cmd_errors = [v for v in path_violations if v.category == "command"]
    
    if path_errors:
        result.checks_failed.append("path")
    elif any(c.claim_type in ("image", "link") for c in claims.path_claims):
        result.checks_passed.append("path")
    
    if cmd_errors:
        result.checks_failed.append("command")
    elif any(c.claim_type == "command" for c in claims.path_claims):
        result.checks_passed.append("command")
    
    # 3. 模块验证（python -m 命令）
    module_violations = verify_modules(claims.module_claims, repo_path)
    result.violations.extend(module_violations)
    
    if module_violations:
        result.checks_failed.append("module")
    elif claims.module_claims:
        result.checks_passed.append("module")
    
    # 记录统计信息
    result.stats["ecosystem_claims"] = len(claims.ecosystem_claims)
    result.stats["path_claims"] = len(claims.path_claims)
    result.stats["module_claims"] = len(claims.module_claims)
    result.stats["hype_claims"] = len(claims.hype_claims)
    result.stats["completeness_claims"] = len(claims.completeness_claims)
    result.stats["total_violations"] = len(result.violations)
    
    return result


# ============================================================
# Build Script Verification (V3)
# ============================================================

def verify_build_scripts(
    commands: list[str],
    build_configs: list[BuildConfig],
) -> list[Violation]:
    """
    验证构建脚本引用 - 检查 npm run / make 等命令是否在配置中定义
    
    Args:
        commands: 从 README 提取的命令列表
        build_configs: 检测到的构建系统配置
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    # 收集所有已定义的脚本
    defined_scripts: dict[str, str] = {}  # script_name -> build_system
    for config in build_configs:
        for script_name in config.scripts:
            defined_scripts[script_name] = config.system_type
    
    # 检查每个命令
    for cmd in commands:
        script_name = _extract_script_name(cmd)
        if script_name is None:
            continue
        
        # 检查脚本是否已定义
        if script_name not in defined_scripts:
            # 确定是哪种构建系统的命令
            build_system = _detect_build_system_from_command(cmd)
            if build_system:
                violations.append(Violation(
                    category="build_script",
                    severity="warning",
                    message=f"Script '{script_name}' not found in {build_system} configuration",
                    details={
                        "command": cmd,
                        "script_name": script_name,
                        "build_system": build_system,
                    },
                ))
    
    return violations


def _extract_script_name(command: str) -> str | None:
    """
    从命令中提取脚本名称
    
    支持:
    - npm run <script>
    - yarn <script>
    - make <target>
    - poetry run <script>
    """
    parts = command.strip().split()
    if len(parts) < 2:
        return None
    
    # npm run <script> / npm run-script <script>
    if parts[0] == "npm" and len(parts) >= 3:
        if parts[1] in ("run", "run-script"):
            return parts[2]
        # npm start, npm test, npm build are shortcuts
        if parts[1] in ("start", "test", "build"):
            return parts[1]
    
    # yarn <script> (yarn run is optional)
    if parts[0] == "yarn":
        if len(parts) >= 3 and parts[1] == "run":
            return parts[2]
        if len(parts) >= 2 and parts[1] not in ("install", "add", "remove", "upgrade"):
            return parts[1]
    
    # make <target>
    if parts[0] == "make" and len(parts) >= 2:
        # Skip flags
        for part in parts[1:]:
            if not part.startswith("-"):
                return part
    
    # poetry run <script>
    if parts[0] == "poetry" and len(parts) >= 3 and parts[1] == "run":
        return parts[2]
    
    return None


def _detect_build_system_from_command(command: str) -> str | None:
    """从命令检测构建系统类型"""
    cmd_lower = command.lower()
    
    if cmd_lower.startswith("npm "):
        return "npm"
    if cmd_lower.startswith("yarn "):
        return "npm"  # yarn uses package.json too
    if cmd_lower.startswith("make "):
        return "make"
    if cmd_lower.startswith("poetry "):
        return "python"
    
    return None


def is_build_artifact(
    path: str,
    artifact_registry: ArtifactRegistry,
) -> bool:
    """
    检查路径是否为构建产物
    
    Args:
        path: 文件路径
        artifact_registry: 构建产物注册表
    
    Returns:
        是否为构建产物
    """
    return artifact_registry.is_build_artifact(path)


def verify_paths_with_artifacts(
    claims: list[PathClaim],
    repo_path: Path,
    artifact_registry: ArtifactRegistry,
) -> list[Violation]:
    """
    验证路径声明 - 考虑构建产物
    
    如果文件不存在但是构建产物，则降低严重程度
    
    Args:
        claims: 路径声明列表
        repo_path: 仓库根目录路径
        artifact_registry: 构建产物注册表
    
    Returns:
        违规记录列表
    """
    violations: list[Violation] = []
    
    for claim in claims:
        path = claim.path
        if path.startswith("./"):
            path = path[2:]
        
        full_path = repo_path / path
        
        if not full_path.exists():
            # 检查是否为构建产物
            if artifact_registry.is_build_artifact(path):
                artifact_info = artifact_registry.get_artifact_info(path)
                source = artifact_info.source_target if artifact_info else "build"
                
                violations.append(Violation(
                    category="build_artifact",
                    severity="info",
                    message=f"Build artifact (not in repo): {claim.path} (generated by '{source}')",
                    line_number=claim.line_number,
                    details={
                        "path": claim.path,
                        "is_build_artifact": True,
                        "source_target": source,
                    },
                ))
            else:
                # 普通文件缺失
                if claim.claim_type == "image":
                    msg = f"Image not found: {claim.path}"
                elif claim.claim_type == "command":
                    msg = f"Script not found: {claim.path}"
                else:
                    msg = f"File not found: {claim.path}"
                
                violations.append(Violation(
                    category="path" if claim.claim_type != "command" else "command",
                    severity="error" if claim.claim_type == "command" else "warning",
                    message=msg,
                    line_number=claim.line_number,
                    details={
                        "path": claim.path,
                        "claim_type": claim.claim_type,
                        "source_text": claim.source_text,
                    },
                ))
    
    return violations
