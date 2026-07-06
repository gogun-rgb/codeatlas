from __future__ import annotations

from app.graph.builder import GraphBuilder
from app.models.graph import CodeGraph
from app.models.repository import Language, RepositoryRef, RepositorySnapshot, SourceFile
from app.services.analyzer import CodebaseAnalyzer


def demo_graph() -> tuple[str, CodeGraph]:
    snapshot = RepositorySnapshot(
        ref=RepositoryRef(owner="demo", name="ai-hype-radar-like"),
        default_branch="main",
        files=[
            SourceFile(
                path="src/main.tsx",
                language=Language.TSX,
                size=134,
                content=(
                    "import { fetchGitHubSignals } from './lib/github';\n"
                    "import { calculateScore } from './lib/scoring';\n"
                    "export function bootstrap() { return calculateScore([]); }\n"
                ),
            ),
            SourceFile(
                path="src/lib/github.ts",
                language=Language.TYPESCRIPT,
                size=142,
                content=(
                    "export class GitHubClient {}\n"
                    "export async function fetchGitHubSignals() { return []; }\n"
                ),
            ),
            SourceFile(
                path="src/lib/scoring.ts",
                language=Language.TYPESCRIPT,
                size=112,
                content=(
                    "export function calculateScore(signals: unknown[]) {\n"
                    "  return signals.length;\n"
                    "}\n"
                    "export class ScoreBucket {}\n"
                ),
            ),
            SourceFile(
                path="src/components/RadarChart.tsx",
                language=Language.TSX,
                size=128,
                content=(
                    "import { calculateScore } from '../lib/scoring';\n"
                    "export function RadarChart() { return calculateScore([]); }\n"
                ),
            ),
            SourceFile(
                path="src/services/analyzer.ts",
                language=Language.TYPESCRIPT,
                size=122,
                content=(
                    "import { fetchGitHubSignals } from '../lib/github';\n"
                    "export class HypeAnalyzer { run() { return fetchGitHubSignals(); } }\n"
                ),
            ),
        ],
        warnings=["Demo graph fixture. Submit a public GitHub repository to analyze live code."],
    )
    graph = CodebaseAnalyzer(graph_builder=GraphBuilder()).analyze_snapshot(snapshot)
    return snapshot.ref.identifier, graph
