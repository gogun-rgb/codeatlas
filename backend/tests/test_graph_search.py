from __future__ import annotations

from app.graph.search import GraphSearch, normalize_tokens
from app.models.graph import CodeGraph, EdgeType, GraphEdge, GraphNode, NodeType


def _file(path: str, metadata: dict[str, object] | None = None) -> GraphNode:
    return GraphNode(
        id=f"file:{path}",
        type=NodeType.FILE,
        label=path.rsplit("/", 1)[-1],
        path=path,
        metadata=metadata or {},
    )


def _function(path: str, name: str, line: int = 1) -> GraphNode:
    return GraphNode(
        id=f"function:{path}:<module>:{name}:{line}:0:10",
        type=NodeType.FUNCTION,
        label=name,
        path=path,
        metadata={"startLine": line, "exported": True},
    )


def _class(path: str, name: str, line: int = 1) -> GraphNode:
    return GraphNode(
        id=f"class:{path}:<module>:{name}:{line}:0:10",
        type=NodeType.CLASS,
        label=name,
        path=path,
        metadata={"startLine": line, "exported": True},
    )


def _imports(source: str, target: str) -> GraphEdge:
    return GraphEdge(
        id=f"imports:file:{source}->file:{target}",
        source=f"file:{source}",
        target=f"file:{target}",
        type=EdgeType.IMPORTS,
        metadata={},
    )


def _contains(file_path: str, symbol: GraphNode) -> GraphEdge:
    return GraphEdge(
        id=f"contains:file:{file_path}->{symbol.id}",
        source=f"file:{file_path}",
        target=symbol.id,
        type=EdgeType.CONTAINS,
        metadata={},
    )


def test_query_normalization_splits_common_identifier_shapes() -> None:
    assert normalize_tokens("GitHubClient") == ["github", "client"]
    assert normalize_tokens("calculate_score") == ["calculate", "score"]
    assert normalize_tokens("credential-service") == ["credential", "service"]
    assert normalize_tokens("src/config/scoring.ts") == ["config", "scoring"]


def test_concept_expansion_ranks_auth_area_without_exact_login_names() -> None:
    session_fn = _function("src/auth/session.ts", "createSession", line=7)
    identity_cls = _class("src/auth/identity.ts", "IdentityService", line=3)
    credential_fn = _function("src/storage/credential_store.py", "load_credentials", line=5)
    graph = CodeGraph(
        nodes=[
            _file("src/auth/session.ts", {"exports": ["createSession"]}),
            session_fn,
            _file("src/auth/identity.ts", {"exports": ["IdentityService"]}),
            identity_cls,
            _file("src/storage/credential_store.py", {"exports": ["load_credentials"]}),
            credential_fn,
            _file("src/notifications/email.ts", {"exports": ["sendEmail"]}),
        ],
        edges=[
            _contains("src/auth/session.ts", session_fn),
            _contains("src/auth/identity.ts", identity_cls),
            _contains("src/storage/credential_store.py", credential_fn),
            _imports("src/auth/session.ts", "src/auth/identity.ts"),
            _imports("src/auth/session.ts", "src/storage/credential_store.py"),
        ],
    )

    candidates = GraphSearch().search(graph, "Where is user login handled?")

    assert candidates[0].node.path.startswith("src/auth/")
    assert "login" not in candidates[0].node.path.lower()
    assert "login" not in candidates[0].node.label.lower()
    assert any("expanded auth concept" in reason for reason in candidates[0].reasons)


def test_graph_expansion_promotes_related_import_over_weak_partial_match() -> None:
    scoring_file = _file("src/core/scoring.ts", {"exports": ["calculateScore"]})
    route_file = _file(
        "src/api/scoring_route.ts",
        {"imports": [{"resolvedPath": "src/core/scoring.ts"}]},
    )
    unrelated = _file("src/docs/scoring_notes.ts")
    graph = CodeGraph(
        nodes=[scoring_file, route_file, unrelated],
        edges=[_imports("src/api/scoring_route.ts", "src/core/scoring.ts")],
    )

    candidates = GraphSearch().search(graph, "Where does src/core/scoring.ts connect?")
    ordered_paths = [candidate.node.path for candidate in candidates]

    assert ordered_paths.index("src/api/scoring_route.ts") < ordered_paths.index(
        "src/docs/scoring_notes.ts"
    )
    related = next(candidate for candidate in candidates if candidate.node.path == route_file.path)
    assert any("reverse dependency" in reason for reason in related.reasons)


def test_containing_file_is_recovered_from_strong_symbol_match() -> None:
    symbol = _function("src/scoring.ts", "calculateScore", line=14)
    graph = CodeGraph(
        nodes=[_file("src/scoring.ts"), symbol],
        edges=[_contains("src/scoring.ts", symbol)],
    )

    candidates = GraphSearch().search(graph, "Where is calculateScore?")
    file_candidate = next(
        candidate for candidate in candidates if candidate.node.type == NodeType.FILE
    )

    assert file_candidate.node.path == "src/scoring.ts"
    assert any("contains matching symbol" in reason for reason in file_candidate.reasons)


def test_exact_path_dominates_ranking() -> None:
    graph = CodeGraph(
        nodes=[
            _file("src/config/scoring.ts"),
            _file("src/scoring/other.ts"),
            _function("src/scoring/other.ts", "scoring"),
        ],
        edges=[],
    )

    candidates = GraphSearch().search(graph, "Open src/config/scoring.ts")

    assert candidates[0].node.path == "src/config/scoring.ts"
    assert candidates[0].reasons[0] == "exact path match: src/config/scoring.ts"


def test_ranking_scores_and_reasons_are_stable() -> None:
    graph = CodeGraph(
        nodes=[
            _file("src/core/scoring.ts", {"exports": ["calculateScore"]}),
            _function("src/core/scoring.ts", "calculateScore", line=12),
            _file("src/api/scoring_route.ts"),
        ],
        edges=[
            _contains(
                "src/core/scoring.ts",
                _function("src/core/scoring.ts", "calculateScore", line=12),
            ),
            _imports("src/api/scoring_route.ts", "src/core/scoring.ts"),
        ],
    )
    search = GraphSearch()

    first = search.search(graph, "Where is calculateScore?")
    second = search.search(graph, "Where is calculateScore?")

    assert [(item.node.id, item.score, item.reasons) for item in first] == [
        (item.node.id, item.score, item.reasons) for item in second
    ]


def test_graph_expansion_is_bounded_and_cycle_safe() -> None:
    graph = CodeGraph(
        nodes=[
            _file("src/a.ts"),
            _file("src/b.ts"),
            _file("src/c.ts"),
            _file("src/d.ts"),
        ],
        edges=[
            _imports("src/a.ts", "src/b.ts"),
            _imports("src/b.ts", "src/c.ts"),
            _imports("src/c.ts", "src/b.ts"),
            _imports("src/c.ts", "src/d.ts"),
        ],
    )

    candidates = GraphSearch().search(graph, "src/a.ts")
    paths = [candidate.node.path for candidate in candidates]

    assert "src/a.ts" in paths
    assert "src/b.ts" in paths
    assert "src/c.ts" in paths
    assert "src/d.ts" not in paths


def test_high_degree_generic_file_does_not_outrank_relevant_auth_candidates() -> None:
    session = _file("src/auth/session.ts", {"exports": ["createSession"]})
    index = _file(
        "src/index.ts",
        {"importedBy": ["src/a.ts", "src/b.ts", "src/c.ts", "src/d.ts", "src/e.ts"]},
    )
    graph = CodeGraph(
        nodes=[
            session,
            _function("src/auth/session.ts", "createSession"),
            index,
            _file("src/a.ts"),
            _file("src/b.ts"),
            _file("src/c.ts"),
            _file("src/d.ts"),
            _file("src/e.ts"),
        ],
        edges=[
            _contains("src/auth/session.ts", _function("src/auth/session.ts", "createSession")),
            _imports("src/index.ts", "src/auth/session.ts"),
            _imports("src/a.ts", "src/index.ts"),
            _imports("src/b.ts", "src/index.ts"),
            _imports("src/c.ts", "src/index.ts"),
            _imports("src/d.ts", "src/index.ts"),
            _imports("src/e.ts", "src/index.ts"),
        ],
    )

    candidates = GraphSearch().search(graph, "Where is login handled?")
    index_candidate = next(
        candidate for candidate in candidates if candidate.node.path == "src/index.ts"
    )
    session_candidate = next(
        candidate for candidate in candidates if candidate.node.path == "src/auth/session.ts"
    )

    assert session_candidate.score > index_candidate.score


def test_converging_auth_seeds_do_not_promote_generic_hub_above_direct_matches() -> None:
    seed_paths = [
        "src/auth.ts",
        "src/authentication.ts",
        "src/authorize.ts",
        "src/authorization.ts",
        "src/signin.ts",
        "src/session.ts",
        "src/credential.ts",
        "src/identity.ts",
    ]
    graph = CodeGraph(
        nodes=[
            *[
                _file(path, {"exports": [path.rsplit("/", 1)[-1].split(".", 1)[0]]})
                for path in seed_paths
            ],
            _file("src/index.ts", {"importedBy": seed_paths}),
        ],
        edges=[_imports(path, "src/index.ts") for path in seed_paths],
    )

    candidates = GraphSearch().search(graph, "Where is login handled?", limit=12)
    index_candidate = next(
        candidate for candidate in candidates if candidate.node.path == "src/index.ts"
    )
    direct_candidates = [
        candidate for candidate in candidates if candidate.node.path in seed_paths
    ]

    assert direct_candidates
    assert max(candidate.score for candidate in direct_candidates) > index_candidate.score
    assert candidates[0].node.path in seed_paths


def test_relevant_high_degree_file_keeps_direct_lexical_advantage() -> None:
    importer_paths = [
        "src/pages/a.ts",
        "src/pages/b.ts",
        "src/pages/c.ts",
        "src/pages/d.ts",
        "src/pages/e.ts",
        "src/pages/f.ts",
    ]
    graph = CodeGraph(
        nodes=[
            _file(
                "src/session/index.ts",
                {
                    "exports": ["createSession"],
                    "importedBy": importer_paths,
                },
            ),
            *[_file(path) for path in importer_paths],
            _file("src/identity.ts", {"exports": ["IdentityService"]}),
        ],
        edges=[
            *[_imports(path, "src/session/index.ts") for path in importer_paths],
            _imports("src/session/index.ts", "src/identity.ts"),
        ],
    )

    candidates = GraphSearch().search(graph, "Where is session handled?", limit=12)

    assert candidates[0].node.path == "src/session/index.ts"
    assert candidates[0].score > next(
        candidate for candidate in candidates if candidate.node.path == "src/identity.ts"
    ).score
