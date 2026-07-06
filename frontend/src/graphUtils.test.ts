import { describe, expect, it } from "vitest";
import { importedByForPath, searchNodes, visibleGraph } from "./graphUtils";
import type { CodeGraph } from "./types";

const graph: CodeGraph = {
  warnings: [],
  metadata: {},
  nodes: [
    { id: "file:src/app.ts", type: "FILE", label: "app.ts", path: "src/app.ts", metadata: {} },
    {
      id: "file:src/scoring.ts",
      type: "FILE",
      label: "scoring.ts",
      path: "src/scoring.ts",
      metadata: {},
    },
    {
      id: "function:src/scoring.ts:<module>:calculateScore:3:24:58",
      type: "FUNCTION",
      label: "calculateScore",
      path: "src/scoring.ts",
      metadata: { startLine: 3 },
    },
  ],
  edges: [
    {
      id: "imports:file:src/app.ts->file:src/scoring.ts:1:./scoring",
      source: "file:src/app.ts",
      target: "file:src/scoring.ts",
      type: "IMPORTS",
      metadata: {},
    },
    {
      id: "contains:file:src/scoring.ts->function:src/scoring.ts:<module>:calculateScore:3:24:58",
      source: "file:src/scoring.ts",
      target: "function:src/scoring.ts:<module>:calculateScore:3:24:58",
      type: "CONTAINS",
      metadata: {},
    },
  ],
};

describe("graph UI helpers", () => {
  it("filters nodes and removes edges with hidden endpoints", () => {
    const visible = visibleGraph(graph, { FILE: true, FUNCTION: false, CLASS: true });

    expect(visible.nodes.map((node) => node.type)).toEqual(["FILE", "FILE"]);
    expect(visible.edges.map((edge) => edge.type)).toEqual(["IMPORTS"]);
  });

  it("searches by label and path", () => {
    expect(searchNodes(graph, "score").map((node) => node.id)).toContain(
      "function:src/scoring.ts:<module>:calculateScore:3:24:58",
    );
  });

  it("finds reverse importers for a file", () => {
    expect(importedByForPath(graph, "src/scoring.ts")).toEqual(["src/app.ts"]);
  });
});
