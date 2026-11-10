import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { transitionGroups } from "../services/replay";
const positions = {
  LOGGED_OUT: [0, 0],
  AUTHENTICATING: [260, 0],
  AUTHENTICATED: [520, 0],
  VIEWING_ACCOUNT: [780, 0],
  TRANSFER_PENDING: [520, 230],
  CLOSED: [780, 230],
  BLOCKED: [260, 230],
  REJECTED: [0, 230],
};
function StateNode({ data }) {
  return (
    <div
      className={`fsm-node ${data.active ? "current" : ""} ${data.accepting ? "accepting" : ""} ${data.active && data.id === "REJECTED" ? "invalid" : ""} ${data.active && data.id === "BLOCKED" ? "blocked" : ""}`}
      data-state={data.id}
      data-current={data.active}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Left} id="back-out" />
      <span>{data.id.replaceAll("_", " ")}</span>
      <small>
        {data.accepting
          ? "Accepting state"
          : data.id === "REJECTED"
            ? "Rejecting sink"
            : data.id === "BLOCKED"
              ? "Enforced restriction"
              : data.id === "LOGGED_OUT"
                ? "Initial state"
                : "Session state"}
      </small>
      <Handle type="source" position={Position.Right} id="out" />
      <Handle type="target" position={Position.Right} id="back-in" />
    </div>
  );
}
function ProtocolEdge(props) {
  const { sourceX, sourceY, targetX, targetY, data, id, markerEnd, style } =
    props;
  const self = props.source === props.target;
  const [normalPath, x, y] = getBezierPath({ ...props, curvature: 0.3 });
  const rejectingBack = data.invalid && targetX < sourceX;
  const path = rejectingBack
    ? `M ${sourceX},${sourceY} C ${sourceX - 60},${sourceY + 120} ${targetX + 60},${targetY + 120} ${targetX},${targetY}`
    : self
      ? `M ${sourceX},${sourceY} C ${sourceX + 65},${sourceY - 120} ${targetX - 65},${targetY - 120} ${targetX},${targetY}`
      : normalPath;
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <span
          className={`fsm-edge-label ${data.active ? "active" : ""} ${data.invalid ? "invalid" : ""}`}
          style={{
            transform: `translate(-50%,-50%) translate(${self || rejectingBack ? (sourceX + targetX) / 2 : x}px,${rejectingBack ? (sourceY + targetY) / 2 + 95 : self ? sourceY - 90 : y + (targetX < sourceX ? -18 : 14)}px)`,
          }}
          title={data.events.join(", ")}
        >
          {data.active ? data.event : data.events[0]}
          {!data.active && data.events.length > 1
            ? ` +${data.events.length - 1}`
            : ""}
        </span>
      </EdgeLabelRenderer>
    </>
  );
}
const nodeTypes = { protocol: StateNode },
  edgeTypes = { protocol: ProtocolEdge };
export default function FSMGraph({
  definition,
  currentState,
  transition,
  showEnforcement,
}) {
  const nodes = definition.states.map((state, index) => {
    const position = positions[state] || [index * 250, 450];
    return {
      id: state,
      type: "protocol",
      position: { x: position[0], y: position[1] },
      data: {
        id: state,
        active: state === currentState,
        accepting: definition.accepting_states.includes(state),
      },
    };
  });
  const edges = transitionGroups(definition, transition, showEnforcement).map(
    (group, index) => {
      const color = group.invalid
        ? "#dd7286"
        : group.active
          ? "#7aa9f5"
          : "#41414f";
      return {
        id: `transition-${index}`,
        source: group.source,
        target: group.target,
        sourceHandle:
          positions[group.source]?.[0] > positions[group.target]?.[0]
            ? "back-out"
            : "out",
        targetHandle:
          positions[group.source]?.[0] > positions[group.target]?.[0]
            ? "back-in"
            : "in",
        type: "protocol",
        data: { ...group, event: transition?.event },
        markerEnd: { type: "arrowclosed", color, width: 14, height: 14 },
        style: {
          stroke: color,
          strokeWidth: group.active ? 2.3 : 1.1,
          strokeDasharray: group.invalid ? "5 4" : undefined,
        },
        zIndex: group.active ? 10 : 0,
      };
    },
  );
  return (
    <div className="fsm-canvas" aria-label="Banking session state graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#33333d" gap={23} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
