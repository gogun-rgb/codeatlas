from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tree_sitter_language_pack import get_parser

from app.models.repository import SourceFile
from app.models.symbols import ImportRef, ParsedFile, SymbolInfo, SymbolKind
from app.parsing.base import SymbolExtractor
from app.parsing.tree_sitter_config import ensure_language_pack_configured
from app.parsing.tree_sitter_utils import (
    first_named_child_text,
    node_byte_range,
    node_has_error,
    node_kind,
    node_line_range,
    node_parent,
    node_text,
    walk,
)

IMPORT_RE = re.compile(r"\bimport(?:[\s\w{},*]+from\s*)?[\"']([^\"']+)[\"']", re.DOTALL)
EXPORT_FROM_RE = re.compile(r"\bexport\s+.*?\sfrom\s*[\"']([^\"']+)[\"']", re.DOTALL)
REQUIRE_RE = re.compile(r"\brequire\s*\(\s*[\"']([^\"']+)[\"']\s*\)")
EXPORT_NAME_RE = re.compile(
    r"\bexport\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)"
)
EXPORT_LIST_RE = re.compile(r"\bexport\s*\{([^}]+)\}")
EXPORT_DEFAULT_NAMED_RE = re.compile(
    r"\bexport\s+default\s+(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)"
)
EXPORT_DEFAULT_RE = re.compile(r"\bexport\s+default\b")


@dataclass(frozen=True)
class ExportInfo:
    exported_names: set[str]
    local_names: set[str]


class JavaScriptLikeExtractor(SymbolExtractor):
    def __init__(self, parser_name: str) -> None:
        ensure_language_pack_configured()
        self._parser_name = parser_name
        self._parser: Any = get_parser(parser_name)

    def parse(self, source_file: SourceFile) -> ParsedFile:
        source = source_file.content.encode("utf-8")
        tree: Any = self._parser.parse(source_file.content)
        root: Any = tree.root_node()
        imports: list[ImportRef] = []
        symbols: list[SymbolInfo] = []
        export_info = self._extract_exports(source, root)

        for node in walk(root):
            kind = node_kind(node)
            if kind in {"import_statement", "export_statement"}:
                imports.extend(self._imports_from_statement(source, node))
            elif kind == "call_expression":
                import_ref = self._import_from_require(source, node)
                if import_ref is not None:
                    imports.append(import_ref)
            elif kind == "function_declaration":
                symbol = self._symbol_from_named_node(
                    source, source_file.path, node, SymbolKind.FUNCTION
                )
                if symbol is not None:
                    symbols.append(
                        symbol.model_copy(
                            update={"exported": symbol.name in export_info.local_names}
                        )
                    )
            elif kind == "class_declaration":
                symbol = self._symbol_from_named_node(
                    source, source_file.path, node, SymbolKind.CLASS
                )
                if symbol is not None:
                    symbols.append(
                        symbol.model_copy(
                            update={"exported": symbol.name in export_info.local_names}
                        )
                    )
            elif kind == "method_definition":
                container_name = self._nearest_class_name(source, node)
                symbol = self._symbol_from_named_node(
                    source,
                    source_file.path,
                    node,
                    SymbolKind.FUNCTION,
                    container_name=container_name,
                )
                if symbol is not None:
                    symbols.append(symbol)
            elif kind == "variable_declarator":
                symbol = self._symbol_from_variable(
                    source,
                    source_file.path,
                    node,
                    export_info.local_names,
                )
                if symbol is not None:
                    symbols.append(symbol)

        parser_errors = ["Tree-sitter reported syntax errors."] if node_has_error(root) else []
        return ParsedFile(
            path=source_file.path,
            language=source_file.language.value,
            size=source_file.size,
            imports=dedupe_imports(imports),
            exports=sorted(export_info.exported_names),
            symbols=sorted(symbols, key=lambda item: (item.start_line, item.kind.value, item.name)),
            parser_errors=parser_errors,
        )

    def _imports_from_statement(self, source: bytes, node: Any) -> list[ImportRef]:
        text = node_text(source, node)
        modules = IMPORT_RE.findall(text) + EXPORT_FROM_RE.findall(text)
        line, _ = node_line_range(node)
        return [self._import_ref(module, text, line) for module in modules]

    def _import_from_require(self, source: bytes, node: Any) -> ImportRef | None:
        text = node_text(source, node)
        match = REQUIRE_RE.search(text)
        if match is None:
            return None
        line, _ = node_line_range(node)
        return self._import_ref(match.group(1), text, line)

    def _import_ref(self, module: str, raw: str, line: int) -> ImportRef:
        is_relative = module.startswith(".")
        return ImportRef(
            module=module,
            raw=raw.strip(),
            line=line,
            is_relative=is_relative,
            is_external=not is_relative,
        )

    def _symbol_from_named_node(
        self,
        source: bytes,
        path: str,
        node: Any,
        kind: SymbolKind,
        container_name: str | None = None,
    ) -> SymbolInfo | None:
        name = first_named_child_text(source, node)
        if not name:
            return None
        start_line, end_line = node_line_range(node)
        start_byte, end_byte = node_byte_range(node)
        return SymbolInfo(
            name=name,
            kind=kind,
            path=path,
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            container_name=container_name,
        )

    def _symbol_from_variable(
        self,
        source: bytes,
        path: str,
        node: Any,
        exported_local_names: set[str],
    ) -> SymbolInfo | None:
        value = node.child_by_field_name("value")
        if value is None or node_kind(value) not in {"arrow_function", "function"}:
            return None
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        name = node_text(source, name_node)
        start_line, end_line = node_line_range(node)
        start_byte, end_byte = node_byte_range(node)
        return SymbolInfo(
            name=name,
            kind=SymbolKind.FUNCTION,
            path=path,
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            exported=name in exported_local_names,
        )

    def _extract_exports(self, source: bytes, root: Any) -> ExportInfo:
        exported_names: set[str] = set()
        local_names: set[str] = set()
        for node in walk(root):
            if node_kind(node) != "export_statement":
                continue
            text = node_text(source, node)
            has_export_from = EXPORT_FROM_RE.search(text) is not None
            for name in EXPORT_NAME_RE.findall(text):
                exported_names.add(name)
                local_names.add(name)
            default_match = EXPORT_DEFAULT_NAMED_RE.search(text)
            if default_match is not None:
                exported_names.add("default")
                local_names.add(default_match.group(1))
            elif EXPORT_DEFAULT_RE.search(text) is not None:
                exported_names.add("default")
            for group in EXPORT_LIST_RE.findall(text):
                for item in group.split(","):
                    token = item.strip()
                    if not token:
                        continue
                    local_name, exported_name = self._export_specifier_names(token)
                    exported_names.add(exported_name)
                    if not has_export_from:
                        local_names.add(local_name)
        return ExportInfo(exported_names=exported_names, local_names=local_names)

    def _export_specifier_names(self, token: str) -> tuple[str, str]:
        parts = [part.strip() for part in token.split(" as ", 1)]
        if len(parts) == 2:
            return parts[0], parts[1]
        return token, token

    def _nearest_class_name(self, source: bytes, node: Any) -> str | None:
        parent = node_parent(node)
        while parent is not None:
            if node_kind(parent) == "class_declaration":
                return first_named_child_text(source, parent)
            parent = node_parent(parent)
        return None


def dedupe_imports(imports: list[ImportRef]) -> list[ImportRef]:
    seen: set[tuple[str, int, str]] = set()
    result: list[ImportRef] = []
    for import_ref in imports:
        key = (import_ref.module, import_ref.line, import_ref.raw)
        if key in seen:
            continue
        seen.add(key)
        result.append(import_ref)
    return sorted(result, key=lambda item: (item.line, item.module))
