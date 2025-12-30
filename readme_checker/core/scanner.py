"""
代码扫描器模块 - 扫描代码库提取环境变量和系统依赖

扫描代码文件，提取：
1. 环境变量引用（os.getenv, process.env 等）
2. 系统依赖调用（subprocess.run, exec 等）
"""

import ast
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EnvVarUsage:
    """
    环境变量使用记录
    
    Attributes:
        name: 环境变量名称
        file_path: 源文件路径
        line_number: 行号 (1-based)
        column_number: 列号 (0-based)
        pattern: 匹配的模式
        source_library: 来源配置库 (pydantic, decouple, django-environ 等)
        context: 上下文信息 (类名、函数名)
    """
    name: str
    file_path: str
    line_number: int
    column_number: int = 0
    pattern: str = ""
    source_library: Optional[str] = None
    context: Optional[str] = None


@dataclass
class UnresolvedRef:
    """
    无法解析的动态引用
    
    Attributes:
        file_path: 源文件路径
        line_number: 行号 (1-based)
        column_number: 列号 (0-based)
        expression: 原始表达式
        reason: 无法解析的原因
    """
    file_path: str
    line_number: int
    column_number: int
    expression: str
    reason: str


@dataclass
class SystemDependency:
    """
    系统依赖使用记录
    
    Attributes:
        tool_name: 工具名称
        file_path: 源文件路径
        line_number: 行号
        invocation: 调用方式
    """
    tool_name: str
    file_path: str
    line_number: int
    invocation: str


@dataclass
class ScanResult:
    """
    扫描结果
    
    Attributes:
        env_vars: 环境变量使用列表
        system_deps: 系统依赖列表
        unresolved_refs: 无法解析的动态引用列表
    """
    env_vars: list[EnvVarUsage] = field(default_factory=list)
    system_deps: list[SystemDependency] = field(default_factory=list)
    unresolved_refs: list[UnresolvedRef] = field(default_factory=list)
    
    def to_json(self) -> str:
        """
        序列化为 JSON 字符串
        
        Returns:
            JSON 格式的字符串
        """
        data = {
            "env_vars": [asdict(ev) for ev in self.env_vars],
            "system_deps": [asdict(sd) for sd in self.system_deps],
            "unresolved_refs": [asdict(ur) for ur in self.unresolved_refs],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ScanResult":
        """
        从 JSON 字符串反序列化
        
        Args:
            json_str: JSON 格式的字符串
        
        Returns:
            ScanResult 对象
        """
        data = json.loads(json_str)
        return cls(
            env_vars=[EnvVarUsage(**ev) for ev in data.get("env_vars", [])],
            system_deps=[SystemDependency(**sd) for sd in data.get("system_deps", [])],
            unresolved_refs=[UnresolvedRef(**ur) for ur in data.get("unresolved_refs", [])],
        )


# AST 文件大小限制 (10MB)
AST_FILE_SIZE_LIMIT = 10 * 1024 * 1024


class VariableTracker:
    """
    变量追踪器 - 追踪字符串变量赋值用于解析间接引用
    
    支持追踪：
    - 简单赋值: key = "API_KEY"
    - 列表赋值: keys = ["A", "B", "C"]
    """
    
    def __init__(self):
        self.string_vars: dict[str, str] = {}  # 变量名 -> 字符串值
        self.list_vars: dict[str, list[str]] = {}  # 变量名 -> 字符串列表
    
    def track_assignment(self, target: str, value: ast.expr) -> None:
        """追踪赋值语句"""
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            self.string_vars[target] = value.value
        elif isinstance(value, ast.List):
            strings = []
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    strings.append(elt.value)
            if strings:
                self.list_vars[target] = strings
    
    def resolve_name(self, name: str) -> Optional[str]:
        """解析变量名到字符串值"""
        return self.string_vars.get(name)
    
    def resolve_list(self, name: str) -> Optional[list[str]]:
        """解析变量名到字符串列表"""
        return self.list_vars.get(name)


class ASTEnvVarExtractor(ast.NodeVisitor):
    """
    AST 环境变量提取器
    
    使用 AST 解析 Python 代码，提取环境变量引用，支持：
    - 直接引用: os.getenv("KEY")
    - 间接引用: key = "API_KEY"; os.getenv(key)
    - 列表迭代: keys = ["A", "B"]; [os.getenv(k) for k in keys]
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self.unresolved: list[UnresolvedRef] = []
        self.var_tracker = VariableTracker()
        self._current_context: Optional[str] = None
        self._comprehension_vars: dict[str, list[str]] = {}  # 迭代变量 -> 来源列表
    
    def visit_Module(self, node: ast.Module) -> None:
        """访问模块，先收集所有赋值"""
        # 第一遍：收集变量赋值
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.var_tracker.track_assignment(target.id, child.value)
        # 第二遍：正常访问
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """访问类定义，记录上下文"""
        old_context = self._current_context
        self._current_context = node.name
        self.generic_visit(node)
        self._current_context = old_context
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """访问函数定义，记录上下文"""
        old_context = self._current_context
        if self._current_context:
            self._current_context = f"{self._current_context}.{node.name}"
        else:
            self._current_context = node.name
        self.generic_visit(node)
        self._current_context = old_context
    
    visit_AsyncFunctionDef = visit_FunctionDef
    
    def visit_ListComp(self, node: ast.ListComp) -> None:
        """访问列表推导式，追踪迭代变量"""
        for generator in node.generators:
            if isinstance(generator.target, ast.Name) and isinstance(generator.iter, ast.Name):
                iter_name = generator.iter.id
                target_name = generator.target.id
                list_values = self.var_tracker.resolve_list(iter_name)
                if list_values:
                    self._comprehension_vars[target_name] = list_values
        
        self.generic_visit(node)
        
        # 清理迭代变量
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self._comprehension_vars.pop(generator.target.id, None)
    
    def visit_Call(self, node: ast.Call) -> None:
        """访问函数调用，检测环境变量访问"""
        self.generic_visit(node)
        
        # 检测 os.getenv(x) 或 os.environ.get(x)
        if self._is_env_call(node):
            self._handle_env_call(node)
    
    def visit_Subscript(self, node: ast.Subscript) -> None:
        """访问下标访问，检测 os.environ["KEY"]"""
        self.generic_visit(node)
        
        # 检测 os.environ["KEY"]
        if self._is_environ_subscript(node):
            self._handle_environ_subscript(node)
    
    def _is_env_call(self, node: ast.Call) -> bool:
        """判断是否为环境变量调用"""
        func = node.func
        # os.getenv(x)
        if isinstance(func, ast.Attribute):
            if func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
                return True
            # os.environ.get(x)
            if func.attr == "get" and isinstance(func.value, ast.Attribute):
                if func.value.attr == "environ" and isinstance(func.value.value, ast.Name):
                    if func.value.value.id == "os":
                        return True
        return False
    
    def _is_environ_subscript(self, node: ast.Subscript) -> bool:
        """判断是否为 os.environ[x] 访问"""
        value = node.value
        if isinstance(value, ast.Attribute):
            if value.attr == "environ" and isinstance(value.value, ast.Name):
                if value.value.id == "os":
                    return True
        return False
    
    def _handle_env_call(self, node: ast.Call) -> None:
        """处理环境变量调用"""
        if not node.args:
            return
        
        arg = node.args[0]
        env_names = self._resolve_arg(arg, node)
        
        for name in env_names:
            self.env_vars.append(EnvVarUsage(
                name=name,
                file_path=self.file_path,
                line_number=node.lineno,
                column_number=node.col_offset,
                pattern="ast:os.getenv",
                context=self._current_context,
            ))
    
    def _handle_environ_subscript(self, node: ast.Subscript) -> None:
        """处理 os.environ[x] 访问"""
        slice_node = node.slice
        env_names = self._resolve_arg(slice_node, node)
        
        for name in env_names:
            self.env_vars.append(EnvVarUsage(
                name=name,
                file_path=self.file_path,
                line_number=node.lineno,
                column_number=node.col_offset,
                pattern="ast:os.environ[]",
                context=self._current_context,
            ))
    
    def _resolve_arg(self, arg: ast.expr, parent_node: ast.AST) -> list[str]:
        """
        解析参数到环境变量名列表
        
        Returns:
            解析出的环境变量名列表，如果无法解析则返回空列表并记录 unresolved
        """
        # 直接字符串常量
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return [arg.value]
        
        # 变量引用
        if isinstance(arg, ast.Name):
            var_name = arg.id
            
            # 检查是否是列表推导式中的迭代变量
            if var_name in self._comprehension_vars:
                return self._comprehension_vars[var_name]
            
            # 尝试解析变量
            resolved = self.var_tracker.resolve_name(var_name)
            if resolved:
                return [resolved]
            
            # 无法解析的变量引用
            self.unresolved.append(UnresolvedRef(
                file_path=self.file_path,
                line_number=parent_node.lineno,
                column_number=parent_node.col_offset,
                expression=f"variable: {var_name}",
                reason="Variable value not tracked",
            ))
            return []
        
        # 函数调用或其他复杂表达式
        self.unresolved.append(UnresolvedRef(
            file_path=self.file_path,
            line_number=parent_node.lineno,
            column_number=parent_node.col_offset,
            expression=ast.dump(arg)[:100],
            reason="Dynamic expression not supported",
        ))
        return []


def extract_env_vars_ast(content: str, file_path: str) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
    """
    使用 AST 从 Python 代码中提取环境变量引用
    
    Args:
        content: 文件内容
        file_path: 文件路径
    
    Returns:
        (环境变量列表, 未解析引用列表)
    
    Raises:
        SyntaxError: 如果代码有语法错误
    """
    tree = ast.parse(content)
    extractor = ASTEnvVarExtractor(file_path)
    extractor.visit(tree)
    return extractor.env_vars, extractor.unresolved


class ConfigLibraryDetector(ast.NodeVisitor):
    """
    配置库检测器基类
    
    检测主流 Python 配置库的使用：
    - pydantic BaseSettings
    - python-decouple
    - django-environ
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self._imports: dict[str, str] = {}  # 别名 -> 完整模块路径
        self._current_class: Optional[str] = None
        self._environ_instances: set[str] = set()  # 追踪 environ.Env() 实例变量名
    
    def visit_Import(self, node: ast.Import) -> None:
        """追踪 import 语句"""
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """追踪 from ... import 语句"""
        module = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = f"{module}.{alias.name}"
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """追踪赋值语句，检测 environ.Env() 实例"""
        # 检测 env = environ.Env()
        if isinstance(node.value, ast.Call):
            if self._is_environ_env_constructor(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._environ_instances.add(target.id)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """检测 pydantic BaseSettings 子类"""
        if self._is_base_settings_subclass(node):
            self._extract_settings_fields(node)
        
        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class
    
    def visit_Call(self, node: ast.Call) -> None:
        """检测 decouple.config() 和 environ.Env() 调用"""
        self.generic_visit(node)
        
        # 检测 decouple config()
        if self._is_decouple_config(node):
            self._handle_decouple_config(node)
        
        # 检测 django-environ
        if self._is_django_environ_call(node):
            self._handle_django_environ(node)
    
    def _is_base_settings_subclass(self, node: ast.ClassDef) -> bool:
        """判断是否继承自 BaseSettings"""
        for base in node.bases:
            base_name = self._get_full_name(base)
            if base_name in (
                "BaseSettings",
                "pydantic.BaseSettings",
                "pydantic_settings.BaseSettings",
            ):
                return True
            # 检查导入别名
            if base_name and base_name in self._imports:
                full_path = self._imports[base_name]
                if "BaseSettings" in full_path:
                    return True
        return False
    
    def _extract_settings_fields(self, node: ast.ClassDef) -> None:
        """从 BaseSettings 子类提取字段作为环境变量"""
        for item in node.body:
            # 类型注解的属性: field_name: str
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                # 跳过私有字段和 model_config
                if not field_name.startswith("_") and field_name != "model_config":
                    # 转换为大写下划线格式（pydantic 默认行为）
                    env_name = self._to_env_name(field_name)
                    self.env_vars.append(EnvVarUsage(
                        name=env_name,
                        file_path=self.file_path,
                        line_number=item.lineno,
                        column_number=item.col_offset,
                        pattern="pydantic:BaseSettings",
                        source_library="pydantic",
                        context=node.name,
                    ))
    
    def _to_env_name(self, field_name: str) -> str:
        """将字段名转换为环境变量名（大写）"""
        return field_name.upper()
    
    def _is_decouple_config(self, node: ast.Call) -> bool:
        """判断是否为 decouple config() 调用"""
        func = node.func
        # config("KEY")
        if isinstance(func, ast.Name) and func.id == "config":
            if "config" in self._imports:
                full_path = self._imports["config"]
                if "decouple" in full_path:
                    return True
        # decouple.config("KEY")
        if isinstance(func, ast.Attribute) and func.attr == "config":
            if isinstance(func.value, ast.Name) and func.value.id == "decouple":
                return True
        return False
    
    def _handle_decouple_config(self, node: ast.Call) -> None:
        """处理 decouple config() 调用"""
        if not node.args:
            return
        
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            self.env_vars.append(EnvVarUsage(
                name=arg.value,
                file_path=self.file_path,
                line_number=node.lineno,
                column_number=node.col_offset,
                pattern="decouple:config",
                source_library="python-decouple",
                context=self._current_class,
            ))
    
    def _is_django_environ_call(self, node: ast.Call) -> bool:
        """判断是否为 django-environ 调用"""
        func = node.func
        # env.str(), env.int(), env.bool() 等方法调用
        if isinstance(func, ast.Attribute):
            if func.attr in ("str", "int", "bool", "float", "list", "dict", "url", "db_url"):
                if isinstance(func.value, ast.Name):
                    var_name = func.value.id
                    # 检查是否是已追踪的 environ.Env() 实例
                    if var_name in self._environ_instances:
                        return True
                    # 检查是否是导入的 environ 模块
                    if var_name in self._imports:
                        full_path = self._imports.get(var_name, "")
                        if "environ" in full_path.lower():
                            return True
        # 直接 env("KEY") 调用
        if isinstance(func, ast.Name):
            var_name = func.id
            # 检查是否是已追踪的 environ.Env() 实例
            if var_name in self._environ_instances:
                return True
            if var_name in self._imports:
                full_path = self._imports.get(var_name, "")
                if "environ" in full_path.lower():
                    return True
        return False
    
    def _is_environ_env_constructor(self, node: ast.Call) -> bool:
        """判断是否为 environ.Env() 构造函数调用"""
        func = node.func
        # environ.Env()
        if isinstance(func, ast.Attribute) and func.attr == "Env":
            if isinstance(func.value, ast.Name):
                var_name = func.value.id
                if var_name == "environ" or var_name in self._imports:
                    full_path = self._imports.get(var_name, var_name)
                    if "environ" in full_path.lower():
                        return True
        # Env() 直接调用（from environ import Env）
        if isinstance(func, ast.Name) and func.id == "Env":
            if "Env" in self._imports:
                full_path = self._imports["Env"]
                if "environ" in full_path.lower():
                    return True
        return False
    
    def _handle_django_environ(self, node: ast.Call) -> None:
        """处理 django-environ 调用"""
        if not node.args:
            return
        
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            self.env_vars.append(EnvVarUsage(
                name=arg.value,
                file_path=self.file_path,
                line_number=node.lineno,
                column_number=node.col_offset,
                pattern="django-environ",
                source_library="django-environ",
                context=self._current_class,
            ))
    
    def _get_full_name(self, node: ast.expr) -> Optional[str]:
        """获取节点的完整名称"""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            value_name = self._get_full_name(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
        return None


def extract_config_library_env_vars(content: str, file_path: str) -> list[EnvVarUsage]:
    """
    从配置库使用中提取环境变量
    
    支持：
    - pydantic BaseSettings
    - python-decouple
    - django-environ
    
    Args:
        content: 文件内容
        file_path: 文件路径
    
    Returns:
        环境变量列表
    
    Raises:
        SyntaxError: 如果代码有语法错误
    """
    tree = ast.parse(content)
    detector = ConfigLibraryDetector(file_path)
    detector.visit(tree)
    return detector.env_vars


# ============================================================================
# JS/TS AST 环境变量提取
# ============================================================================

# 尝试导入 esprima，如果失败则禁用 JS AST
try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False
    logger.warning("esprima not installed, JS AST parsing disabled")


class JSVariableTracker:
    """
    JS 变量追踪器 - 追踪字符串变量赋值用于解析间接引用
    
    支持追踪：
    - const key = "API_KEY"
    - let key = "API_KEY"
    - var key = "API_KEY"
    - const keys = ["A", "B", "C"]
    """
    
    def __init__(self):
        self.string_vars: dict[str, str] = {}  # 变量名 -> 字符串值
        self.list_vars: dict[str, list[str]] = {}  # 变量名 -> 字符串列表
    
    def track_declaration(self, node: dict) -> None:
        """追踪变量声明"""
        if node.get("type") != "VariableDeclaration":
            return
        
        for decl in node.get("declarations", []):
            if decl.get("type") != "VariableDeclarator":
                continue
            
            id_node = decl.get("id", {})
            init_node = decl.get("init")
            
            if id_node.get("type") != "Identifier" or not init_node:
                continue
            
            var_name = id_node.get("name")
            
            # 字符串字面量
            if init_node.get("type") == "Literal" and isinstance(init_node.get("value"), str):
                self.string_vars[var_name] = init_node["value"]
            
            # 模板字符串（无表达式）
            elif init_node.get("type") == "TemplateLiteral":
                quasis = init_node.get("quasis", [])
                if len(quasis) == 1 and not init_node.get("expressions"):
                    self.string_vars[var_name] = quasis[0].get("value", {}).get("raw", "")
            
            # 数组字面量
            elif init_node.get("type") == "ArrayExpression":
                strings = []
                for elem in init_node.get("elements", []):
                    if elem and elem.get("type") == "Literal" and isinstance(elem.get("value"), str):
                        strings.append(elem["value"])
                if strings:
                    self.list_vars[var_name] = strings
    
    def resolve_name(self, name: str) -> Optional[str]:
        """解析变量名到字符串值"""
        return self.string_vars.get(name)
    
    def resolve_list(self, name: str) -> Optional[list[str]]:
        """解析变量名到字符串列表"""
        return self.list_vars.get(name)


class JSEnvVarExtractor:
    """
    JS/TS 环境变量提取器
    
    使用 esprima 解析 JavaScript 代码，提取环境变量引用，支持：
    - 直接引用: process.env.KEY
    - 下标引用: process.env["KEY"]
    - 间接引用: const key = "API_KEY"; process.env[key]
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self.unresolved: list[UnresolvedRef] = []
        self.var_tracker = JSVariableTracker()
        self._current_context: Optional[str] = None
    
    def extract(self, content: str) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
        """
        解析 JS 代码提取环境变量
        
        Args:
            content: JS 代码内容
        
        Returns:
            (环境变量列表, 未解析引用列表)
        """
        if not ESPRIMA_AVAILABLE:
            return [], []
        
        try:
            # 使用 tolerant 模式允许部分语法错误
            ast_tree = esprima.parseScript(content, {"tolerant": True, "loc": True})
            self._collect_variables(ast_tree.toDict())
            self._visit(ast_tree.toDict())
            return self.env_vars, self.unresolved
        except Exception as e:
            logger.debug(f"JS AST parsing failed for {self.file_path}: {e}")
            return [], []
    
    def _collect_variables(self, node: dict) -> None:
        """第一遍：收集所有变量声明"""
        if not isinstance(node, dict):
            return
        
        if node.get("type") == "VariableDeclaration":
            self.var_tracker.track_declaration(node)
        
        # 递归遍历子节点
        for key, value in node.items():
            if isinstance(value, dict):
                self._collect_variables(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._collect_variables(item)
    
    def _visit(self, node: dict) -> None:
        """第二遍：查找 process.env 访问"""
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # 追踪函数上下文
        if node_type in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
            old_context = self._current_context
            id_node = node.get("id")
            if id_node and id_node.get("type") == "Identifier":
                self._current_context = id_node.get("name")
            self._visit_children(node)
            self._current_context = old_context
            return
        
        # 检测 process.env.KEY (MemberExpression)
        if node_type == "MemberExpression":
            self._handle_member_expression(node)
        
        # 检测 configService.get("KEY") (CallExpression)
        if node_type == "CallExpression":
            self._handle_call_expression(node)
        
        self._visit_children(node)
    
    def _visit_children(self, node: dict) -> None:
        """递归访问子节点"""
        for key, value in node.items():
            if key in ("loc", "range"):
                continue
            if isinstance(value, dict):
                self._visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._visit(item)
    
    def _handle_member_expression(self, node: dict) -> None:
        """处理 MemberExpression: process.env.KEY 或 process.env["KEY"]"""
        obj = node.get("object", {})
        prop = node.get("property", {})
        computed = node.get("computed", False)
        
        # 检查是否是 process.env.X 或 process.env[X]
        if not self._is_process_env(obj):
            return
        
        loc = node.get("loc", {}).get("start", {})
        line = loc.get("line", 1)
        col = loc.get("column", 0)
        
        # process.env.KEY (非计算属性)
        if not computed and prop.get("type") == "Identifier":
            env_name = prop.get("name")
            if env_name:
                self.env_vars.append(EnvVarUsage(
                    name=env_name,
                    file_path=self.file_path,
                    line_number=line,
                    column_number=col,
                    pattern="ast:process.env.X",
                    context=self._current_context,
                ))
        
        # process.env["KEY"] (计算属性，字符串字面量)
        elif computed and prop.get("type") == "Literal" and isinstance(prop.get("value"), str):
            env_name = prop["value"]
            self.env_vars.append(EnvVarUsage(
                name=env_name,
                file_path=self.file_path,
                line_number=line,
                column_number=col,
                pattern="ast:process.env[]",
                context=self._current_context,
            ))
        
        # process.env[variable] (计算属性，变量引用)
        elif computed and prop.get("type") == "Identifier":
            var_name = prop.get("name")
            resolved = self.var_tracker.resolve_name(var_name)
            if resolved:
                self.env_vars.append(EnvVarUsage(
                    name=resolved,
                    file_path=self.file_path,
                    line_number=line,
                    column_number=col,
                    pattern="ast:process.env[var]",
                    context=self._current_context,
                ))
            else:
                self.unresolved.append(UnresolvedRef(
                    file_path=self.file_path,
                    line_number=line,
                    column_number=col,
                    expression=f"process.env[{var_name}]",
                    reason="Variable value not tracked",
                ))
        
        # process.env[expression] (其他复杂表达式)
        elif computed:
            self.unresolved.append(UnresolvedRef(
                file_path=self.file_path,
                line_number=line,
                column_number=col,
                expression="process.env[<dynamic>]",
                reason="Dynamic expression not supported",
            ))
    
    def _handle_call_expression(self, node: dict) -> None:
        """处理 CallExpression: configService.get("KEY")"""
        callee = node.get("callee", {})
        args = node.get("arguments", [])
        
        if not args:
            return
        
        loc = node.get("loc", {}).get("start", {})
        line = loc.get("line", 1)
        col = loc.get("column", 0)
        
        # configService.get("KEY") 或 configService.getOrThrow("KEY")
        if callee.get("type") == "MemberExpression":
            obj = callee.get("object", {})
            prop = callee.get("property", {})
            
            if prop.get("type") == "Identifier" and prop.get("name") in ("get", "getOrThrow"):
                obj_name = obj.get("name", "") if obj.get("type") == "Identifier" else ""
                # 检查是否像 configService
                if "config" in obj_name.lower() or "env" in obj_name.lower():
                    first_arg = args[0]
                    if first_arg.get("type") == "Literal" and isinstance(first_arg.get("value"), str):
                        self.env_vars.append(EnvVarUsage(
                            name=first_arg["value"],
                            file_path=self.file_path,
                            line_number=line,
                            column_number=col,
                            pattern="ast:configService.get",
                            source_library="nestjs-config",
                            context=self._current_context,
                        ))
    
    def _is_process_env(self, node: dict) -> bool:
        """判断节点是否为 process.env"""
        if node.get("type") != "MemberExpression":
            return False
        
        obj = node.get("object", {})
        prop = node.get("property", {})
        
        return (
            obj.get("type") == "Identifier" and
            obj.get("name") == "process" and
            prop.get("type") == "Identifier" and
            prop.get("name") == "env"
        )


def extract_env_vars_js_ast(content: str, file_path: str) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
    """
    使用 AST 从 JS/TS 代码中提取环境变量引用
    
    Args:
        content: 文件内容
        file_path: 文件路径
    
    Returns:
        (环境变量列表, 未解析引用列表)
    """
    extractor = JSEnvVarExtractor(file_path)
    return extractor.extract(content)


# 环境变量提取模式
ENV_VAR_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        # os.getenv("KEY") or os.getenv('KEY')
        (re.compile(r'os\.getenv\s*\(\s*["\'](\w+)["\']'), 1),
        # os.environ["KEY"] or os.environ['KEY']
        (re.compile(r'os\.environ\s*\[\s*["\'](\w+)["\']'), 1),
        # os.environ.get("KEY")
        (re.compile(r'os\.environ\.get\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        # process.env.KEY
        (re.compile(r'process\.env\.(\w+)'), 1),
        # process.env["KEY"] or process.env['KEY']
        (re.compile(r'process\.env\s*\[\s*["\'](\w+)["\']'), 1),
    ],
    "go": [
        # os.Getenv("KEY")
        (re.compile(r'os\.Getenv\s*\(\s*["\'](\w+)["\']'), 1),
        # os.LookupEnv("KEY")
        (re.compile(r'os\.LookupEnv\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "c": [
        # getenv("KEY")
        (re.compile(r'\bgetenv\s*\(\s*["\'](\w+)["\']'), 1),
        # std::getenv("KEY")
        (re.compile(r'std::getenv\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "java": [
        # System.getenv("KEY")
        (re.compile(r'System\.getenv\s*\(\s*["\'](\w+)["\']'), 1),
        # System.getProperty("KEY")
        (re.compile(r'System\.getProperty\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "rust": [
        # std::env::var("KEY")
        (re.compile(r'std::env::var\s*\(\s*["\'](\w+)["\']'), 1),
        # env::var("KEY")
        (re.compile(r'\benv::var\s*\(\s*["\'](\w+)["\']'), 1),
        # std::env::var_os("KEY")
        (re.compile(r'std::env::var_os\s*\(\s*["\'](\w+)["\']'), 1),
        # env::var_os("KEY")
        (re.compile(r'\benv::var_os\s*\(\s*["\'](\w+)["\']'), 1),
    ],
}

# 系统依赖提取模式
SYSTEM_DEP_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        # subprocess.run(["ffmpeg", ...]) or subprocess.run("ffmpeg", ...)
        (re.compile(r'subprocess\.(?:run|call|Popen)\s*\(\s*\[?\s*["\'](\w+)["\']'), 1),
        # os.system("ffmpeg ...")
        (re.compile(r'os\.system\s*\(\s*["\'](\w+)'), 1),
        # shutil.which("ffmpeg")
        (re.compile(r'shutil\.which\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "javascript": [
        # exec("ffmpeg ...") or execSync("ffmpeg ...")
        (re.compile(r'exec(?:Sync)?\s*\(\s*["\'](\w+)'), 1),
        # spawn("ffmpeg", [...])
        (re.compile(r'spawn\s*\(\s*["\'](\w+)["\']'), 1),
        # child_process.exec("ffmpeg")
        (re.compile(r'child_process\.exec\s*\(\s*["\'](\w+)'), 1),
    ],
    "go": [
        # exec.Command("ffmpeg", ...)
        (re.compile(r'exec\.Command\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "c": [
        # system("ffmpeg ...")
        (re.compile(r'\bsystem\s*\(\s*["\'](\w+)'), 1),
        # popen("ffmpeg ...")
        (re.compile(r'\bpopen\s*\(\s*["\'](\w+)'), 1),
        # execl("/usr/bin/ffmpeg", ...)
        (re.compile(r'\bexecl?\s*\(\s*["\'][^"\']*?(\w+)["\']'), 1),
    ],
    "java": [
        # Runtime.getRuntime().exec("ffmpeg")
        (re.compile(r'\.exec\s*\(\s*["\'](\w+)'), 1),
        # ProcessBuilder("ffmpeg", ...)
        (re.compile(r'ProcessBuilder\s*\(\s*["\'](\w+)["\']'), 1),
    ],
    "rust": [
        # Command::new("ffmpeg")
        (re.compile(r'Command::new\s*\(\s*["\'](\w+)["\']'), 1),
        # process::Command::new("ffmpeg")
        (re.compile(r'process::Command::new\s*\(\s*["\'](\w+)["\']'), 1),
    ],
}

# 文件扩展名到语言的映射
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".jsx": "javascript",
    ".tsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".c": "c",
    ".cpp": "c",
    ".cc": "c",
    ".cxx": "c",
    ".h": "c",
    ".hpp": "c",
    ".hxx": "c",
    ".java": "java",
    ".rs": "rust",
}

# 常见的系统工具（用于过滤）
COMMON_SYSTEM_TOOLS: set[str] = {
    "ffmpeg", "ffprobe", "imagemagick", "convert", "graphviz", "dot",
    "docker", "kubectl", "terraform", "ansible",
    "git", "curl", "wget", "tar", "zip", "unzip",
    "gcc", "g++", "clang", "make", "cmake",
    "python", "python3", "node", "npm", "yarn",
    "java", "javac", "mvn", "gradle",
    "ruby", "gem", "bundle",
    "go", "cargo", "rustc",
    "mysql", "psql", "redis-cli", "mongo",
}


@dataclass
class PackageManagerPattern:
    """
    包管理器模式定义
    
    Attributes:
        name: 包管理器名称 (apt, brew, docker, nix, pacman)
        install_patterns: 安装命令的正则表达式列表
    """
    name: str
    install_patterns: list[re.Pattern]


# 多包管理器支持
PACKAGE_MANAGERS: list[PackageManagerPattern] = [
    PackageManagerPattern(
        name="apt",
        install_patterns=[
            re.compile(r'apt(?:-get)?\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+apt(?:-get)?\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="brew",
        install_patterns=[
            re.compile(r'brew\s+install\s+(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="docker",
        install_patterns=[
            # Dockerfile RUN commands
            re.compile(r'RUN\s+apt-get\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'RUN\s+apk\s+add\s+(?:--no-cache\s+)?(.+)', re.IGNORECASE),
            re.compile(r'RUN\s+yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="nix",
        install_patterns=[
            re.compile(r'nix-env\s+-i\s+(.+)', re.IGNORECASE),
            re.compile(r'nix\s+profile\s+install\s+(.+)', re.IGNORECASE),
            re.compile(r'nix-shell\s+-p\s+(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="pacman",
        install_patterns=[
            re.compile(r'pacman\s+-S\s+(?:--noconfirm\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+pacman\s+-S\s+(?:--noconfirm\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="yum",
        install_patterns=[
            re.compile(r'yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+yum\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
    PackageManagerPattern(
        name="dnf",
        install_patterns=[
            re.compile(r'dnf\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
            re.compile(r'sudo\s+dnf\s+install\s+(?:-y\s+)?(.+)', re.IGNORECASE),
        ]
    ),
]


def extract_documented_packages(content: str) -> dict[str, set[str]]:
    """
    从 README 或 Dockerfile 内容中提取已文档化的包
    
    Args:
        content: 文档内容
    
    Returns:
        字典，键为包管理器名称，值为包名集合
    """
    documented: dict[str, set[str]] = {}
    
    for pm in PACKAGE_MANAGERS:
        packages: set[str] = set()
        for pattern in pm.install_patterns:
            for match in pattern.finditer(content):
                # 提取包名列表（可能是空格分隔的多个包）
                pkg_str = match.group(1).strip()
                # 移除常见的命令行选项
                pkg_str = re.sub(r'\s+&&.*', '', pkg_str)  # 移除 && 后的内容
                pkg_str = re.sub(r'\s+\\$', '', pkg_str)   # 移除行尾的 \
                pkg_str = re.sub(r'\s*#.*', '', pkg_str)   # 移除注释
                
                # 分割并清理包名
                for pkg in pkg_str.split():
                    # 跳过选项（以 - 开头）
                    if pkg.startswith('-'):
                        continue
                    # 移除版本号（如 package=1.0）
                    pkg = re.sub(r'[=<>].*', '', pkg)
                    if pkg:
                        packages.add(pkg.lower())
        
        if packages:
            documented[pm.name] = packages
    
    return documented


def is_package_documented(package_name: str, documented_packages: dict[str, set[str]]) -> bool:
    """
    检查包是否在任何包管理器中被文档化
    
    Args:
        package_name: 包名
        documented_packages: 已文档化的包字典
    
    Returns:
        是否已文档化
    """
    pkg_lower = package_name.lower()
    for packages in documented_packages.values():
        if pkg_lower in packages:
            return True
    return False


def get_documented_package_managers(package_name: str, documented_packages: dict[str, set[str]]) -> list[str]:
    """
    获取文档化了指定包的包管理器列表
    
    Args:
        package_name: 包名
        documented_packages: 已文档化的包字典
    
    Returns:
        包管理器名称列表
    """
    pkg_lower = package_name.lower()
    managers = []
    for pm_name, packages in documented_packages.items():
        if pkg_lower in packages:
            managers.append(pm_name)
    return managers


def _is_comment_line(line: str, language: str) -> bool:
    """判断是否为注释行"""
    stripped = line.strip()
    if language == "python":
        return stripped.startswith('#')
    elif language in ("javascript", "go"):
        return stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*')
    return False


def extract_env_vars_smart(
    content: str,
    file_path: str,
    language: str,
    file_size: int = 0,
) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
    """
    智能提取环境变量 - AST 优先，正则回退
    
    对于 Python 文件：
    1. 如果文件 > 10MB，跳过 AST，直接用正则
    2. 尝试 AST 解析 + 配置库检测
    3. 如果 AST 失败（语法错误），回退到正则
    
    对于 JavaScript/TypeScript 文件：
    1. 如果 esprima 可用，使用 JS AST 解析
    2. 如果 AST 失败，回退到正则
    
    对于其他语言：直接用正则
    
    Args:
        content: 文件内容
        file_path: 文件路径
        language: 编程语言
        file_size: 文件大小（字节）
    
    Returns:
        (环境变量列表, 未解析引用列表)
    """
    unresolved: list[UnresolvedRef] = []
    
    # JavaScript/TypeScript 文件
    if language == "javascript":
        if ESPRIMA_AVAILABLE and file_size <= AST_FILE_SIZE_LIMIT:
            js_env_vars, js_unresolved = extract_env_vars_js_ast(content, file_path)
            if js_env_vars or js_unresolved:
                # AST 成功，返回结果
                return js_env_vars, js_unresolved
        # AST 失败或不可用，回退到正则
        return extract_env_vars(content, file_path, language), unresolved
    
    # 非 Python 文件直接用正则
    if language != "python":
        return extract_env_vars(content, file_path, language), unresolved
    
    # 大文件跳过 AST
    if file_size > AST_FILE_SIZE_LIMIT:
        logger.warning(f"File {file_path} exceeds {AST_FILE_SIZE_LIMIT} bytes, using regex fallback")
        return extract_env_vars(content, file_path, language), unresolved
    
    # 尝试 AST 解析
    try:
        # AST 环境变量提取
        ast_env_vars, ast_unresolved = extract_env_vars_ast(content, file_path)
        unresolved.extend(ast_unresolved)
        
        # 配置库检测
        config_env_vars = extract_config_library_env_vars(content, file_path)
        
        # 合并结果（去重）
        seen_names: set[str] = set()
        all_env_vars: list[EnvVarUsage] = []
        
        for ev in ast_env_vars + config_env_vars:
            key = (ev.name, ev.file_path, ev.line_number)
            if key not in seen_names:
                seen_names.add(key)
                all_env_vars.append(ev)
        
        return all_env_vars, unresolved
        
    except SyntaxError as e:
        # 语法错误，回退到正则
        logger.warning(f"Syntax error in {file_path}, using regex fallback: {e}")
        return extract_env_vars(content, file_path, language), unresolved
    except Exception as e:
        # 其他错误，回退到正则
        logger.warning(f"AST parsing failed for {file_path}, using regex fallback: {e}")
        return extract_env_vars(content, file_path, language), unresolved


def extract_env_vars(content: str, file_path: str, language: str) -> list[EnvVarUsage]:
    """
    从代码中提取环境变量引用
    
    Args:
        content: 文件内容
        file_path: 文件路径
        language: 编程语言
    
    Returns:
        环境变量使用列表
    """
    env_vars: list[EnvVarUsage] = []
    
    patterns = ENV_VAR_PATTERNS.get(language, [])
    if not patterns:
        return env_vars
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过注释行
        if _is_comment_line(line, language):
            continue
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(line):
                var_name = match.group(group_idx)
                env_vars.append(EnvVarUsage(
                    name=var_name,
                    file_path=file_path,
                    line_number=line_num,
                    column_number=match.start(),
                    pattern=pattern.pattern,
                ))
    
    return env_vars


def extract_system_deps(content: str, file_path: str, language: str) -> list[SystemDependency]:
    """
    从代码中提取系统依赖调用
    
    Args:
        content: 文件内容
        file_path: 文件路径
        language: 编程语言
    
    Returns:
        系统依赖列表
    """
    deps: list[SystemDependency] = []
    
    patterns = SYSTEM_DEP_PATTERNS.get(language, [])
    if not patterns:
        return deps
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # 跳过注释行
        if _is_comment_line(line, language):
            continue
        
        for pattern, group_idx in patterns:
            for match in pattern.finditer(line):
                tool_name = match.group(group_idx)
                # 只记录常见的系统工具
                if tool_name.lower() in COMMON_SYSTEM_TOOLS:
                    deps.append(SystemDependency(
                        tool_name=tool_name,
                        file_path=file_path,
                        line_number=line_num,
                        invocation=line.strip()[:100],
                    ))
    
    return deps


from typing import Callable

# 进度回调类型: (file_path: str, language: str) -> None
ProgressCallback = Callable[[str, str], None]


def scan_code_files(
    repo_path: Path,
    extensions: Optional[list[str]] = None,
    use_ast: bool = True,
    on_file: Optional[ProgressCallback] = None,
) -> ScanResult:
    """
    扫描代码文件
    
    Args:
        repo_path: 仓库根目录
        extensions: 要扫描的文件扩展名（默认为所有支持的扩展名）
        use_ast: 是否使用 AST 解析（默认 True，对 Python 文件启用智能解析）
        on_file: 可选的进度回调函数，每扫描一个文件时调用
    
    Returns:
        扫描结果
    """
    result = ScanResult()
    
    if extensions is None:
        extensions = list(EXTENSION_TO_LANGUAGE.keys())
    
    # 要忽略的目录
    ignore_dirs = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', 'target', 'vendor',
    }
    
    def safe_walk(path: Path):
        """安全遍历目录，跳过忽略的目录和无法访问的路径"""
        try:
            for entry in path.iterdir():
                try:
                    if entry.is_dir():
                        if entry.name not in ignore_dirs:
                            yield from safe_walk(entry)
                    elif entry.is_file():
                        yield entry
                except (OSError, PermissionError):
                    # 跳过无法访问的路径（如 Windows 长路径问题）
                    continue
        except (OSError, PermissionError):
            return
    
    for file_path in safe_walk(repo_path):
        # 检查扩展名
        if file_path.suffix.lower() not in extensions:
            continue
        
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if not language:
            continue
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            file_size = file_path.stat().st_size
        except Exception:
            continue
        
        rel_path = str(file_path.relative_to(repo_path))
        
        # 调用进度回调
        if on_file:
            on_file(rel_path, language)
        
        # 提取环境变量（智能模式或正则模式）
        if use_ast:
            env_vars, unresolved = extract_env_vars_smart(content, rel_path, language, file_size)
            result.env_vars.extend(env_vars)
            result.unresolved_refs.extend(unresolved)
        else:
            env_vars = extract_env_vars(content, rel_path, language)
            result.env_vars.extend(env_vars)
        
        # 提取系统依赖
        deps = extract_system_deps(content, rel_path, language)
        result.system_deps.extend(deps)
    
    return result


def format_env_var(env_var: EnvVarUsage, ide_format: bool = False) -> str:
    """
    将 EnvVarUsage 格式化为字符串
    
    Args:
        env_var: EnvVarUsage 对象
        ide_format: 是否使用 IDE 兼容格式 (file:line:column: message)
    
    Returns:
        格式化的字符串
    """
    if ide_format:
        # IDE 兼容格式：file:line:column: ENV_VAR_NAME
        return f"{env_var.file_path}:{env_var.line_number}:{env_var.column_number}: {env_var.name}"
    return f"{env_var.name} ({env_var.file_path}:{env_var.line_number})"


# ============================================================================
# DotEnv 文件解析
# ============================================================================

@dataclass
class DotEnvEntry:
    """
    dotenv 文件条目
    
    Attributes:
        name: 变量名
        value: 值（可选）
        comment: 注释（可选）
        line_number: 行号
        file_path: 来源文件
    """
    name: str
    value: Optional[str] = None
    comment: Optional[str] = None
    line_number: int = 0
    file_path: str = ""


# .env 文件名模式
DOTENV_FILE_PATTERNS = [
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.development.example",
    ".env.production.example",
    ".env.local.example",
    ".env.test.example",
]


def parse_dotenv_file(file_path: Path) -> list[DotEnvEntry]:
    """
    解析 .env 文件
    
    支持格式:
    - KEY=value
    - KEY="quoted value"
    - KEY='single quoted'
    - # comment
    - KEY=value # inline comment
    - export KEY=value
    
    Args:
        file_path: .env 文件路径
    
    Returns:
        DotEnvEntry 列表
    """
    entries: list[DotEnvEntry] = []
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return entries
    
    # 正则匹配 .env 行
    # 支持: KEY=value, export KEY=value, KEY="value", KEY='value'
    line_pattern = re.compile(
        r'^(?:export\s+)?'  # 可选的 export
        r'([A-Za-z_][A-Za-z0-9_]*)'  # 变量名
        r'\s*=\s*'  # 等号
        r'(?:'
        r'"([^"]*)"'  # 双引号值
        r"|'([^']*)'"  # 单引号值
        r'|([^#\n]*?)'  # 无引号值
        r')'
        r'(?:\s*#\s*(.*))?$'  # 可选的行内注释
    )
    
    comment_pattern = re.compile(r'^\s*#\s*(.*)$')
    
    pending_comment: Optional[str] = None
    
    for line_num, line in enumerate(content.split('\n'), 1):
        line = line.strip()
        
        # 空行
        if not line:
            pending_comment = None
            continue
        
        # 纯注释行（可能是下一个变量的描述）
        comment_match = comment_pattern.match(line)
        if comment_match and '=' not in line:
            pending_comment = comment_match.group(1).strip()
            continue
        
        # 变量定义行
        match = line_pattern.match(line)
        if match:
            name = match.group(1)
            # 值可能在 group 2, 3, 或 4
            value = match.group(2) or match.group(3) or (match.group(4).strip() if match.group(4) else None)
            inline_comment = match.group(5)
            
            # 使用行内注释或之前的注释
            comment = inline_comment.strip() if inline_comment else pending_comment
            
            entries.append(DotEnvEntry(
                name=name,
                value=value,
                comment=comment,
                line_number=line_num,
                file_path=str(file_path),
            ))
            
            pending_comment = None
    
    return entries


def parse_dotenv_content(content: str, file_path: str = "") -> list[DotEnvEntry]:
    """
    解析 .env 文件内容字符串
    
    Args:
        content: .env 文件内容
        file_path: 文件路径（用于记录）
    
    Returns:
        DotEnvEntry 列表
    """
    entries: list[DotEnvEntry] = []
    
    line_pattern = re.compile(
        r'^(?:export\s+)?'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'\s*=\s*'
        r'(?:'
        r'"([^"]*)"'
        r"|'([^']*)'"
        r'|([^#\n]*?)'
        r')'
        r'(?:\s*#\s*(.*))?$'
    )
    
    comment_pattern = re.compile(r'^\s*#\s*(.*)$')
    pending_comment: Optional[str] = None
    
    for line_num, line in enumerate(content.split('\n'), 1):
        line = line.strip()
        
        if not line:
            pending_comment = None
            continue
        
        comment_match = comment_pattern.match(line)
        if comment_match and '=' not in line:
            pending_comment = comment_match.group(1).strip()
            continue
        
        match = line_pattern.match(line)
        if match:
            name = match.group(1)
            value = match.group(2) or match.group(3) or (match.group(4).strip() if match.group(4) else None)
            inline_comment = match.group(5)
            comment = inline_comment.strip() if inline_comment else pending_comment
            
            entries.append(DotEnvEntry(
                name=name,
                value=value,
                comment=comment,
                line_number=line_num,
                file_path=file_path,
            ))
            pending_comment = None
    
    return entries


def collect_documented_env_vars(repo_path: Path) -> dict[str, list[str]]:
    """
    收集所有文档来源中的环境变量
    
    来源:
    1. .env.example 等文件
    
    Args:
        repo_path: 仓库根目录
    
    Returns:
        字典，键为变量名，值为来源文件列表
    """
    documented: dict[str, list[str]] = {}
    
    for pattern in DOTENV_FILE_PATTERNS:
        env_file = repo_path / pattern
        if env_file.exists():
            entries = parse_dotenv_file(env_file)
            for entry in entries:
                if entry.name not in documented:
                    documented[entry.name] = []
                documented[entry.name].append(entry.file_path)
    
    return documented


def get_documented_env_var_names(repo_path: Path) -> set[str]:
    """
    获取所有文档化的环境变量名称
    
    Args:
        repo_path: 仓库根目录
    
    Returns:
        环境变量名称集合
    """
    documented = collect_documented_env_vars(repo_path)
    return set(documented.keys())
