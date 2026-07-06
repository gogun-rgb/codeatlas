export type NodeType = "FILE" | "FUNCTION" | "CLASS";
export type EdgeType = "IMPORTS" | "CONTAINS" | "CALLS" | "REFERENCES" | "IMPLEMENTS" | "EXTENDS";

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  path: string;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  metadata: Record<string, unknown>;
}

export interface CodeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface AnalyzeResponse {
  repository: string;
  graph: CodeGraph;
}

export interface SearchCandidate {
  node: GraphNode;
  score: number;
  reasons: string[];
}

export interface QuestionAnswer {
  question: string;
  candidates: SearchCandidate[];
  deterministic_answer: string;
  ai_status: "disabled" | "unavailable" | "generated";
  ai_explanation?: string | null;
  ai_references: Array<{ path: string; symbol?: string | null; reason: string }>;
}

export interface Filters {
  FILE: boolean;
  FUNCTION: boolean;
  CLASS: boolean;
}
