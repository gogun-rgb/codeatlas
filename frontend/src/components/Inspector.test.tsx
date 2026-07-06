import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Inspector } from "./Inspector";
import type { CodeGraph } from "../types";

describe("Inspector", () => {
  it("shows a safe parser warning for files with parser errors", () => {
    const graph: CodeGraph = {
      warnings: [],
      metadata: {},
      nodes: [
        {
          id: "file:src/broken.ts",
          type: "FILE",
          label: "broken.ts",
          path: "src/broken.ts",
          metadata: { parserErrors: ["Tree-sitter reported syntax errors."] },
        },
      ],
      edges: [],
    };

    render(<Inspector graph={graph} selectedId="file:src/broken.ts" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Parser warning");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This file contains syntax or parser errors. Graph data may be incomplete.",
    );
  });
});
