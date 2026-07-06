from __future__ import annotations

from app.graph.builder import GraphBuilder
from app.graph.import_resolution import resolve_javascript_import, resolve_python_import
from app.graph.search import GraphSearch
from app.models.graph import EdgeType, NodeType
from app.models.repository import Language, SourceFile
from app.parsing.javascript import JavaScriptLikeExtractor
from app.parsing.python import PythonExtractor
from app.parsing.registry import ParserRegistry


def _source(path: str, language: Language, content: str) -> SourceFile:
    return SourceFile(
        path=path,
        language=language,
        size=len(content.encode()),
        content=content,
    )


def _build_graph(files: list[SourceFile]):
    parsed = ParserRegistry().parse_files(files)
    return GraphBuilder().build(parsed)


def _import_targets(graph, source_path: str) -> list[str]:
    nodes_by_id = {node.id: node for node in graph.nodes}
    return sorted(
        nodes_by_id[edge.target].path
        for edge in graph.edges
        if edge.type == EdgeType.IMPORTS and edge.source == f"file:{source_path}"
    )


def _node_ids(graph) -> list[str]:
    return [node.id for node in graph.nodes]


def _edge_ids(graph) -> list[str]:
    return [edge.id for edge in graph.edges]


def test_typescript_imports_functions_and_classes() -> None:
    source = SourceFile(
        path="src/app.ts",
        language=Language.TYPESCRIPT,
        size=200,
        content=(
            "import { calculateScore } from './scoring';\n"
            "export { Button } from './components/Button';\n"
            "const auth = require('../auth');\n"
            "export function boot() { return calculateScore([]); }\n"
            "const normalize = () => true;\n"
            "export class AppController {}\n"
        ),
    )

    parsed = JavaScriptLikeExtractor("typescript").parse(source)

    assert [item.module for item in parsed.imports] == [
        "./scoring",
        "./components/Button",
        "../auth",
    ]
    assert {symbol.name for symbol in parsed.symbols} >= {"boot", "normalize", "AppController"}
    assert "AppController" in parsed.exports


def test_python_imports_functions_and_classes() -> None:
    source = SourceFile(
        path="pkg/app.py",
        language=Language.PYTHON,
        size=120,
        content=(
            "import os\n"
            "from .scoring import calculate_score\n"
            "def run():\n"
            "    return calculate_score([])\n"
            "class Analyzer:\n"
            "    pass\n"
        ),
    )

    parsed = PythonExtractor().parse(source)

    assert [item.module for item in parsed.imports] == ["os", ".scoring"]
    assert {symbol.name for symbol in parsed.symbols} == {"run", "Analyzer"}


def test_javascript_typescript_import_resolution_is_language_aware() -> None:
    all_paths = {
        "src/app.js",
        "src/app.ts",
        "src/foo.js",
        "src/foo.ts",
        "src/lib/index.js",
        "src/routes/index.ts",
        "src/view/index.tsx",
    }

    assert resolve_javascript_import("src/app.js", "./foo", all_paths) == "src/foo.js"
    assert resolve_javascript_import("src/app.ts", "./foo", all_paths) == "src/foo.ts"
    assert resolve_javascript_import("src/app.ts", "./routes", all_paths) == "src/routes/index.ts"
    assert resolve_javascript_import("src/app.ts", "./view", all_paths) == "src/view/index.tsx"
    assert resolve_javascript_import("src/app.js", "./lib", all_paths) == "src/lib/index.js"
    assert resolve_javascript_import("src/app.ts", "./missing.js", all_paths) is None


def test_typescript_explicit_js_specifier_can_resolve_to_ts_source() -> None:
    all_paths = {"src/app.ts", "src/foo.ts"}

    assert resolve_javascript_import("src/app.ts", "./foo.js", all_paths) == "src/foo.ts"


def test_python_relative_import_resolution_preserves_alias_targets() -> None:
    all_paths = {
        "pkg/app.py",
        "pkg/scoring.py",
        "pkg/weights.py",
        "pkg/models.py",
        "pkg/services/user.py",
        "pkg/sub/app.py",
    }

    assert resolve_python_import("pkg/app.py", ".scoring", all_paths) == "pkg/scoring.py"
    assert resolve_python_import("pkg/app.py", ".weights", all_paths) == "pkg/weights.py"
    assert resolve_python_import("pkg/sub/app.py", "..models", all_paths) == "pkg/models.py"
    assert (
        resolve_python_import("pkg/app.py", ".services", all_paths, imported_name="user")
        == "pkg/services/user.py"
    )
    assert (
        resolve_python_import("pkg/sub/app.py", "..models", all_paths, imported_name="User")
        == "pkg/models.py"
    )


def test_graph_builder_generates_deterministic_nodes_contains_and_import_edges() -> None:
    files = [
        SourceFile(
            path="src/app.ts",
            language=Language.TYPESCRIPT,
            size=80,
            content="import { calculateScore } from './scoring';\nexport function boot() {}\n",
        ),
        SourceFile(
            path="src/scoring.ts",
            language=Language.TYPESCRIPT,
            size=90,
            content="export function calculateScore() { return 1; }\nexport class ScoreBucket {}\n",
        ),
    ]

    parsed = ParserRegistry().parse_files(files)
    graph = GraphBuilder().build(parsed)

    assert [node.id for node in graph.nodes] == sorted(node.id for node in graph.nodes)
    assert "file:src/scoring.ts" in {node.id for node in graph.nodes}
    assert any(
        node.type == NodeType.FUNCTION
        and node.path == "src/scoring.ts"
        and node.label == "calculateScore"
        for node in graph.nodes
    )
    assert any(edge.type == EdgeType.CONTAINS for edge in graph.edges)
    assert any(edge.type == EdgeType.IMPORTS for edge in graph.edges)


def test_duplicate_symbols_have_collision_safe_deterministic_node_ids() -> None:
    files = [
        _source(
            "src/duplicates.ts",
            Language.TYPESCRIPT,
            (
                "function render() { return 1; }\n"
                "function render() { return 2; }\n"
                "class Card { render() { return 3; } }\n"
                "class Panel { render() { return 4; } }\n"
            ),
        ),
        _source(
            "src/other.ts",
            Language.TYPESCRIPT,
            "function render() { return 5; }\n",
        ),
    ]

    first = _build_graph(files)
    second = _build_graph(files)
    render_nodes = [
        node
        for node in first.nodes
        if node.type == NodeType.FUNCTION and node.label == "render"
    ]
    symbol_ids = [
        node.id
        for node in first.nodes
        if node.type in {NodeType.CLASS, NodeType.FUNCTION}
    ]
    contains_targets = {edge.target for edge in first.edges if edge.type == EdgeType.CONTAINS}

    assert len(render_nodes) == 5
    assert len(symbol_ids) == len(set(symbol_ids))
    assert len(_edge_ids(first)) == len(set(_edge_ids(first)))
    assert set(symbol_ids) <= contains_targets
    assert {node.metadata["containerName"] for node in render_nodes} >= {
        None,
        "Card",
        "Panel",
    }
    assert _node_ids(first) == _node_ids(second)
    assert _edge_ids(first) == _edge_ids(second)


def test_graph_import_edges_use_exact_python_alias_targets() -> None:
    graph = _build_graph(
        [
            _source(
                "pkg/app.py",
                Language.PYTHON,
                "from . import scoring, weights\nfrom .services import user\n",
            ),
            _source(
                "pkg/sub/app.py",
                Language.PYTHON,
                "from .. import models\nfrom ..models import User\n",
            ),
            _source("pkg/scoring.py", Language.PYTHON, "def score():\n    return 1\n"),
            _source("pkg/weights.py", Language.PYTHON, "WEIGHT = 2\n"),
            _source("pkg/models.py", Language.PYTHON, "class User:\n    pass\n"),
            _source("pkg/services/user.py", Language.PYTHON, "def load():\n    return None\n"),
        ]
    )

    assert _import_targets(graph, "pkg/app.py") == [
        "pkg/scoring.py",
        "pkg/services/user.py",
        "pkg/weights.py",
    ]
    assert _import_targets(graph, "pkg/sub/app.py") == ["pkg/models.py", "pkg/models.py"]


def test_graph_builder_records_unresolved_local_imports_without_fake_nodes() -> None:
    parsed = ParserRegistry().parse_files(
        [
            SourceFile(
                path="src/app.ts",
                language=Language.TYPESCRIPT,
                size=80,
                content="import thing from './missing';\nexport function boot() {}\n",
            )
        ]
    )

    graph = GraphBuilder().build(parsed)
    file_node = next(node for node in graph.nodes if node.type == NodeType.FILE)

    assert file_node.metadata["unresolvedLocalImports"] == ["./missing"]
    assert not any(edge.type == EdgeType.IMPORTS for edge in graph.edges)
    assert not any(node.path == "src/missing.ts" for node in graph.nodes)


def test_external_imports_are_metadata_without_fake_internal_nodes() -> None:
    graph = _build_graph(
        [
            _source(
                "src/app.ts",
                Language.TYPESCRIPT,
                "import express from 'express';\nexport function boot() {}\n",
            )
        ]
    )
    file_node = next(node for node in graph.nodes if node.type == NodeType.FILE)

    assert file_node.metadata["externalImports"] == ["express"]
    assert not any(edge.type == EdgeType.IMPORTS for edge in graph.edges)
    assert not any(node.id == "file:express" for node in graph.nodes)


def test_parser_errors_are_recorded_as_safe_file_metadata() -> None:
    graph = _build_graph(
        [
            _source(
                "src/broken.ts",
                Language.TYPESCRIPT,
                "export function broken( {\n",
            )
        ]
    )
    file_node = next(node for node in graph.nodes if node.type == NodeType.FILE)

    assert file_node.metadata["parserErrors"] == ["Tree-sitter reported syntax errors."]


def test_graph_search_ranks_matching_file_first() -> None:
    parsed = ParserRegistry().parse_files(
        [
            SourceFile(
                path="src/scoring.ts",
                language=Language.TYPESCRIPT,
                size=80,
                content="export function calculateScore() { return 1; }\n",
            ),
            SourceFile(
                path="src/github.ts",
                language=Language.TYPESCRIPT,
                size=80,
                content="export function fetchGitHubSignals() { return []; }\n",
            ),
        ]
    )
    graph = GraphBuilder().build(parsed)

    candidates = GraphSearch().search(graph, "Where is the scoring logic?")

    assert candidates[0].node.path == "src/scoring.ts"
    assert "scoring" in " ".join(candidates[0].reasons)
