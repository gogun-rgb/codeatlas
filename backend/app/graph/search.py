from __future__ import annotations

import re
from collections import defaultdict

from app.models.graph import CodeGraph, GraphNode, GraphQuestionAnswer, SearchCandidate

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class GraphSearch:
    def search(self, graph: CodeGraph, question: str, limit: int = 8) -> list[SearchCandidate]:
        tokens = normalize_tokens(question)
        import_neighbors = self._import_neighbors(graph)
        candidates: list[SearchCandidate] = []
        for node in graph.nodes:
            score, reasons = self._score(node, tokens, question.lower(), import_neighbors[node.id])
            if score > 0:
                candidates.append(SearchCandidate(node=node, score=score, reasons=reasons))
        return sorted(candidates, key=lambda item: (-item.score, item.node.id))[:limit]

    def answer(self, graph: CodeGraph, question: str) -> GraphQuestionAnswer:
        candidates = self.search(graph, question)
        deterministic_answer = format_deterministic_answer(candidates)
        return GraphQuestionAnswer(
            question=question,
            candidates=candidates,
            deterministic_answer=deterministic_answer,
            ai_status="disabled",
        )

    def _score(
        self,
        node: GraphNode,
        tokens: list[str],
        lowered_question: str,
        neighbor_paths: list[str],
    ) -> tuple[float, list[str]]:
        haystacks = {
            "label": node.label.lower(),
            "path": node.path.lower(),
            "type": node.type.value.lower(),
            "imports": " ".join(neighbor_paths).lower(),
        }
        metadata = node.metadata
        for key in ("exports", "externalImports", "unresolvedLocalImports", "importedBy"):
            value = metadata.get(key)
            if isinstance(value, list):
                haystacks[key] = " ".join(str(item) for item in value).lower()

        score = 0.0
        reasons: list[str] = []
        for token in tokens:
            if token in haystacks["label"]:
                score += 8
                reasons.append(f"name matches '{token}'")
            if token in haystacks["path"]:
                score += 5
                reasons.append(f"path matches '{token}'")
            if token in haystacks.get("imports", "") or token in haystacks.get("importedBy", ""):
                score += 3
                reasons.append(f"dependency context matches '{token}'")
            if token in haystacks.get("exports", ""):
                score += 4
                reasons.append(f"export matches '{token}'")
        if node.path.lower() in lowered_question:
            score += 12
            reasons.append("exact path mentioned")
        return score, sorted(set(reasons))

    def _import_neighbors(self, graph: CodeGraph) -> dict[str, list[str]]:
        by_id = {node.id: node for node in graph.nodes}
        neighbors: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            if edge.type != "IMPORTS":
                continue
            source = by_id.get(edge.source)
            target = by_id.get(edge.target)
            if source is not None and target is not None:
                neighbors[source.id].append(target.path)
                neighbors[target.id].append(source.path)
        return neighbors


def normalize_tokens(question: str) -> list[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "change",
        "does",
        "file",
        "for",
        "in",
        "is",
        "logic",
        "of",
        "should",
        "the",
        "this",
        "to",
        "where",
        "which",
    }
    return [
        token.lower()
        for token in TOKEN_RE.findall(question)
        if token.lower() not in stop_words
    ]


def format_deterministic_answer(candidates: list[SearchCandidate]) -> str:
    if not candidates:
        return (
            "No strong graph matches were found. Try a file name, function name, "
            "class name, or import keyword."
        )
    lines = ["Most relevant locations", ""]
    for index, candidate in enumerate(candidates[:5], start=1):
        node = candidate.node
        if node.type == "FILE":
            lines.append(f"{index}. {node.path}")
        else:
            start = node.metadata.get("startLine")
            suffix = f" (line {start})" if start else ""
            lines.append(f"{index}. {node.path} - {node.label}(){suffix}")
    lines.extend(["", f"Suggested starting point: {candidates[0].node.path}"])
    return "\n".join(lines)
