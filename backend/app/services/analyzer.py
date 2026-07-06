from __future__ import annotations

from app.graph.builder import GraphBuilder
from app.models.graph import CodeGraph
from app.models.repository import RepositorySnapshot
from app.parsing.registry import ParserRegistry
from app.repositories.github import GitHubRepositoryLoader


class CodebaseAnalyzer:
    def __init__(
        self,
        loader: GitHubRepositoryLoader | None = None,
        parser_registry: ParserRegistry | None = None,
        graph_builder: GraphBuilder | None = None,
    ) -> None:
        self._loader = loader or GitHubRepositoryLoader()
        self._parser_registry = parser_registry or ParserRegistry()
        self._graph_builder = graph_builder or GraphBuilder()

    async def analyze_repository(self, repository: str) -> tuple[str, CodeGraph]:
        snapshot = await self._loader.load(repository)
        return snapshot.ref.identifier, self.analyze_snapshot(snapshot)

    def analyze_snapshot(self, snapshot: RepositorySnapshot) -> CodeGraph:
        parsed = self._parser_registry.parse_files(snapshot.files)
        graph = self._graph_builder.build(parsed, warnings=snapshot.warnings)
        graph.metadata.update(
            {
                "repository": snapshot.ref.identifier,
                "defaultBranch": snapshot.default_branch,
                "fileCount": len(snapshot.files),
                "treeTruncated": snapshot.tree_truncated,
            }
        )
        return graph
