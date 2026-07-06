import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CodeGraph } from "../types";
import { GraphCanvas } from "./GraphCanvas";

const reactFlowProps = vi.hoisted(() => [] as Array<Record<string, unknown>>);

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: (props: Record<string, unknown>) => {
      reactFlowProps.push(props);
      return React.createElement("div", { "data-testid": "react-flow" });
    },
  };
});

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
  ],
  edges: [
    {
      id: "imports:file:src/app.ts->file:src/scoring.ts",
      source: "file:src/app.ts",
      target: "file:src/scoring.ts",
      type: "IMPORTS",
      metadata: {},
    },
  ],
};

describe("GraphCanvas", () => {
  it("renders a non-editable graph while preserving controlled node props", () => {
    reactFlowProps.length = 0;

    render(
      <GraphCanvas
        graph={graph}
        filters={{ FILE: true, FUNCTION: true, CLASS: true }}
        selectedId="file:src/scoring.ts"
        searchTerm="score"
        onSearchTerm={() => undefined}
        onSelect={() => undefined}
      />,
    );

    const props = reactFlowProps[0];
    expect(props.nodesDraggable).toBe(false);
    expect(props.nodesConnectable).toBe(false);
    expect(props.onNodesChange).toBeUndefined();
    expect(props.onEdgesChange).toBeUndefined();
    expect((props.nodes as Array<{ id: string }>).map((node) => node.id)).toEqual([
      "file:src/app.ts",
      "file:src/scoring.ts",
    ]);
  });
});
