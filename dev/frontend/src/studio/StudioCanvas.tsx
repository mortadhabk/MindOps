import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  type NodeTypes,
  type OnNodeDrag,
  ReactFlow,
  useReactFlow,
} from "@xyflow/react";
import { type DragEvent, useCallback, useMemo, useRef } from "react";

import type { ConnectorInstance, ConnectorType } from "../lib/api";
import { CONNECTOR_DRAG_FORMAT } from "./ConnectorPalette";
import { ConnectorNode, type ConnectorNodeData } from "./ConnectorNode";
import { OrchestratorNode } from "./OrchestratorNode";

const ORCHESTRATOR_NODE_ID = "orchestrator";

const nodeTypes: NodeTypes = {
  orchestrator: OrchestratorNode,
  connector: ConnectorNode,
};

interface StudioCanvasProps {
  instances: ConnectorInstance[];
  onDropType: (type: ConnectorType, position: { x: number; y: number }) => void;
  onMoveInstance: (id: number, x: number, y: number) => void;
  onSyncInstance: (id: number) => void;
  onDeleteInstance: (id: number) => void;
}

export function StudioCanvas({
  instances,
  onDropType,
  onMoveInstance,
  onSyncInstance,
  onDeleteInstance,
}: StudioCanvasProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  const nodes: Node[] = useMemo(() => {
    const orchestratorNode: Node = {
      id: ORCHESTRATOR_NODE_ID,
      type: "orchestrator",
      position: { x: 520, y: 220 },
      draggable: false,
      selectable: false,
      data: {},
    };
    const connectorNodes: Node<ConnectorNodeData>[] = instances.map((instance) => ({
      id: String(instance.id),
      type: "connector",
      position: { x: instance.position_x, y: instance.position_y },
      data: { instance, onSync: onSyncInstance, onDelete: onDeleteInstance },
    }));
    return [orchestratorNode, ...connectorNodes];
  }, [instances, onSyncInstance, onDeleteInstance]);

  const edges: Edge[] = useMemo(
    () =>
      instances.map((instance) => ({
        id: `edge-${instance.id}`,
        source: String(instance.id),
        target: ORCHESTRATOR_NODE_ID,
        animated: instance.status === "syncing",
        style: { stroke: "rgba(129,140,248,0.5)" },
      })),
    [instances],
  );

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData(CONNECTOR_DRAG_FORMAT);
      if (!raw) return;
      const type: ConnectorType = JSON.parse(raw);
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      onDropType(type, position);
    },
    [onDropType, screenToFlowPosition],
  );

  const onNodeDragStop: OnNodeDrag<Node> = useCallback(
    (_event, node) => {
      if (node.id === ORCHESTRATOR_NODE_ID) return;
      onMoveInstance(Number(node.id), node.position.x, node.position.y);
    },
    [onMoveInstance],
  );

  return (
    <div
      ref={wrapperRef}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className="flex-1 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeDragStop={onNodeDragStop}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#252a3a" />
        <Controls className="!border-white/10 !bg-surface-800 [&_button]:!border-white/10 [&_button]:!bg-surface-800 [&_button]:!fill-slate-300" />
        <MiniMap className="!bg-surface-800" maskColor="rgba(5,6,10,0.6)" nodeColor="#6366f1" />
      </ReactFlow>
    </div>
  );
}
