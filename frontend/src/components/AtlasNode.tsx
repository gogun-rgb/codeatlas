import { memo, type ReactElement } from "react";
import type { NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import { Braces, FileCode2, FunctionSquare } from "lucide-react";
import type { AtlasNodeData } from "../layout";

function AtlasNodeComponent({ data, selected }: NodeProps): ReactElement {
  const graphNode = (data as AtlasNodeData).graphNode;
  const highlighted = Boolean((data as AtlasNodeData).highlighted);
  const Icon =
    graphNode.type === "FILE" ? FileCode2 : graphNode.type === "CLASS" ? Braces : FunctionSquare;
  return (
    <div className={`atlas-node atlas-node-${graphNode.type.toLowerCase()} ${selected ? "is-selected" : ""} ${highlighted ? "is-highlighted" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="atlas-node-icon">
        <Icon size={16} aria-hidden="true" />
      </div>
      <div className="atlas-node-text">
        <strong>{graphNode.label}</strong>
        <span>{graphNode.type}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const AtlasNode = memo(AtlasNodeComponent);
