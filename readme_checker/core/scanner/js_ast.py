"""
JavaScript AST 环境变量提取

使用 esprima 解析 JavaScript 代码，支持：
- 直接引用: process.env.KEY
- 下标引用: process.env["KEY"]
- 间接引用: const key = "API_KEY"; process.env[key]
"""

import logging
from typing import Optional

from readme_checker.core.scanner.models import EnvVarUsage, UnresolvedRef

logger = logging.getLogger(__name__)

# 尝试导入 esprima
try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False
    logger.warning("esprima not installed, JS AST parsing disabled")


class JSVariableTracker:
    """JS 变量追踪器"""
    
    def __init__(self):
        self.string_vars: dict[str, str] = {}
        self.list_vars: dict[str, list[str]] = {}
    
    def track_declaration(self, node: dict) -> None:
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
            if init_node.get("type") == "Literal" and isinstance(init_node.get("value"), str):
                self.string_vars[var_name] = init_node["value"]
            elif init_node.get("type") == "TemplateLiteral":
                quasis = init_node.get("quasis", [])
                if len(quasis) == 1 and not init_node.get("expressions"):
                    self.string_vars[var_name] = quasis[0].get("value", {}).get("raw", "")
            elif init_node.get("type") == "ArrayExpression":
                strings = []
                for elem in init_node.get("elements", []):
                    if elem and elem.get("type") == "Literal" and isinstance(elem.get("value"), str):
                        strings.append(elem["value"])
                if strings:
                    self.list_vars[var_name] = strings
    
    def resolve_name(self, name: str) -> Optional[str]:
        return self.string_vars.get(name)
    
    def resolve_list(self, name: str) -> Optional[list[str]]:
        return self.list_vars.get(name)


class JSEnvVarExtractor:
    """JS/TS 环境变量提取器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars: list[EnvVarUsage] = []
        self.unresolved: list[UnresolvedRef] = []
        self.var_tracker = JSVariableTracker()
        self._current_context: Optional[str] = None
    
    def extract(self, content: str) -> tuple[list[EnvVarUsage], list[UnresolvedRef]]:
        if not ESPRIMA_AVAILABLE:
            return [], []
        try:
            ast_tree = esprima.parseScript(content, {"tolerant": True, "loc": True})
            self._collect_variables(ast_tree.toDict())
            self._visit(ast_tree.toDict())
            return self.env_vars, self.unresolved
        except Exception as e:
            logger.debug(f"JS AST parsing failed for {self.file_path}: {e}")
            return [], []
    
    def _collect_variables(self, node: dict) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "VariableDeclaration":
            self.var_tracker.track_declaration(node)
        for key, value in node.items():
            if isinstance(value, dict):
                self._collect_variables(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._collect_variables(item)
    
    def _visit(self, node: dict) -> None:
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
            old_context = self._current_context
            id_node = node.get("id")
            if id_node and id_node.get("type") == "Identifier":
                self._current_context = id_node.get("name")
            self._visit_children(node)
            self._current_context = old_context
            return
        if node_type == "MemberExpression":
            self._handle_member_expression(node)
        if node_type == "CallExpression":
            self._handle_call_expression(node)
        self._visit_children(node)
    
    def _visit_children(self, node: dict) -> None:
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
        obj = node.get("object", {})
        prop = node.get("property", {})
        computed = node.get("computed", False)
        if not self._is_process_env(obj):
            return
        loc = node.get("loc", {}).get("start", {})
        line = loc.get("line", 1)
        col = loc.get("column", 0)
        
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
        elif computed:
            self.unresolved.append(UnresolvedRef(
                file_path=self.file_path,
                line_number=line,
                column_number=col,
                expression="process.env[<dynamic>]",
                reason="Dynamic expression not supported",
            ))
    
    def _handle_call_expression(self, node: dict) -> None:
        callee = node.get("callee", {})
        args = node.get("arguments", [])
        if not args:
            return
        loc = node.get("loc", {}).get("start", {})
        line = loc.get("line", 1)
        col = loc.get("column", 0)
        
        if callee.get("type") == "MemberExpression":
            obj = callee.get("object", {})
            prop = callee.get("property", {})
            if prop.get("type") == "Identifier" and prop.get("name") in ("get", "getOrThrow"):
                obj_name = obj.get("name", "") if obj.get("type") == "Identifier" else ""
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
    """使用 AST 从 JS/TS 代码中提取环境变量引用"""
    extractor = JSEnvVarExtractor(file_path)
    return extractor.extract(content)
