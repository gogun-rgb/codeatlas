import dagre from "dagre";
import type { Edge, Node } from "@xyflow/react";
import type { CodeGraph, GraphNode } from "./types";

export interface AtlasNodeData extends Record<string, unknown> {
  graphNode: GraphNode;
  highlighted: boolean;
}

const NODE_WIDTH: Record<string, number> = {
  FILE: 190,
  FUNCTION: 170,
  CLASS: 170,
};

const NODE_HEIGHT = 56;

export function toFlowGraph(
  graph: CodeGraph,
  selectedId: string | null,
  highlightedIds: Set<string>,
): { nodes: Array<Node<AtlasNodeData>>; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 36, ranksep: 72 });

  graph.nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: NODE_WIDTH[node.type],
      height: NODE_HEIGHT,
    });
  });
  graph.edges.forEach((edge) => dagreGraph.setEdge(edge.source, edge.target));
  dagre.layout(dagreGraph);

  const nodes = graph.nodes.map<Node<AtlasNodeData>>((node) => {
    const layout = dagreGraph.node(node.id) as { x: number; y: number } | undefined;
    return {
      id: node.id,
      type: "atlas",
      position: {
        x: (layout?.x ?? 0) - NODE_WIDTH[node.type] / 2,
        y: (layout?.y ?? 0) - NODE_HEIGHT / 2,
      },
      data: { graphNode: node, highlighted: highlightedIds.has(node.id) },
      selected: selectedId === node.id,
    };
  });

  const edges = graph.edges.map<Edge>((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    animated: false,
    label: edge.type === "IMPORTS" ? "imports" : undefined,
    className: edge.type === "IMPORTS" ? "edge-imports" : "edge-contains",
  }));
  return { nodes, edges };
}
