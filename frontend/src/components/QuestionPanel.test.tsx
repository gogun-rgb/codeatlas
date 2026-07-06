import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuestionPanel } from "./QuestionPanel";

vi.mock("../api", () => ({
  askQuestion: vi.fn(async () => ({
    question: "Where is scoring?",
    candidates: [],
    deterministic_answer: "Suggested starting point\n\nsrc/scoring.ts",
    ai_status: "generated",
    ai_explanation: "The retrieved graph context suggests starting in src/scoring.ts.",
    ai_references: [{ path: "src/scoring.ts", symbol: null, reason: "valid" }],
  })),
}));

describe("QuestionPanel", () => {
  it("renders deterministic graph result before optional AI explanation", async () => {
    render(<QuestionPanel analysisId="analysis-123" aiAvailable />);

    fireEvent.click(screen.getByLabelText("AI explanation"));
    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));

    expect(await screen.findByText("Graph result")).toBeInTheDocument();
    expect(screen.getByText("Optional AI explanation")).toBeInTheDocument();
    expect(screen.getByText(/Suggested starting point/)).toBeInTheDocument();
    expect(screen.getByText(/retrieved graph context/)).toBeInTheDocument();
  });
});
