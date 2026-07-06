import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";
import { MessageSquareText, Sparkles } from "lucide-react";
import type { QuestionAnswer } from "../types";
import { askQuestion } from "../api";

interface Props {
  analysisId: string | null;
  aiAvailable: boolean;
}

export function QuestionPanel({ analysisId, aiAvailable }: Props): ReactElement {
  const [question, setQuestion] = useState("Where is the scoring logic?");
  const [answer, setAnswer] = useState<QuestionAnswer | null>(null);
  const [useAi, setUseAi] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latestAnalysisId = useRef<string | null>(analysisId);
  const requestId = useRef(0);

  useEffect(() => {
    latestAnalysisId.current = analysisId;
    requestId.current += 1;
    setAnswer(null);
    setError(null);
    setLoading(false);
  }, [analysisId]);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!analysisId || !question.trim()) {
      return;
    }
    const activeAnalysisId = analysisId;
    const activeRequestId = requestId.current + 1;
    requestId.current = activeRequestId;
    setLoading(true);
    setError(null);
    try {
      const nextAnswer = await askQuestion(question, activeAnalysisId, useAi && aiAvailable);
      if (
        requestId.current === activeRequestId &&
        latestAnalysisId.current === activeAnalysisId
      ) {
        setAnswer(nextAnswer);
      }
    } catch (caught) {
      if (
        requestId.current === activeRequestId &&
        latestAnalysisId.current === activeAnalysisId
      ) {
        setError(caught instanceof Error ? caught.message : "Question failed.");
      }
    } finally {
      if (
        requestId.current === activeRequestId &&
        latestAnalysisId.current === activeAnalysisId
      ) {
        setLoading(false);
      }
    }
  }

  return (
    <section className="panel question-panel">
      <div className="panel-header">
        <h2>Ask</h2>
      </div>
      <form onSubmit={submit}>
        <label htmlFor="question">Question</label>
        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={!analysisId || loading}
          rows={3}
        />
        <label className="ai-toggle">
          <input
            type="checkbox"
            checked={useAi}
            disabled={!aiAvailable}
            onChange={(event) => setUseAi(event.target.checked)}
          />
          <Sparkles size={15} aria-hidden="true" />
          <span>{aiAvailable ? "AI explanation" : "AI unavailable"}</span>
        </label>
        <button
          type="submit"
          disabled={!analysisId || loading || !question.trim()}
          title="Search graph"
        >
          <MessageSquareText size={16} aria-hidden="true" />
          Ask graph
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {answer ? (
        <div className="answer">
          <section className="answer-section">
            <h3>Graph result</h3>
            <pre>{answer.deterministic_answer}</pre>
          </section>
          {answer.ai_status === "generated" && answer.ai_explanation ? (
            <section className="answer-section">
              <h3>Optional AI explanation</h3>
              <pre>{answer.ai_explanation}</pre>
              {answer.ai_references.length ? (
                <ul className="ai-references">
                  {answer.ai_references.map((reference) => (
                    <li key={`${reference.path}:${reference.symbol ?? ""}`}>
                      <strong>{reference.path}</strong>
                      {reference.symbol ? <span>{reference.symbol}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}
          {answer.ai_status === "unavailable" || answer.ai_status === "validation_failed" ? (
            <p className="muted">Optional AI explanation unavailable.</p>
          ) : null}
          <ol>
            {answer.candidates.slice(0, 5).map((candidate) => (
              <li key={candidate.node.id}>
                <strong>{candidate.node.label}</strong>
                <span>{candidate.node.path}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
