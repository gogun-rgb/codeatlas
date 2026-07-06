import type { ReactElement } from "react";

import type { CodeGraph, GraphNode } from "../types";
import { importedByForPath, importEdgesForPath, symbolNodesForPath } from "../graphUtils";

interface Props {
  graph: CodeGraph | null;
  selectedId: string | null;
}

export function Inspector({ graph, selectedId }: Props): ReactElement {
  const node = graph?.nodes.find((item) => item.id === selectedId) ?? null;
  return (
    <section className="panel inspector">
      <div className="panel-header">
        <h2>Inspector</h2>
      </div>
      {graph && node ? <NodeDetails graph={graph} node={node} /> : <p className="empty">Select a node.</p>}
    </section>
  );
}

function NodeDetails({ graph, node }: { graph: CodeGraph; node: GraphNode }): ReactElement {
  if (node.type === "FILE") {
    const symbols = symbolNodesForPath(graph, node.path);
    const imports = importEdgesForPath(graph, node.path)
      .map((edge) => graph.nodes.find((item) => item.id === edge.target)?.path)
      .filter((path): path is string => Boolean(path));
    const importedBy = importedByForPath(graph, node.path);
    const unresolved = asStringList(node.metadata.unresolvedLocalImports);
    const parserErrors = asStringList(node.metadata.parserErrors);
    return (
      <div className="details">
        <Kicker value="FILE" />
        <h3>{node.path}</h3>
        {parserErrors.length ? (
          <div className="parser-warning" role="alert">
            <h4>Parser warning</h4>
            <p>This file contains syntax or parser errors. Graph data may be incomplete.</p>
          </div>
        ) : null}
        <DetailList title="Functions" values={symbols.filter((item) => item.type === "FUNCTION").map((item) => item.label)} />
        <DetailList title="Classes" values={symbols.filter((item) => item.type === "CLASS").map((item) => item.label)} />
        <DetailList title="Imports" values={imports} />
        <DetailList title="Imported by" values={importedBy} />
        <DetailList title="Unresolved local imports" values={unresolved} />
      </div>
    );
  }

  return (
    <div className="details">
      <Kicker value={node.type} />
      <h3>{node.label}</h3>
      <dl>
        <div>
          <dt>Path</dt>
          <dd>{node.path}</dd>
        </div>
        <div>
          <dt>Lines</dt>
          <dd>
            {String(node.metadata.startLine ?? "?")} - {String(node.metadata.endLine ?? "?")}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function DetailList({ title, values }: { title: string; values: string[] }): ReactElement {
  return (
    <div className="detail-block">
      <h4>{title}</h4>
      {values.length ? (
        <ul>
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <span className="muted">None</span>
      )}
    </div>
  );
}

function Kicker({ value }: { value: string }): ReactElement {
  return <span className="kicker">{value}</span>;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}
