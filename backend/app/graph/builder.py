from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from app.graph.import_resolution import resolve_import
from app.models.graph import CodeGraph, EdgeType, GraphEdge, GraphNode, NodeType
from app.models.symbols import ImportRef, ParsedFile, SymbolInfo, SymbolKind


class GraphBuilder:
    def build(self, parsed_files: list[ParsedFile], warnings: list[str] | None = None) -> CodeGraph:
        by_path = {parsed.path: parsed for parsed in parsed_files}
        all_paths = set(by_path)
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        file_imports: dict[str, list[ImportRef]] = {}
        imported_by: dict[str, list[str]] = defaultdict(list)

        for parsed in sorted(parsed_files, key=lambda item: item.path):
            resolved_imports: list[ImportRef] = []
            for import_ref in parsed.imports:
                resolved_path = resolve_import(parsed.path, import_ref, all_paths)
                resolved_imports.append(
                    import_ref.model_copy(update={"resolved_path": resolved_path})
                )
                if resolved_path is not None:
                    imported_by[resolved_path].append(parsed.path)
            file_imports[parsed.path] = resolved_imports

        for parsed in sorted(parsed_files, key=lambda item: item.path):
            nodes.append(
                self._file_node(parsed, file_imports[parsed.path], imported_by[parsed.path])
            )
            for symbol in parsed.symbols:
                symbol_node = self._symbol_node(symbol)
                nodes.append(symbol_node)
                source = self._file_id(parsed.path)
                edges.append(
                    GraphEdge(
                        id=f"contains:{source}->{symbol_node.id}",
                        source=source,
                        target=symbol_node.id,
                        type=EdgeType.CONTAINS,
                    )
                )

        for source_path, imports in sorted(file_imports.items()):
            for import_index, import_ref in enumerate(imports):
                if import_ref.resolved_path is None:
                    continue
                source_id = self._file_id(source_path)
                target_id = self._file_id(import_ref.resolved_path)
                edges.append(
                    GraphEdge(
                        id=(
                            f"imports:{source_id}->{target_id}:"
                            f"{import_index}:{import_ref.line}:{import_ref.module}"
                        ),
                        source=source_id,
                        target=target_id,
                        type=EdgeType.IMPORTS,
                        metadata={
                            "module": import_ref.module,
                            "importedName": import_ref.imported_name,
                            "line": import_ref.line,
                        },
                    )
                )

        return CodeGraph(
            nodes=sorted(nodes, key=lambda node: node.id),
            edges=sorted(edges, key=lambda edge: edge.id),
            warnings=warnings or [],
            metadata={"schemaVersion": "0.1.0"},
        )

    def _file_node(
        self,
        parsed: ParsedFile,
        imports: list[ImportRef],
        imported_by: list[str],
    ) -> GraphNode:
        external_imports = sorted(ref.module for ref in imports if ref.is_external)
        unresolved_local = sorted(
            self._import_label(ref)
            for ref in imports
            if ref.is_relative and ref.resolved_path is None
        )
        metadata: dict[str, Any] = {
            "language": parsed.language,
            "size": parsed.size,
            "imports": [ref.model_dump() for ref in imports],
            "exports": parsed.exports,
            "externalImports": external_imports,
            "unresolvedLocalImports": unresolved_local,
            "importedBy": sorted(imported_by),
            "parserErrors": parsed.parser_errors,
        }
        return GraphNode(
            id=self._file_id(parsed.path),
            type=NodeType.FILE,
            label=PurePosixPath(parsed.path).name,
            path=parsed.path,
            metadata=metadata,
        )

    def _symbol_node(self, symbol: SymbolInfo) -> GraphNode:
        node_type = NodeType.FUNCTION if symbol.kind == SymbolKind.FUNCTION else NodeType.CLASS
        metadata = {
            "startLine": symbol.start_line,
            "endLine": symbol.end_line,
            "startByte": symbol.start_byte,
            "endByte": symbol.end_byte,
            "containerName": symbol.container_name,
            "exported": symbol.exported,
        }
        return GraphNode(
            id=self._symbol_id(symbol, node_type),
            type=node_type,
            label=symbol.name,
            path=symbol.path,
            metadata=metadata,
        )

    def _file_id(self, path: str) -> str:
        return f"file:{path}"

    def _symbol_id(self, symbol: SymbolInfo, node_type: NodeType) -> str:
        container = symbol.container_name or "<module>"
        return (
            f"{node_type.value.lower()}:{symbol.path}:"
            f"{container}:{symbol.name}:{symbol.start_line}:{symbol.start_byte}:{symbol.end_byte}"
        )

    def _import_label(self, import_ref: ImportRef) -> str:
        if import_ref.imported_name:
            return f"{import_ref.module}.{import_ref.imported_name}"
        return import_ref.module
