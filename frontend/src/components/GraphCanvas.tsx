import { useMemo, type ReactElement } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type NodeMouseHandler,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Search } from "lucide-react";
import type { CodeGraph, Filters } from "../types";
import { searchNodes, visibleGraph } from "../graphUtils";
import { toFlowGraph } from "../layout";
import { AtlasNode } from "./AtlasNode";

const nodeTypes = { atlas: AtlasNode };

interface Props {
  graph: CodeGraph | null;
  filters: Filters;
  selectedId: string | null;
  searchTerm: string;
  onSearchTerm: (value: string) => void;
  onSelect: (id: string) => void;
}

export function GraphCanvas({
  graph,
  filters,
  selectedId,
  searchTerm,
  onSearchTerm,
  onSelect,
}: Props): ReactElement {
  const highlighted = useMemo(() => {
    if (!graph) {
      return new Set<string>();
    }
    return new Set(searchNodes(graph, searchTerm).map((node) => node.id));
  }, [graph, searchTerm]);

  const visible = useMemo(() => (graph ? visibleGraph(graph, filters) : null), [graph, filters]);
  const flow = useMemo(
    () => (visible ? toFlowGraph(visible, selectedId, highlighted) : { nodes: [], edges: [] }),
    [visible, selectedId, highlighted],
  );
  const [nodes, , onNodesChange] = useNodesState(flow.nodes);
  const [edges, , onEdgesChange] = useEdgesState(flow.edges);

  const onNodeClick: NodeMouseHandler = (_event, node) => onSelect(node.id);

  return (
    <section className="graph-shell">
      <div className="graph-toolbar">
        <div className="graph-search">
          <Search size={16} aria-hidden="true" />
          <input
            value={searchTerm}
            onChange={(event) => onSearchTerm(event.target.value)}
            placeholder="Find node"
          />
        </div>
        <span>{visible?.nodes.length ?? 0} nodes</span>
      </div>
      <div className="graph-canvas">
        <ReactFlow
          nodes={flow.nodes.length ? flow.nodes : nodes}
          edges={flow.edges.length ? flow.edges : edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
          minZoom={0.15}
          maxZoom={1.8}
        >
          <Background gap={20} size={1} />
          <MiniMap pannable zoomable />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
