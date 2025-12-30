"""
Python AST 环境变量提取

使用 AST 解析 Python 代码，支持：
- 直接引用: os.getenv("KEY")
- 间接引用: key = "API_KEY"; os.getenv(key)
- 配置库: pydantic, decouple, django-environ
"""

import ast
from typing import Optional

from readme_checker.core.scanner.models import EnvVarUsage, UnresolvedRef


class VariableTracker:
    """变量追踪器 - 追踪字符串变量赋值"""
    
    def __init__(self):
        self.string_vars: dict[str, str] = {}
        self.list_vars: dict[str, list[str]] = {}
    
    def track_assignment(self, target: str, value: ast.expr) -> None:
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
        return self.string_vars.get(name)
    
    def resolve_list(self, name: str) -> Optional[list[str]]:
        return self.list_vars.get(name)


class ASTEnvVarExtractor(ast.NodeVisitor):
    """AST 环境变量提取器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self.unresolved: list[UnresolvedRef] = []
        self.var_tracker = VariableTracker()
        self._current_context: Optional[str] = None
        self._comprehension_vars: dict[str, list[str]] = {}
    
    def visit_Module(self, node: ast.Module) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.var_tracker.track_assignment(target.id, child.value)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_context = self._current_context
        self._current_context = node.name
        self.generic_visit(node)
        self._current_context = old_context
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        old_context = self._current_context
        if self._current_context:
            self._current_context = f"{self._current_context}.{node.name}"
        else:
            self._current_context = node.name
        self.generic_visit(node)
        self._current_context = old_context
    
    visit_AsyncFunctionDef = visit_FunctionDef
    
    def visit_ListComp(self, node: ast.ListComp) -> None:
        for generator in node.generators:
            if isinstance(generator.target, ast.Name) and isinstance(generator.iter, ast.Name):
                iter_name = generator.iter.id
                target_name = generator.target.id
                list_values = self.var_tracker.resolve_list(iter_name)
                if list_values:
                    self._comprehension_vars[target_name] = list_values
        self.generic_visit(node)
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self._comprehension_vars.pop(generator.target.id, None)
    
    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        if self._is_env_call(node):
            self._handle_env_call(node)
    
    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.generic_visit(node)
        if self._is_environ_subscript(node):
            self._handle_environ_subscript(node)
    
    def _is_env_call(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
                return True
            if func.attr == "get" and isinstance(func.value, ast.Attribute):
                if func.value.attr == "environ" and isinstance(func.value.value, ast.Name):
                    if func.value.value.id == "os":
                        return True
        return False
    
    def _is_environ_subscript(self, node: ast.Subscript) -> bool:
        value = node.value
        if isinstance(value, ast.Attribute):
            if value.attr == "environ" and isinstance(value.value, ast.Name):
                if value.value.id == "os":
                    return True
        return False
    
    def _handle_env_call(self, node: ast.Call) -> None:
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
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return [arg.value]
        if isinstance(arg, ast.Name):
            var_name = arg.id
            if var_name in self._comprehension_vars:
                return self._comprehension_vars[var_name]
            resolved = self.var_tracker.resolve_name(var_name)
            if resolved:
                return [resolved]
            self.unresolved.append(UnresolvedRef(
                file_path=self.file_path,
                line_number=parent_node.lineno,
                column_number=parent_node.col_offset,
                expression=f"variable: {var_name}",
                reason="Variable value not tracked",
            ))
            return []
        self.unresolved.append(UnresolvedRef(
            file_path=self.file_path,
            line_number=parent_node.lineno,
            column_number=parent_node.col_offset,
            expression=ast.dump(arg)[:100],
            reason="Dynamic expression not supported",
        ))
        return []


class ConfigLibraryDetector(ast.NodeVisitor):
    """配置库检测器 - pydantic, decouple, django-environ"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self._imports: dict[str, str] = {}
        self._current_class: Optional[str] = None
        self._environ_instances: set[str] = set()
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = f"{module}.{alias.name}"
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            if self._is_environ_env_constructor(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._environ_instances.add(target.id)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._is_base_settings_subclass(node):
            self._extract_settings_fields(node)
        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class
    
    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        if self._is_decouple_config(node):
            self._handle_decouple_config(node)
        if self._is_django_environ_call(node):
            self._handle_django_environ(node)
    
    def _is_base_settings_subclass(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            base_name = self._get_full_name(base)
            if base_name in ("BaseSettings", "pydantic.BaseSettings", "pydantic_settings.BaseSettings"):
                return True
            if base_name and base_name in self._imports:
                full_path = self._imports[base_name]
                if "BaseSettings" in full_path:
                    return True
        return False
    
    def _extract_settings_fields(self, node: ast.ClassDef) -> None:
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                if not field_name.startswith("_") and field_name != "model_config":
                    env_name = field_name.upper()
                    self.env_vars.append(EnvVarUsage(
                        name=env_name,
                        file_path=self.file_path,
                        line_number=item.lineno,
                        column_number=item.col_offset,
                        pattern="pydantic:BaseSettings",
                        source_library="pydantic",
                        context=node.name,
                    ))
    
    def _is_decouple_config(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Name) and func.id == "config":
            if "config" in self._imports:
                full_path = self._imports["config"]
                if "decouple" in full_path:
                    return True
        if isinstance(func, ast.Attribute) and func.attr == "config":
            if isinstance(func.value, ast.Name) and func.value.id == "decouple":
                return True
        return False
    
    def _handle_decouple_config(self, node: ast.Call) -> None:
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
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in ("str", "int", "bool", "float", "list", "dict", "url", "db_url"):
                if isinstance(func.value, ast.Name):
                    var_name = func.value.id
                    if var_name in self._environ_instances:
                        return True
                    if var_name in self._imports:
                        full_path = self._imports.get(var_name, "")
                        if "environ" in full_path.lower():
                            return True
        if isinstance(func, ast.Name):
            var_name = func.id
            if var_name in self._environ_instances:
                return True
            if var_name in self._imports:
                full_path = self._imports.get(var_name, "")
                if "environ" in full_path.lower():
                    return True
        return False
    
    def _is_environ_env_constructor(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "Env":
            if isinstance(func.value, ast.Name):
                var_name = func.value.id
                if var_name == "environ" or var_name in self._imports:
                    full_path = self._imports.get(var_name, var_name)
                    if "environ" in full_path.lower():
                        return True
        if isinstance(func, ast.Name) and func.id == "Env":
            if "Env" in self._imports:
                full_path = self._imports["Env"]
                if "environ" in full_path.lower():
                    return True
        return False
    
    def _handle_django_environ(self, node: ast.Call) -> None:
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
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            value_name = self._get_full_name(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
        return None


def extract_env_vars_ast(content: str, file_path: str) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
    """使用 AST 从 Python 代码中提取环境变量引用"""
    tree = ast.parse(content)
    extractor = ASTEnvVarExtractor(file_path)
    extractor.visit(tree)
    return extractor.env_vars, extractor.unresolved


def extract_config_library_env_vars(content: str, file_path: str) -> list[EnvVarUsage]:
    """从配置库使用中提取环境变量"""
    tree = ast.parse(content)
    detector = ConfigLibraryDetector(file_path)
    detector.visit(tree)
    return detector.env_vars
