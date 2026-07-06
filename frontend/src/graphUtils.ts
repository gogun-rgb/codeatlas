import type { CodeGraph, Filters, GraphEdge, GraphNode } from "./types";

export function fileNodes(graph: CodeGraph): GraphNode[] {
  return graph.nodes
    .filter((node) => node.type === "FILE")
    .sort((a, b) => a.path.localeCompare(b.path));
}

export function symbolNodesForPath(graph: CodeGraph, path: string): GraphNode[] {
  return graph.nodes
    .filter((node) => node.path === path && node.type !== "FILE")
    .sort((a, b) => String(a.metadata.startLine ?? 0).localeCompare(String(b.metadata.startLine ?? 0)));
}

export function visibleGraph(graph: CodeGraph, filters: Filters): CodeGraph {
  const nodes = graph.nodes.filter((node) => filters[node.type]);
  const ids = new Set(nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  return { ...graph, nodes, edges };
}

export function searchNodes(graph: CodeGraph, query: string): GraphNode[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return [];
  }
  return graph.nodes
    .filter(
      (node) =>
        node.label.toLowerCase().includes(needle) ||
        node.path.toLowerCase().includes(needle) ||
        node.type.toLowerCase().includes(needle),
    )
    .sort((a, b) => a.path.localeCompare(b.path) || a.label.localeCompare(b.label));
}

export function importEdgesForPath(graph: CodeGraph, path: string): GraphEdge[] {
  const fileId = `file:${path}`;
  return graph.edges.filter((edge) => edge.type === "IMPORTS" && edge.source === fileId);
}

export function importedByForPath(graph: CodeGraph, path: string): string[] {
  const fileId = `file:${path}`;
  const ids = new Set(
    graph.edges.filter((edge) => edge.type === "IMPORTS" && edge.target === fileId).map((edge) => edge.source),
  );
  return graph.nodes
    .filter((node) => ids.has(node.id))
    .map((node) => node.path)
    .sort();
}
