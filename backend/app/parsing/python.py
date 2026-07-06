from __future__ import annotations

import ast
import re
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


class PythonExtractor(SymbolExtractor):
    def __init__(self) -> None:
        ensure_language_pack_configured()
        self._parser: Any = get_parser("python")

    def parse(self, source_file: SourceFile) -> ParsedFile:
        source = source_file.content.encode("utf-8")
        tree: Any = self._parser.parse(source_file.content)
        root: Any = tree.root_node()
        imports: list[ImportRef] = []
        symbols: list[SymbolInfo] = []

        for node in walk(root):
            kind = node_kind(node)
            if kind in {"import_statement", "import_from_statement"}:
                imports.extend(self._imports_from_statement(source, node))
            elif kind == "function_definition":
                symbol = self._symbol_from_node(
                    source,
                    source_file.path,
                    node,
                    SymbolKind.FUNCTION,
                    container_name=self._nearest_class_name(source, node),
                )
                if symbol is not None:
                    symbols.append(symbol)
            elif kind == "class_definition":
                symbol = self._symbol_from_node(source, source_file.path, node, SymbolKind.CLASS)
                if symbol is not None:
                    symbols.append(symbol)

        parser_errors = ["Tree-sitter reported syntax errors."] if node_has_error(root) else []
        return ParsedFile(
            path=source_file.path,
            language=source_file.language.value,
            size=source_file.size,
            imports=sorted(imports, key=lambda item: (item.line, item.module)),
            exports=self._extract_all(source_file.content),
            symbols=sorted(symbols, key=lambda item: (item.start_line, item.kind.value, item.name)),
            parser_errors=parser_errors,
        )

    def _imports_from_statement(self, source: bytes, node: Any) -> list[ImportRef]:
        text = node_text(source, node).strip()
        line, _ = node_line_range(node)
        try:
            parsed = ast.parse(text)
        except SyntaxError:
            return []

        refs: list[ImportRef] = []
        for item in parsed.body:
            if isinstance(item, ast.Import):
                for alias in item.names:
                    refs.append(
                        ImportRef(
                            module=alias.name,
                            raw=text,
                            line=line,
                            is_relative=False,
                            is_external=True,
                        )
                    )
            elif isinstance(item, ast.ImportFrom):
                is_relative = item.level > 0
                base_module = "." * item.level + (item.module or "")
                for alias in item.names:
                    module = base_module
                    imported_name: str | None = alias.name
                    if is_relative and not item.module:
                        module = "." * item.level + alias.name
                        imported_name = None
                    refs.append(
                        ImportRef(
                            module=module,
                            raw=text,
                            line=line,
                            is_relative=is_relative,
                            is_external=not is_relative,
                            imported_name=imported_name,
                        )
                    )
        return refs

    def _symbol_from_node(
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

    def _extract_all(self, content: str) -> list[str]:
        match = re.search(r"__all__\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
        if match is None:
            return []
        return sorted(re.findall(r"[\"']([^\"']+)[\"']", match.group(1)))

    def _nearest_class_name(self, source: bytes, node: Any) -> str | None:
        parent = node_parent(node)
        while parent is not None:
            if node_kind(parent) == "class_definition":
                return first_named_child_text(source, parent)
            parent = node_parent(parent)
        return None
