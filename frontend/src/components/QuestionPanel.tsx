import { useState, type FormEvent, type ReactElement } from "react";
import { MessageSquareText, Sparkles } from "lucide-react";
import type { CodeGraph, QuestionAnswer } from "../types";
import { askQuestion } from "../api";

interface Props {
  graph: CodeGraph | null;
  aiAvailable: boolean;
}

export function QuestionPanel({ graph, aiAvailable }: Props): ReactElement {
  const [question, setQuestion] = useState("Where is the scoring logic?");
  const [answer, setAnswer] = useState<QuestionAnswer | null>(null);
  const [useAi, setUseAi] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!graph || !question.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setAnswer(await askQuestion(question, graph, useAi && aiAvailable));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Question failed.");
    } finally {
      setLoading(false);
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
          disabled={!graph || loading}
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
        <button type="submit" disabled={!graph || loading || !question.trim()} title="Search graph">
          <MessageSquareText size={16} aria-hidden="true" />
          Ask graph
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {answer ? (
        <div className="answer">
          <pre>{answer.ai_explanation && answer.ai_status === "generated" ? answer.ai_explanation : answer.deterministic_answer}</pre>
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
