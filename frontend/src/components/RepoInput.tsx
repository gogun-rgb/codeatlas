import { useState, type FormEvent, type ReactElement } from "react";
import { Database, Github, Play } from "lucide-react";

interface Props {
  defaultRepository: string;
  disabled: boolean;
  onAnalyze: (repository: string) => void;
  onDemo: () => void;
}

export function RepoInput({
  defaultRepository,
  disabled,
  onAnalyze,
  onDemo,
}: Props): ReactElement {
  const [repository, setRepository] = useState(defaultRepository);

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onAnalyze(repository);
  }

  return (
    <form className="repo-input" onSubmit={submit}>
      <label htmlFor="repository">Repository</label>
      <div className="repo-input-row">
        <Github size={18} aria-hidden="true" />
        <input
          id="repository"
          value={repository}
          onChange={(event) => setRepository(event.target.value)}
          placeholder="owner/repo or https://github.com/owner/repo"
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || repository.trim().length === 0} title="Analyze repository">
          <Play size={16} aria-hidden="true" />
          Analyze
        </button>
        <button type="button" onClick={onDemo} disabled={disabled} title="Load demo graph">
          <Database size={16} aria-hidden="true" />
          Demo
        </button>
      </div>
    </form>
  );
}
