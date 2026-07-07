import { afterEach, describe, expect, it, vi } from "vitest";

import { analyzeRepository, apiUrl, askQuestion, loadDemoGraph } from "./api";

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("uses relative API paths when VITE_API_BASE_URL is absent", async () => {
    vi.stubEnv("VITE_API_BASE_URL", undefined);

    expect(apiUrl("/api/analyze")).toBe("/api/analyze");
    expect(apiUrl("/api/question")).toBe("/api/question");
    expect(apiUrl("/api/demo")).toBe("/api/demo");
  });

  it("uses relative API paths when VITE_API_BASE_URL is empty", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");

    expect(apiUrl("/api/analyze")).toBe("/api/analyze");
  });

  it("uses configured production API base URL without duplicating slashes", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/");

    expect(apiUrl("/api/analyze")).toBe("https://api.example.test/api/analyze");
    expect(apiUrl("/api/question")).toBe("https://api.example.test/api/question");
    expect(apiUrl("/api/demo")).toBe("https://api.example.test/api/demo");
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

  it("applies configured API base URL to repository and demo requests", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        analysis_id: "analysis-123",
        repository: "demo/repo",
        graph: { nodes: [], edges: [], warnings: [], metadata: {} },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await analyzeRepository("demo/repo");
    await loadDemoGraph();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "https://api.example.test/api/analyze",
      "https://api.example.test/api/demo",
    ]);
  });
});
