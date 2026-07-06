import { useEffect, useMemo, useState, type ReactElement } from "react";
import { AlertTriangle, Boxes, Loader2 } from "lucide-react";
import { analyzeRepository, loadCapabilities, loadDemoGraph } from "./api";
import { FiltersBar } from "./components/FiltersBar";
import { FileTree } from "./components/FileTree";
import { GraphCanvas } from "./components/GraphCanvas";
import { Inspector } from "./components/Inspector";
import { QuestionPanel } from "./components/QuestionPanel";
import { RepoInput } from "./components/RepoInput";
import type { CodeGraph, Filters } from "./types";
import "./App.css";

const DEFAULT_FILTERS: Filters = { FILE: true, FUNCTION: true, CLASS: true };

export function App(): ReactElement {
  const [graph, setGraph] = useState<CodeGraph | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [repository, setRepository] = useState<string>("gogun-rgb/ai-hype-radar");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);

  useEffect(() => {
    void loadCapabilities()
      .then((capabilities) => setAiAvailable(capabilities.aiExplanationAvailable))
      .catch(() => setAiAvailable(false));
  }, []);

  const counts = useMemo(() => {
    const nodes = graph?.nodes ?? [];
    return {
      files: nodes.filter((node) => node.type === "FILE").length,
      functions: nodes.filter((node) => node.type === "FUNCTION").length,
      classes: nodes.filter((node) => node.type === "CLASS").length,
      imports: graph?.edges.filter((edge) => edge.type === "IMPORTS").length ?? 0,
    };
  }, [graph]);

  async function runAnalyze(value: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const response = await analyzeRepository(value);
      setAnalysisId(response.analysis_id);
      setGraph(response.graph);
      setRepository(response.repository);
      setSelectedId(response.graph.nodes[0]?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runDemo(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const response = await loadDemoGraph();
      setAnalysisId(response.analysis_id);
      setGraph(response.graph);
      setRepository(response.repository);
      setSelectedId(response.graph.nodes.find((node) => node.type === "FILE")?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Demo failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Boxes size={24} aria-hidden="true" />
          <div>
            <h1>CodeAtlas</h1>
            <span>Codebase memory graph</span>
          </div>
        </div>
        <RepoInput
          defaultRepository="gogun-rgb/ai-hype-radar"
          disabled={loading}
          onAnalyze={(value) => void runAnalyze(value)}
          onDemo={() => void runDemo()}
        />
      </header>

      <section className="status-strip">
        <strong>{repository}</strong>
        <span>{counts.files} files</span>
        <span>{counts.functions} functions</span>
        <span>{counts.classes} classes</span>
        <span>{counts.imports} imports</span>
        {loading ? (
          <span className="loading">
            <Loader2 size={15} aria-hidden="true" /> Analyzing
          </span>
        ) : null}
      </section>

      {error ? (
        <div className="notice error">
          <AlertTriangle size={18} aria-hidden="true" />
          {error}
        </div>
      ) : null}
      {graph?.warnings.map((warning) => (
        <div className="notice" key={warning}>
          <AlertTriangle size={18} aria-hidden="true" />
          {warning}
        </div>
      ))}

      <main className="workspace">
        <FileTree graph={graph} selectedId={selectedId} onSelect={setSelectedId} />
        <section className="center-workspace">
          <FiltersBar filters={filters} onChange={setFilters} />
          <GraphCanvas
            graph={graph}
            filters={filters}
            selectedId={selectedId}
            searchTerm={searchTerm}
            onSearchTerm={setSearchTerm}
            onSelect={setSelectedId}
          />
        </section>
        <aside className="right-rail">
          <Inspector graph={graph} selectedId={selectedId} />
          <QuestionPanel analysisId={analysisId} aiAvailable={aiAvailable} />
        </aside>
      </main>
    </div>
  );
}
