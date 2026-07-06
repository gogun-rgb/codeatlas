import { afterEach, describe, expect, it, vi } from "vitest";

import { askQuestion } from "./api";

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks questions with analysis_id instead of a client-owned graph", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        question: "Where is scoring?",
        candidates: [],
        deterministic_answer: "No strong graph matches were found.",
        ai_status: "disabled",
        ai_explanation: null,
        ai_references: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await askQuestion("Where is scoring?", "analysis-123", true);

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init.body))).toEqual({
      analysis_id: "analysis-123",
      question: "Where is scoring?",
      use_ai: true,
    });
    expect(String(init.body)).not.toContain("nodes");
    expect(String(init.body)).not.toContain("edges");
  });
});
