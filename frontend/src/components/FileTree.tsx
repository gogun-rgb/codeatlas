import { FileCode2 } from "lucide-react";
import type { ReactElement } from "react";
import type { CodeGraph } from "../types";
import { fileNodes } from "../graphUtils";

interface Props {
  graph: CodeGraph | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function FileTree({ graph, selectedId, onSelect }: Props): ReactElement {
  const files = graph ? fileNodes(graph) : [];
  return (
    <aside className="panel file-tree">
      <div className="panel-header">
        <h2>Files</h2>
        <span>{files.length}</span>
      </div>
      <div className="file-list">
        {files.map((file) => (
          <button
            key={file.id}
            type="button"
            className={file.id === selectedId ? "is-active" : ""}
            onClick={() => onSelect(file.id)}
          >
            <FileCode2 size={15} aria-hidden="true" />
            <span>{file.path}</span>
          </button>
        ))}
        {files.length === 0 ? <p className="empty">Load a demo or analyze a public repository.</p> : null}
      </div>
    </aside>
  );
}
