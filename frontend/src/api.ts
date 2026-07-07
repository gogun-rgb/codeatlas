import type { AnalyzeResponse, QuestionAnswer } from "./types";

export function apiUrl(path: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!baseUrl) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Request failed.");
  }
  return (await response.json()) as T;
}

export function analyzeRepository(repository: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ repository }),
  });
}

export function loadDemoGraph(): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/demo");
}

export function askQuestion(
  question: string,
  analysisId: string,
  useAi: boolean,
): Promise<QuestionAnswer> {
  return request<QuestionAnswer>("/api/question", {
    method: "POST",
    body: JSON.stringify({ question, analysis_id: analysisId, use_ai: useAi }),
  });
}

export async function loadCapabilities(): Promise<{ aiExplanationAvailable: boolean }> {
  const response = await request<{ ai_explanation_available: boolean }>("/api/capabilities");
  return { aiExplanationAvailable: response.ai_explanation_available };
}
