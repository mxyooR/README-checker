"""
核心验证器模块 - 验证 README 与代码库的一致性

执行以下验证：
1. 链接验证：检查相对路径链接的文件是否存在
2. 锚点验证：检查页内锚点是否指向有效的标题
3. 绝对 URL 检测：警告指向本仓库的绝对 URL
4. 代码块验证：检查语言标记和 JSON/YAML 语法
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from readme_checker.core.parser import Link, Header, CodeBlock, ParsedMarkdown

# 尝试导入 YAML 解析器
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class Issue:
    """
    检查问题
    
    Attributes:
        severity: 严重程度 (error, warning, info)
        code: 问题代码 (如 DEAD_LINK, INVALID_ANCHOR)
        message: 问题描述
        file_path: 相关文件路径
        line_number: 行号
        suggestion: 修复建议
    """
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    file_path: str
    line_number: int
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """
    验证结果
    
    Attributes:
        issues: 发现的问题列表
        stats: 统计信息
    """
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


class Validator:
    """验证器"""
    
    def __init__(self, repo_path: Path, repo_url_pattern: Optional[str] = None):
        """
        初始化验证器
        
        Args:
            repo_path: 仓库根目录
            repo_url_pattern: 仓库 URL 模式（用于检测绝对 URL）
        """
        self.repo_path = repo_path
        self.repo_url_pattern = repo_url_pattern
    
    def validate_links(
        self,
        links: list[Link],
        headers: list[Header],
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证链接有效性
        
        检查：
        1. 相对路径链接的文件是否存在
        2. 带锚点的链接，目标文件中是否存在对应标题
        
        Args:
            links: 链接列表
            headers: 当前文档的标题列表（用于验证页内锚点）
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        for link in links:
            # 跳过外部链接和 mailto
            if "://" in link.path or link.path.startswith("mailto:"):
                continue
            
            # 页内锚点链接
            if link.path == "" and link.anchor:
                # 在 validate_anchors 中处理
                continue
            
            # 相对路径链接
            if link.path:
                # 清理路径
                clean_path = link.path
                if clean_path.startswith("./"):
                    clean_path = clean_path[2:]
                
                full_path = self.repo_path / clean_path
                
                # 检查是否存在
                path_exists = full_path.exists()
                
                # 如果是目录，检查是否有索引文件（GitHub 会自动渲染）
                if not path_exists and clean_path.endswith('/'):
                    dir_path = self.repo_path / clean_path.rstrip('/')
                    if dir_path.is_dir():
                        index_files = ['README.md', 'readme.md', 'index.md', 'INDEX.md']
                        path_exists = any((dir_path / f).exists() for f in index_files)
                
                # 如果路径是目录（没有尾部斜杠），也检查索引文件
                if full_path.is_dir():
                    index_files = ['README.md', 'readme.md', 'index.md', 'INDEX.md']
                    path_exists = any((full_path / f).exists() for f in index_files)
                
                if not path_exists:
                    issues.append(Issue(
                        severity="error",
                        code="DEAD_LINK",
                        message=f"Link target does not exist: {link.path}",
                        file_path=readme_path,
                        line_number=link.line_number,
                        suggestion=f"Check if '{link.path}' exists or fix the path",
                    ))
                elif link.anchor:
                    # 验证目标文件中的锚点
                    anchor_issue = self._validate_external_anchor(
                        full_path, link.anchor, link, readme_path
                    )
                    if anchor_issue:
                        issues.append(anchor_issue)
        
        return issues
    
    def _validate_external_anchor(
        self,
        target_path: Path,
        anchor: str,
        link: Link,
        readme_path: str,
    ) -> Optional[Issue]:
        """验证外部文件中的锚点"""
        if not target_path.suffix.lower() in ('.md', '.markdown'):
            return None  # 只验证 Markdown 文件的锚点
        
        try:
            content = target_path.read_text(encoding="utf-8")
        except Exception:
            return None  # 无法读取文件，跳过锚点验证
        
        # 简单的标题提取
        from readme_checker.core.parser import parse_markdown
        parsed = parse_markdown(content)
        
        header_ids = {h.id for h in parsed.headers}
        
        if anchor.lower() not in {hid.lower() for hid in header_ids}:
            return Issue(
                severity="error",
                code="INVALID_ANCHOR",
                message=f"Anchor '#{anchor}' not found in {link.path}",
                file_path=readme_path,
                line_number=link.line_number,
                suggestion=f"Check available headers in '{link.path}'",
            )
        
        return None
    
    def validate_anchors(
        self,
        links: list[Link],
        headers: list[Header],
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证页内锚点有效性
        
        Args:
            links: 链接列表
            headers: 当前文档的标题列表
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        # 构建标题 ID 集合（小写用于不区分大小写比较）
        header_ids = {h.id.lower() for h in headers}
        
        for link in links:
            # 只处理页内锚点链接
            if link.path == "" and link.anchor:
                anchor_lower = link.anchor.lower()
                if anchor_lower not in header_ids:
                    issues.append(Issue(
                        severity="error",
                        code="INVALID_ANCHOR",
                        message=f"Anchor '#{link.anchor}' does not match any header",
                        file_path=readme_path,
                        line_number=link.line_number,
                        suggestion=f"Available headers: {', '.join(h.id for h in headers[:5])}...",
                    ))
        
        return issues
    
    def detect_absolute_urls(
        self,
        links: list[Link],
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        检测指向本仓库的绝对 URL
        
        Args:
            links: 链接列表
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        if not self.repo_url_pattern:
            return issues
        
        pattern = re.compile(self.repo_url_pattern, re.IGNORECASE)
        
        for link in links:
            full_path = link.path
            if link.anchor:
                full_path = f"{link.path}#{link.anchor}"
            
            if pattern.search(full_path):
                issues.append(Issue(
                    severity="warning",
                    code="ABSOLUTE_URL",
                    message=f"Absolute URL to own repository: {full_path}",
                    file_path=readme_path,
                    line_number=link.line_number,
                    suggestion="Consider using a relative path for fork/branch compatibility",
                ))
        
        return issues
    
    def _is_directory_tree(self, content: str) -> bool:
        """
        判断代码块内容是否为目录树结构
        
        目录树特征：
        - 包含 │ ├ └ ─ 等树形字符
        - 包含文件扩展名（.py, .js, .cpp 等）
        - 行以 │ 或空格开头
        """
        tree_chars = {'│', '├', '└', '─', '┌', '┐', '┘', '┬', '┴', '┼', '|', '+', '\\'}
        lines = content.strip().split('\n')
        
        if not lines:
            return False
        
        tree_line_count = 0
        for line in lines:
            # 检查是否包含树形字符
            if any(c in line for c in tree_chars):
                tree_line_count += 1
            # 检查是否像文件路径（包含 / 或 \ 和扩展名）
            elif re.search(r'[\\/].*\.\w+', line):
                tree_line_count += 1
        
        # 如果超过 50% 的行看起来像目录树，认为是目录树
        return tree_line_count > len(lines) * 0.5
    
    def _is_plain_text_output(self, content: str) -> bool:
        """
        判断代码块内容是否为纯文本输出（非代码）
        
        纯文本特征：
        - 没有明显的代码语法（函数调用、变量赋值等）
        - 主要是描述性文字
        - 内容较长（短内容可能是代码片段）
        """
        lines = content.strip().split('\n')
        
        if not lines:
            return False
        
        # 短内容（少于 3 行或总字符少于 50）不认为是纯文本
        total_chars = sum(len(line) for line in lines)
        if len(lines) < 3 and total_chars < 50:
            return False
        
        # 代码特征模式
        code_patterns = [
            r'^\s*(def|class|function|const|let|var|import|from|export)\s',
            r'^\s*(if|for|while|switch|try|catch)\s*[\(\{]',
            r'[=;{}()\[\]]',  # 常见代码符号
            r'^\s*#include\s*<',  # C/C++ include
            r'^\s*package\s+\w+',  # Java/Go package
        ]
        
        code_line_count = 0
        for line in lines:
            for pattern in code_patterns:
                if re.search(pattern, line):
                    code_line_count += 1
                    break
        
        # 如果代码行少于 20%，可能是纯文本
        return code_line_count < len(lines) * 0.2

    def validate_code_blocks(
        self,
        code_blocks: list[CodeBlock],
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证代码块
        
        检查：
        1. 代码块是否有语言标记
        2. JSON 代码块语法是否正确
        3. YAML 代码块语法是否正确
        
        Args:
            code_blocks: 代码块列表
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        for block in code_blocks:
            # 检查语言标记
            if not block.language:
                # 智能检测：如果是目录树或纯文本，不报警告
                if self._is_directory_tree(block.content):
                    continue  # 目录树不需要语言标记
                if self._is_plain_text_output(block.content):
                    continue  # 纯文本输出不需要语言标记
                
                issues.append(Issue(
                    severity="warning",
                    code="MISSING_LANG_TAG",
                    message="Code block missing language identifier",
                    file_path=readme_path,
                    line_number=block.line_number,
                    suggestion="Add a language tag like ```python or ```bash",
                ))
                continue
            
            lang = block.language.lower()
            
            # 验证 JSON
            if lang == "json":
                json_issue = self._validate_json(block, readme_path)
                if json_issue:
                    issues.append(json_issue)
            
            # 验证 YAML
            elif lang in ("yaml", "yml"):
                yaml_issue = self._validate_yaml(block, readme_path)
                if yaml_issue:
                    issues.append(yaml_issue)
        
        return issues
    
    def _validate_json(self, block: CodeBlock, readme_path: str) -> Optional[Issue]:
        """验证 JSON 语法"""
        try:
            json.loads(block.content)
            return None
        except json.JSONDecodeError as e:
            return Issue(
                severity="error",
                code="INVALID_JSON",
                message=f"Invalid JSON syntax: {e.msg}",
                file_path=readme_path,
                line_number=block.line_number + e.lineno - 1,
                suggestion="Fix the JSON syntax error",
            )
    
    def _validate_yaml(self, block: CodeBlock, readme_path: str) -> Optional[Issue]:
        """验证 YAML 语法"""
        if not YAML_AVAILABLE:
            return None  # 没有 YAML 解析器，跳过验证
        
        try:
            yaml.safe_load(block.content)
            return None
        except yaml.YAMLError as e:
            line_num = block.line_number
            if hasattr(e, 'problem_mark') and e.problem_mark:
                line_num = block.line_number + e.problem_mark.line
            
            return Issue(
                severity="error",
                code="INVALID_YAML",
                message=f"Invalid YAML syntax: {str(e)[:100]}",
                file_path=readme_path,
                line_number=line_num,
                suggestion="Fix the YAML syntax error",
            )
    
    def validate_all(
        self,
        parsed: ParsedMarkdown,
        readme_path: str = "README.md",
    ) -> ValidationResult:
        """
        执行所有验证
        
        Args:
            parsed: 解析后的 Markdown
            readme_path: README 文件路径
        
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        # 链接验证
        link_issues = self.validate_links(parsed.links, parsed.headers, readme_path)
        result.issues.extend(link_issues)
        
        # 锚点验证
        anchor_issues = self.validate_anchors(parsed.links, parsed.headers, readme_path)
        result.issues.extend(anchor_issues)
        
        # 绝对 URL 检测
        url_issues = self.detect_absolute_urls(parsed.links, readme_path)
        result.issues.extend(url_issues)
        
        # 代码块验证
        block_issues = self.validate_code_blocks(parsed.code_blocks, readme_path)
        result.issues.extend(block_issues)
        
        # 统计
        result.stats["total_links"] = len(parsed.links)
        result.stats["total_headers"] = len(parsed.headers)
        result.stats["total_code_blocks"] = len(parsed.code_blocks)
        result.stats["total_issues"] = len(result.issues)
        result.stats["errors"] = sum(1 for i in result.issues if i.severity == "error")
        result.stats["warnings"] = sum(1 for i in result.issues if i.severity == "warning")
        
        return result


    def validate_version(
        self,
        readme_content: str,
        package_version: Optional[str],
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证版本号一致性
        
        从 README 中提取版本号，与包配置文件中的版本对比。
        
        Args:
            readme_content: README 内容
            package_version: 包配置文件中的版本号
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        if not package_version:
            return issues
        
        # 从 README 中提取版本号
        readme_versions = self._extract_versions_from_readme(readme_content)
        
        if not readme_versions:
            return issues  # README 中没有版本号，不报错
        
        # 标准化版本号进行比较
        pkg_version_normalized = self._normalize_version(package_version)
        
        for version, line_num in readme_versions:
            version_normalized = self._normalize_version(version)
            if version_normalized != pkg_version_normalized:
                issues.append(Issue(
                    severity="warning",
                    code="VERSION_MISMATCH",
                    message=f"Version mismatch: README has '{version}', package has '{package_version}'",
                    file_path=readme_path,
                    line_number=line_num,
                    suggestion=f"Update version to '{package_version}'",
                ))
        
        return issues
    
    def _extract_versions_from_readme(self, content: str) -> list[tuple[str, int]]:
        """
        从 README 中提取版本号
        
        支持的格式：
        - v1.2.3
        - version 1.2.3
        - 徽章中的版本号
        """
        versions: list[tuple[str, int]] = []
        
        # 版本号模式
        patterns = [
            # v1.2.3 或 V1.2.3
            r'\bv?(\d+\.\d+\.\d+(?:-[\w.]+)?)\b',
            # version: 1.2.3
            r'version[:\s]+(\d+\.\d+\.\d+(?:-[\w.]+)?)',
        ]
        
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    version = match.group(1)
                    # 过滤掉明显不是项目版本的（如 Python 3.10）
                    if not self._is_likely_project_version(version, line):
                        continue
                    versions.append((version, line_num))
        
        return versions
    
    def _is_likely_project_version(self, version: str, context: str) -> bool:
        """判断版本号是否可能是项目版本"""
        context_lower = context.lower()
        
        # 排除 Python/Node 版本
        if 'python' in context_lower and version.startswith('3.'):
            return False
        if 'node' in context_lower and version.startswith(('14.', '16.', '18.', '20.')):
            return False
        
        # 徽章中的版本号通常是项目版本
        if 'badge' in context_lower or 'shield' in context_lower:
            return True
        
        # 标题中的版本号
        if context.strip().startswith('#'):
            return True
        
        return True
    
    def _normalize_version(self, version: str) -> str:
        """标准化版本号"""
        # 移除 v 前缀
        if version.lower().startswith('v'):
            version = version[1:]
        return version.strip()
    
    def validate_license(
        self,
        readme_content: str,
        package_license: Optional[str],
        license_file_content: Optional[str] = None,
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证 License 一致性
        
        Args:
            readme_content: README 内容
            package_license: 包配置文件中的 License
            license_file_content: LICENSE 文件内容
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        # 从 README 中提取 License
        readme_license = self._extract_license_from_readme(readme_content)
        
        if not readme_license:
            return issues  # README 中没有 License 信息
        
        # 标准化 License 名称
        readme_license_normalized = self._normalize_license(readme_license)
        
        if package_license:
            pkg_license_normalized = self._normalize_license(package_license)
            if readme_license_normalized != pkg_license_normalized:
                issues.append(Issue(
                    severity="warning",
                    code="LICENSE_MISMATCH",
                    message=f"License mismatch: README mentions '{readme_license}', package has '{package_license}'",
                    file_path=readme_path,
                    line_number=1,
                    suggestion="Ensure license information is consistent",
                ))
        
        return issues
    
    def _extract_license_from_readme(self, content: str) -> Optional[str]:
        """从 README 中提取 License"""
        # 常见 License 名称
        license_names = [
            'MIT', 'Apache-2.0', 'Apache 2.0', 'GPL-3.0', 'GPL-2.0',
            'BSD-3-Clause', 'BSD-2-Clause', 'ISC', 'MPL-2.0', 'LGPL-3.0',
            'Unlicense', 'WTFPL', 'CC0', 'CC-BY-4.0',
        ]
        
        content_upper = content.upper()
        
        for license_name in license_names:
            if license_name.upper() in content_upper:
                return license_name
        
        return None
    
    def _normalize_license(self, license_str: str) -> str:
        """标准化 License 名称"""
        # 移除空格和连字符的差异
        normalized = license_str.upper().replace(' ', '-').replace('_', '-')
        
        # 常见别名映射
        aliases = {
            'APACHE-2.0': 'APACHE-2.0',
            'APACHE-2': 'APACHE-2.0',
            'APACHE2': 'APACHE-2.0',
            'GPL-3': 'GPL-3.0',
            'GPL3': 'GPL-3.0',
            'BSD-3': 'BSD-3-CLAUSE',
            'BSD3': 'BSD-3-CLAUSE',
        }
        
        return aliases.get(normalized, normalized)


    def validate_env_vars(
        self,
        env_vars: list,  # list[EnvVarUsage]
        readme_content: str,
        env_example_path: Optional[Path] = None,
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证环境变量一致性
        
        检查代码中使用的环境变量是否在 README 或 .env.example 中文档化。
        
        Args:
            env_vars: 代码中使用的环境变量列表
            readme_content: README 内容
            env_example_path: .env.example 文件路径（已弃用，使用 repo_path 自动扫描）
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        # 从 README 中提取提到的环境变量
        documented_vars = self._extract_env_vars_from_readme(readme_content)
        
        # 从 .env.example 等文件中提取环境变量（使用新的扫描器）
        from readme_checker.core.scanner import get_documented_env_var_names
        dotenv_vars = get_documented_env_var_names(self.repo_path)
        documented_vars.update(dotenv_vars)
        
        # 兼容旧的 env_example_path 参数
        if env_example_path and env_example_path.exists():
            try:
                env_content = env_example_path.read_text(encoding='utf-8')
                documented_vars.update(self._extract_env_vars_from_env_file(env_content))
            except Exception:
                pass
        
        # 检查每个代码中使用的环境变量
        seen_vars: set[str] = set()
        for env_var in env_vars:
            if env_var.name in seen_vars:
                continue
            seen_vars.add(env_var.name)
            
            # 跳过常见的系统环境变量
            if self._is_common_env_var(env_var.name):
                continue
            
            if env_var.name not in documented_vars:
                issues.append(Issue(
                    severity="error",
                    code="MISSING_ENV_VAR",
                    message=f"Environment variable '{env_var.name}' used in code but not documented",
                    file_path=env_var.file_path,
                    line_number=env_var.line_number,
                    suggestion=f"Add '{env_var.name}' to README or .env.example",
                ))
        
        return issues
    
    def _extract_env_vars_from_readme(self, content: str) -> set[str]:
        """从 README 中提取提到的环境变量"""
        vars_found: set[str] = set()
        
        # 匹配大写字母和下划线组成的词（典型的环境变量命名）
        pattern = re.compile(r'\b([A-Z][A-Z0-9_]{2,})\b')
        
        for match in pattern.finditer(content):
            var_name = match.group(1)
            # 过滤掉常见的非环境变量词
            if not self._is_common_word(var_name):
                vars_found.add(var_name)
        
        return vars_found
    
    def _extract_env_vars_from_env_file(self, content: str) -> set[str]:
        """从 .env 文件中提取环境变量"""
        vars_found: set[str] = set()
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                var_name = line.split('=')[0].strip()
                if var_name:
                    vars_found.add(var_name)
        
        return vars_found
    
    def _is_common_env_var(self, name: str) -> bool:
        """判断是否为常见的系统环境变量"""
        common_vars = {
            'PATH', 'HOME', 'USER', 'SHELL', 'LANG', 'TERM',
            'PWD', 'OLDPWD', 'HOSTNAME', 'LOGNAME',
            'NODE_ENV', 'DEBUG', 'CI', 'GITHUB_ACTIONS',
            'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE',
        }
        return name in common_vars
    
    def _is_common_word(self, word: str) -> bool:
        """判断是否为常见的非环境变量词"""
        common_words = {
            'README', 'TODO', 'FIXME', 'NOTE', 'WARNING', 'ERROR',
            'API', 'URL', 'URI', 'HTTP', 'HTTPS', 'JSON', 'XML',
            'HTML', 'CSS', 'SQL', 'CLI', 'GUI', 'SDK', 'IDE',
            'MIT', 'BSD', 'GPL', 'APACHE',
        }
        return word in common_words
    
    def validate_system_deps(
        self,
        deps: list,  # list[SystemDependency]
        readme_content: str,
        readme_path: str = "README.md",
    ) -> list[Issue]:
        """
        验证系统依赖文档
        
        检查代码中调用的系统工具是否在 README 中提及。
        
        Args:
            deps: 系统依赖列表
            readme_content: README 内容
            readme_path: README 文件路径
        
        Returns:
            问题列表
        """
        issues: list[Issue] = []
        
        readme_lower = readme_content.lower()
        
        # 检查每个系统依赖
        seen_deps: set[str] = set()
        for dep in deps:
            tool_name = dep.tool_name.lower()
            if tool_name in seen_deps:
                continue
            seen_deps.add(tool_name)
            
            # 检查 README 中是否提到该工具
            if tool_name not in readme_lower:
                # 检查是否有安装指令
                install_patterns = [
                    f'apt-get install.*{tool_name}',
                    f'apt install.*{tool_name}',
                    f'brew install.*{tool_name}',
                    f'yum install.*{tool_name}',
                    f'dnf install.*{tool_name}',
                    f'pacman -S.*{tool_name}',
                    f'choco install.*{tool_name}',
                ]
                
                has_install = any(
                    re.search(pattern, readme_lower)
                    for pattern in install_patterns
                )
                
                if not has_install:
                    issues.append(Issue(
                        severity="warning",
                        code="MISSING_SYS_DEP",
                        message=f"System dependency '{dep.tool_name}' used in code but not documented",
                        file_path=dep.file_path,
                        line_number=dep.line_number,
                        suggestion=f"Add installation instructions for '{dep.tool_name}' to README",
                    ))
        
        return issues
