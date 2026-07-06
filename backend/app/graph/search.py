from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.models.graph import CodeGraph, EdgeType, GraphNode, GraphQuestionAnswer, SearchCandidate

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
ACRONYM_BOUNDARY_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
SEPARATOR_RE = re.compile(r"[/_.\-\s]+")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "change",
    "code",
    "does",
    "file",
    "for",
    "from",
    "handle",
    "handled",
    "handler",
    "in",
    "is",
    "logic",
    "of",
    "on",
    "should",
    "src",
    "the",
    "this",
    "to",
    "where",
    "which",
    "with",
    "js",
    "jsx",
    "ts",
    "tsx",
    "py",
}

COMPOUND_TOKENS = {
    ("git", "hub"): "github",
}

CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "auth": (
        "auth",
        "authentication",
        "authorize",
        "authorization",
        "login",
        "signin",
        "session",
        "credential",
        "identity",
    ),
    "config": (
        "config",
        "configuration",
        "settings",
        "env",
        "environment",
    ),
    "database": (
        "database",
        "db",
        "storage",
        "repository",
        "persistence",
    ),
    "api": (
        "api",
        "route",
        "routes",
        "router",
        "endpoint",
        "controller",
        "handler",
    ),
    "github": (
        "github",
        "repository",
        "repo",
        "git",
    ),
}

MAX_GRAPH_EXPANSION_DEPTH = 2
MAX_STRUCTURAL_SEEDS = 8
MIN_LEXICAL_SEED_SCORE = 6.0


@dataclass(frozen=True)
class QueryTerms:
    original: tuple[str, ...]
    expanded: dict[str, str]

    @property
    def original_set(self) -> set[str]:
        return set(self.original)


@dataclass(frozen=True)
class NodeTerms:
    label: set[str]
    path: set[str]
    exports: set[str]
    imports: set[str]
    imported_by: set[str]
    external_imports: set[str]
    unresolved_imports: set[str]


@dataclass(frozen=True)
class GraphLink:
    target_id: str
    kind: str


@dataclass
class CandidateAccumulator:
    node: GraphNode
    score: float = 0.0
    lexical_score: float = 0.0
    structural_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    reason_set: set[str] = field(default_factory=set)

    def add(self, points: float, reason: str, evidence: str = "lexical") -> None:
        if points <= 0:
            return
        applied_points = points
        if evidence == "structural":
            cap = 24.0 if self.lexical_score > 0 else 10.0
            applied_points = min(points, max(cap - self.structural_score, 0.0))
            if applied_points <= 0:
                return
            self.structural_score = round(self.structural_score + applied_points, 4)
        else:
            self.lexical_score = round(self.lexical_score + applied_points, 4)
        self.score = round(self.score + applied_points, 4)
        if reason not in self.reason_set:
            self.reason_set.add(reason)
            self.reasons.append(reason)


class GraphSearch:
    def search(self, graph: CodeGraph, question: str, limit: int = 8) -> list[SearchCandidate]:
        query = build_query_terms(question)
        lowered_question = question.lower().replace("\\", "/")
        accumulators = {
            node.id: CandidateAccumulator(node=node)
            for node in graph.nodes
        }
        node_terms = {node.id: build_node_terms(node) for node in graph.nodes}

        for node in graph.nodes:
            self._add_lexical_evidence(
                accumulators[node.id],
                node_terms[node.id],
                query,
                lowered_question,
            )

        lexical_scores = {
            node_id: accumulator.score
            for node_id, accumulator in accumulators.items()
        }
        self._add_graph_expansion_evidence(graph, accumulators, lexical_scores)
        self._add_structural_reranking(accumulators)

        candidates = [
            SearchCandidate(
                node=accumulator.node,
                score=accumulator.score,
                reasons=accumulator.reasons,
            )
            for accumulator in accumulators.values()
            if accumulator.score > 0
        ]
        return sorted(
            candidates,
            key=lambda item: (
                -item.score,
                _node_type(item.node),
                item.node.path,
                item.node.label,
                item.node.id,
            ),
        )[:limit]

    def answer(self, graph: CodeGraph, question: str) -> GraphQuestionAnswer:
        candidates = self.search(graph, question)
        deterministic_answer = format_deterministic_answer(candidates)
        return GraphQuestionAnswer(
            question=question,
            candidates=candidates,
            deterministic_answer=deterministic_answer,
            ai_status="disabled",
        )

    def _add_lexical_evidence(
        self,
        accumulator: CandidateAccumulator,
        terms: NodeTerms,
        query: QueryTerms,
        lowered_question: str,
    ) -> None:
        node = accumulator.node
        if node.path.lower() in lowered_question:
            accumulator.add(120.0, f"exact path match: {node.path}")

        label_terms = terms.label
        if label_terms and label_terms <= query.original_set and _node_type(node) != "FILE":
            accumulator.add(42.0, f"exact symbol match: {node.label}")

        for token in query.original:
            if token in terms.label:
                accumulator.add(24.0, f"name matches original query: {token}")
            if token in terms.path:
                accumulator.add(18.0, f"path matches original query: {token}")
            if token in terms.exports:
                accumulator.add(20.0, f"export matches original query: {token}")
            if token in terms.imports or token in terms.imported_by:
                accumulator.add(9.0, f"dependency context matches original query: {token}")
            if token in terms.external_imports or token in terms.unresolved_imports:
                accumulator.add(5.0, f"import metadata matches original query: {token}")

        for token, concept in query.expanded.items():
            if token in query.original_set:
                continue
            if token in terms.label:
                accumulator.add(7.0, f"expanded {concept} concept: {token}")
            if token in terms.path:
                accumulator.add(6.0, f"expanded {concept} concept: {token}")
            if token in terms.exports:
                accumulator.add(6.0, f"expanded {concept} concept: {token}")
            if token in terms.imports:
                accumulator.add(3.0, f"expanded {concept} dependency context: {token}")

    def _add_graph_expansion_evidence(
        self,
        graph: CodeGraph,
        accumulators: dict[str, CandidateAccumulator],
        lexical_scores: dict[str, float],
    ) -> None:
        links = build_graph_links(graph)
        seed_ids = [
            node_id
            for node_id, score in sorted(
                lexical_scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if score >= MIN_LEXICAL_SEED_SCORE
        ][:MAX_STRUCTURAL_SEEDS]

        for seed_id in seed_ids:
            seed_score = lexical_scores[seed_id]
            seed_node = accumulators[seed_id].node
            queue: list[tuple[str, int]] = [(seed_id, 0)]
            visited = {seed_id}
            while queue:
                current_id, depth = queue.pop(0)
                if depth >= MAX_GRAPH_EXPANSION_DEPTH:
                    continue
                for link in sorted(links[current_id], key=lambda item: (item.target_id, item.kind)):
                    if link.target_id in visited:
                        continue
                    visited.add(link.target_id)
                    distance = depth + 1
                    points = structural_points(link.kind, distance, seed_score)
                    reason = structural_reason(link.kind, distance, seed_node)
                    accumulators[link.target_id].add(points, reason, evidence="structural")
                    queue.append((link.target_id, distance))

    def _add_structural_reranking(
        self,
        accumulators: dict[str, CandidateAccumulator],
    ) -> None:
        for accumulator in accumulators.values():
            if accumulator.score <= 0 or _node_type(accumulator.node) != "FILE":
                continue
            imported_by = accumulator.node.metadata.get("importedBy")
            if isinstance(imported_by, list) and len(imported_by) >= 2:
                points = min(2.0, len(imported_by) * 0.25)
                accumulator.add(points, "weak reverse-import centrality", evidence="structural")


def normalize_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    for piece in SEPARATOR_RE.split(question):
        if not piece:
            continue
        piece = ACRONYM_BOUNDARY_RE.sub(" ", CAMEL_BOUNDARY_RE.sub(" ", piece))
        for token in TOKEN_RE.findall(piece):
            lowered = token.lower()
            if lowered and lowered not in STOP_WORDS:
                tokens.append(lowered)
    return dedupe_tokens(combine_compound_tokens(tokens))


def build_query_terms(question: str) -> QueryTerms:
    original = tuple(normalize_tokens(question))
    expanded: dict[str, str] = {}
    for token in original:
        for concept, terms in CONCEPT_GROUPS.items():
            if token == concept or token in terms:
                for expanded_token in terms:
                    if expanded_token not in STOP_WORDS and expanded_token not in original:
                        expanded.setdefault(expanded_token, concept)
    return QueryTerms(original=original, expanded=expanded)


def build_node_terms(node: GraphNode) -> NodeTerms:
    metadata = node.metadata
    return NodeTerms(
        label=set(normalize_tokens(node.label)),
        path=set(normalize_tokens(node.path)),
        exports=set(tokens_from_metadata(metadata.get("exports"))),
        imports=set(tokens_from_imports(metadata.get("imports"))),
        imported_by=set(tokens_from_metadata(metadata.get("importedBy"))),
        external_imports=set(tokens_from_metadata(metadata.get("externalImports"))),
        unresolved_imports=set(tokens_from_metadata(metadata.get("unresolvedLocalImports"))),
    )


def tokens_from_metadata(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        tokens.extend(normalize_tokens(str(item)))
    return dedupe_tokens(tokens)


def tokens_from_imports(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        if isinstance(item, dict):
            for key in ("module", "imported_name", "importedName", "resolved_path", "resolvedPath"):
                import_value = item.get(key)
                if import_value is not None:
                    tokens.extend(normalize_tokens(str(import_value)))
        else:
            tokens.extend(normalize_tokens(str(item)))
    return dedupe_tokens(tokens)


def build_graph_links(graph: CodeGraph) -> dict[str, list[GraphLink]]:
    links: dict[str, list[GraphLink]] = defaultdict(list)
    node_ids = {node.id for node in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            continue
        if edge.type == EdgeType.IMPORTS:
            links[edge.source].append(GraphLink(target_id=edge.target, kind="imports"))
            links[edge.target].append(GraphLink(target_id=edge.source, kind="imported_by"))
        elif edge.type == EdgeType.CONTAINS:
            links[edge.source].append(GraphLink(target_id=edge.target, kind="contains"))
            links[edge.target].append(GraphLink(target_id=edge.source, kind="contained_by"))
    return links


def structural_points(kind: str, distance: int, seed_score: float) -> float:
    base = {
        "contains": 18.0,
        "contained_by": 22.0,
        "imports": 11.0,
        "imported_by": 9.0,
    }[kind]
    decay = 1.0 if distance == 1 else 0.45
    seed_factor = min(seed_score, 40.0) / 40.0
    return round(base * decay * max(seed_factor, 0.35), 4)


def structural_reason(kind: str, distance: int, seed_node: GraphNode) -> str:
    seed_label = _location_label(seed_node)
    if distance > 1:
        return f"{distance}-hop graph neighbor of matching result: {seed_label}"
    if kind == "contains":
        return f"contained by matching file: {seed_node.path}"
    if kind == "contained_by":
        return f"contains matching symbol: {seed_node.label}"
    if kind == "imports":
        return f"direct dependency of matching file: {seed_node.path}"
    return f"1-hop reverse dependency of matching file: {seed_node.path}"


def format_deterministic_answer(candidates: list[SearchCandidate]) -> str:
    if not candidates:
        return (
            "No strong graph matches were found. Try a file name, function name, "
            "class name, or import keyword."
        )
    top = candidates[0]
    lines = [
        "Suggested starting point",
        "",
        _candidate_location(top),
        f"Type: {_node_type(top.node)}",
    ]
    if top.reasons:
        lines.append(f"Reason: {top.reasons[0]}.")
    lines.extend(["", "Most relevant graph locations", ""])
    for index, candidate in enumerate(candidates[:5], start=1):
        lines.append(f"{index}. {_candidate_location(candidate)}")
    return "\n".join(lines)


def _candidate_location(candidate: SearchCandidate) -> str:
    node = candidate.node
    if _node_type(node) == "FILE":
        return node.path
    start = node.metadata.get("startLine")
    suffix = f" (line {start})" if start else ""
    return f"{node.path} - {node.label}(){suffix}"


def _location_label(node: GraphNode) -> str:
    if _node_type(node) == "FILE":
        return node.path
    return f"{node.path} - {node.label}"


def _node_type(node: GraphNode) -> str:
    value = node.type
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def combine_compound_tokens(tokens: list[str]) -> list[str]:
    combined: list[str] = []
    index = 0
    while index < len(tokens):
        pair = tuple(tokens[index : index + 2])
        if len(pair) == 2 and pair in COMPOUND_TOKENS:
            combined.append(COMPOUND_TOKENS[pair])
            index += 2
            continue
        combined.append(tokens[index])
        index += 1
    return combined


def dedupe_tokens(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result
