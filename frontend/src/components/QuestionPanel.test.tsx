import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { QuestionAnswer } from "../types";
import { QuestionPanel } from "./QuestionPanel";

const askQuestionMock = vi.hoisted(() => vi.fn());

vi.mock("../api", () => ({
  askQuestion: askQuestionMock,
}));

function answer(text: string, ai = false): QuestionAnswer {
  return {
    question: "Where is scoring?",
    candidates: [],
    deterministic_answer: text,
    ai_status: ai ? "generated" : "disabled",
    ai_explanation: ai ? "AI explanation for retrieved graph context." : null,
    ai_references: ai ? [{ path: "src/scoring.ts", symbol: null, reason: "valid" }] : [],
  };
}

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

describe("QuestionPanel", () => {
  afterEach(() => {
    askQuestionMock.mockReset();
  });

  it("renders deterministic graph result before optional AI explanation", async () => {
    askQuestionMock.mockResolvedValueOnce(answer("Suggested starting point\n\nsrc/scoring.ts", true));
    render(<QuestionPanel analysisId="analysis-123" aiAvailable />);

    fireEvent.click(screen.getByLabelText("AI explanation"));
    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));

    const graphResult = await screen.findByText("Graph result");
    const aiExplanation = screen.getByText("Optional AI explanation");
    expect(graphResult.compareDocumentPosition(aiExplanation)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(/Suggested starting point/)).toBeInTheDocument();
    expect(screen.getByText(/AI explanation for/)).toBeInTheDocument();
  });

  it("clears a previous answer when analysisId changes", async () => {
    askQuestionMock.mockResolvedValueOnce(answer("Repository A answer"));
    const { rerender } = render(<QuestionPanel analysisId="analysis-a" aiAvailable />);

    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));
    expect(await screen.findByText("Repository A answer")).toBeInTheDocument();

    rerender(<QuestionPanel analysisId="analysis-b" aiAvailable />);

    await waitFor(() => {
      expect(screen.queryByText("Repository A answer")).not.toBeInTheDocument();
    });
  });

  it("clears a previous result error when analysisId changes", async () => {
    askQuestionMock.mockRejectedValueOnce(new Error("Repository A failed"));
    const { rerender } = render(<QuestionPanel analysisId="analysis-a" aiAvailable />);

    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));
    expect(await screen.findByText("Repository A failed")).toBeInTheDocument();

    rerender(<QuestionPanel analysisId="analysis-b" aiAvailable />);

    await waitFor(() => {
      expect(screen.queryByText("Repository A failed")).not.toBeInTheDocument();
    });
  });

  it("ignores a delayed response from an old analysis after analysisId changes", async () => {
    const oldRequest = deferred<QuestionAnswer>();
    askQuestionMock.mockReturnValueOnce(oldRequest.promise);
    const { rerender } = render(<QuestionPanel analysisId="analysis-a" aiAvailable />);

    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));
    rerender(<QuestionPanel analysisId="analysis-b" aiAvailable />);

    await act(async () => {
      oldRequest.resolve(answer("Repository A delayed answer"));
      await oldRequest.promise;
    });

    expect(screen.queryByText("Repository A delayed answer")).not.toBeInTheDocument();
  });

  it("submits normally for the current analysis after an analysis change", async () => {
    askQuestionMock.mockResolvedValueOnce(answer("Repository B answer"));
    const { rerender } = render(<QuestionPanel analysisId="analysis-a" aiAvailable />);
    rerender(<QuestionPanel analysisId="analysis-b" aiAvailable />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /ask graph/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /ask graph/i }));

    expect(await screen.findByText("Repository B answer")).toBeInTheDocument();
    expect(askQuestionMock).toHaveBeenCalledWith(
      "Where is the scoring logic?",
      "analysis-b",
      false,
    );
  });
});
