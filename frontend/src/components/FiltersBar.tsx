import type { ReactElement } from "react";

import type { Filters, NodeType } from "../types";

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

const OPTIONS: Array<{ key: NodeType; label: string }> = [
  { key: "FILE", label: "Files" },
  { key: "FUNCTION", label: "Functions" },
  { key: "CLASS", label: "Classes" },
];

export function FiltersBar({ filters, onChange }: Props): ReactElement {
  return (
    <div className="filters-bar" aria-label="Graph filters">
      {OPTIONS.map((option) => (
        <label key={option.key}>
          <input
            type="checkbox"
            checked={filters[option.key]}
            onChange={(event) => onChange({ ...filters, [option.key]: event.target.checked })}
          />
          <span>{option.label}</span>
        </label>
      ))}
    </div>
  );
}
