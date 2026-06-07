'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  MiniMap,
  Background,
  Node,
  Edge,
  Handle,
  MarkerType,
  NodeChange,
  OnNodeDrag,
  Position,
  ReactFlow,
  ReactFlowInstance,
  ReactFlowProvider,
  Viewport,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Character, Relationship, TimelineEntry } from '@/lib/types';

interface RelationshipGraphProps {
  characters: Character[];
  timeline?: TimelineEntry[];
  projectId?: string;
  onNodeClick?: (characterId: string) => void;
}

interface CharacterNodeData extends Record<string, unknown> {
  label: string;
  role: string;
  id: string;
}

type CharacterFlowNode = Node<CharacterNodeData>;

type SavedGraphLayout = {
  nodes: Record<string, { x: number; y: number }>;
  viewport?: Viewport;
  height?: number;
};

const DEFAULT_GRAPH_HEIGHT = 460;
const MIN_GRAPH_HEIGHT = 320;
const MAX_GRAPH_HEIGHT = 920;
const NODE_TYPES = {
  character: CharacterNode,
};

function CharacterNode({ data }: { data: CharacterNodeData }) {
  const roleColors: Record<string, string> = {
    protagonist: 'var(--color-accent)',
    antagonist: 'var(--color-warning)',
    supporting: 'var(--color-teal)',
    minor: 'var(--color-muted)',
    narrator: 'var(--color-accent-dim)',
  };

  const borderColor = roleColors[data.role] || 'var(--color-border)';
  const roleLabels: Record<string, string> = {
    protagonist: '主角',
    antagonist: '反派',
    supporting: '配角',
    minor: '次要',
    narrator: '叙述者',
  };

  return (
    <div
      className="rounded-md px-3 py-2 text-center shadow-sm"
      style={{
        backgroundColor: 'var(--color-surface)',
        border: `2px solid ${borderColor}`,
        color: 'var(--color-foreground)',
        fontSize: '12px',
        minWidth: '88px',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="relationship-graph-handle"
      />
      <Handle
        type="target"
        position={Position.Left}
        className="relationship-graph-handle"
      />
      <div className="font-semibold leading-5">{data.label}</div>
      <div className="text-xs leading-4" style={{ color: borderColor }}>
        {roleLabels[data.role] || data.role}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="relationship-graph-handle"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="relationship-graph-handle"
      />
    </div>
  );
}

function RelationshipGraphInner({ characters, timeline = [], projectId, onNodeClick }: RelationshipGraphProps) {
  const storageKey = useMemo(
    () => getGraphStorageKey(characters, projectId),
    [characters, projectId]
  );
  const savedLayout = useMemo(() => readSavedGraphLayout(storageKey), [storageKey]);
  const reactFlowRef = useRef<ReactFlowInstance<CharacterFlowNode, Edge> | null>(null);
  const hideMiniMapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paneDragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    isDragging: boolean;
  } | null>(null);
  const [isMiniMapVisible, setIsMiniMapVisible] = useState(false);
  const [height, setHeight] = useState(savedLayout?.height ?? DEFAULT_GRAPH_HEIGHT);

  const initialNodes: CharacterFlowNode[] = useMemo(
    () => buildCharacterNodes(characters, savedLayout),
    [characters, savedLayout]
  );

  const initialEdges: Edge[] = useMemo(
    () => buildRelationshipEdges(characters, timeline),
    [characters, timeline]
  );

  const [nodes, setNodes, onNodesChangeBase] = useNodesState<CharacterFlowNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const saveLayout = useCallback((nextNodes = nodes, nextHeight = height, viewport?: Viewport) => {
    const currentViewport = viewport ?? reactFlowRef.current?.getViewport();
    writeSavedGraphLayout(storageKey, {
      nodes: nextNodes.reduce<SavedGraphLayout['nodes']>((acc, node) => {
        acc[node.id] = { x: node.position.x, y: node.position.y };
        return acc;
      }, {}),
      viewport: currentViewport,
      height: nextHeight,
    });
  }, [height, nodes, storageKey]);

  useEffect(() => {
    const saved = readSavedGraphLayout(storageKey);
    setNodes(buildCharacterNodes(characters, saved));
    setEdges(buildRelationshipEdges(characters, timeline));
    setHeight(saved?.height ?? DEFAULT_GRAPH_HEIGHT);
  }, [characters, setEdges, setNodes, storageKey, timeline]);

  useEffect(() => {
    return () => {
      if (hideMiniMapTimerRef.current) {
        clearTimeout(hideMiniMapTimerRef.current);
      }
    };
  }, []);

  const revealMiniMap = useCallback(() => {
    if (hideMiniMapTimerRef.current) {
      clearTimeout(hideMiniMapTimerRef.current);
    }
    setIsMiniMapVisible(true);
  }, []);

  const scheduleMiniMapHide = useCallback(() => {
    if (hideMiniMapTimerRef.current) {
      clearTimeout(hideMiniMapTimerRef.current);
    }
    hideMiniMapTimerRef.current = setTimeout(() => {
      setIsMiniMapVisible(false);
    }, 900);
  }, []);

  const handleNodesChange = useCallback((changes: NodeChange<CharacterFlowNode>[]) => {
    onNodesChangeBase(changes);
  }, [onNodesChangeBase]);

  const handleNodeDragStop: OnNodeDrag<CharacterFlowNode> = useCallback((event, node, draggedNodes) => {
    const movedNodeIds = new Set([node.id, ...draggedNodes.map((item) => item.id)]);
    const currentNodes = reactFlowRef.current?.getNodes() ?? nodes;
    const nextNodes = currentNodes.map((item) => {
      if (item.id === node.id) {
        return { ...item, position: node.position };
      }
      const dragged = draggedNodes.find((candidate) => candidate.id === item.id);
      return dragged && movedNodeIds.has(item.id)
        ? { ...item, position: dragged.position }
        : item;
    });
    setNodes(nextNodes);
    saveLayout(nextNodes);
  }, [nodes, saveLayout, setNodes]);

  const handleFlowPointerDownCapture = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !isPaneDragTarget(event.target)) return;
    paneDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      isDragging: false,
    };
  }, []);

  const handleFlowPointerMoveCapture = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const paneDrag = paneDragRef.current;
    if (!paneDrag || paneDrag.pointerId !== event.pointerId) return;

    const deltaX = event.clientX - paneDrag.startX;
    const deltaY = event.clientY - paneDrag.startY;
    if (!paneDrag.isDragging && Math.hypot(deltaX, deltaY) < 4) return;

    paneDrag.isDragging = true;
    revealMiniMap();
  }, [revealMiniMap]);

  const handleFlowPointerEndCapture = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const paneDrag = paneDragRef.current;
    if (!paneDrag || paneDrag.pointerId !== event.pointerId) return;

    paneDragRef.current = null;
    if (paneDrag.isDragging) {
      saveLayout(nodes, height);
      scheduleMiniMapHide();
    }
  }, [height, nodes, saveLayout, scheduleMiniMapHide]);

  const handleResizePointerDown = useCallback((event: React.PointerEvent<HTMLButtonElement>) => {
    const startY = event.clientY;
    const startHeight = height;
    document.body.classList.add('is-resizing-relationship-graph');

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const nextHeight = clamp(startHeight + moveEvent.clientY - startY, MIN_GRAPH_HEIGHT, MAX_GRAPH_HEIGHT);
      setHeight(nextHeight);
    };

    const handlePointerUp = (upEvent: PointerEvent) => {
      const nextHeight = clamp(startHeight + upEvent.clientY - startY, MIN_GRAPH_HEIGHT, MAX_GRAPH_HEIGHT);
      setHeight(nextHeight);
      saveLayout(nodes, nextHeight);
      document.body.classList.remove('is-resizing-relationship-graph');
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  }, [height, nodes, saveLayout]);

  const handleResizeKeyDown = useCallback((event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const delta = event.shiftKey ? 80 : 24;
    const nextHeight = event.key === 'Home'
      ? MIN_GRAPH_HEIGHT
      : event.key === 'End'
        ? MAX_GRAPH_HEIGHT
        : clamp(height + (event.key === 'ArrowDown' ? delta : -delta), MIN_GRAPH_HEIGHT, MAX_GRAPH_HEIGHT);
    setHeight(nextHeight);
    saveLayout(nodes, nextHeight);
  }, [height, nodes, saveLayout]);

  const handleResizeReset = useCallback(() => {
    setHeight(DEFAULT_GRAPH_HEIGHT);
    saveLayout(nodes, DEFAULT_GRAPH_HEIGHT);
  }, [nodes, saveLayout]);

  if (characters.length === 0) {
    return (
      <div
        className="flex h-[320px] items-center justify-center rounded-md border text-sm"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-muted)' }}
      >
        暂无人物关系
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border" style={{ borderColor: 'var(--color-border)' }}>
      <div
        className="w-full"
        style={{ height, backgroundColor: 'var(--color-base)' }}
      >
        <ReactFlow<CharacterFlowNode, Edge>
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={handleNodeDragStop}
          onMoveStart={revealMiniMap}
          onMove={revealMiniMap}
          onMoveEnd={(event, viewport) => {
            saveLayout(nodes, height, viewport);
            scheduleMiniMapHide();
          }}
          onInit={(instance) => {
            reactFlowRef.current = instance;
            if (savedLayout?.viewport) {
              window.requestAnimationFrame(() => {
                instance.setViewport(savedLayout.viewport as Viewport, { duration: 0 });
              });
            } else {
              window.requestAnimationFrame(() => {
                instance.fitView({ padding: 0.16, duration: 0 });
              });
            }
          }}
          nodeTypes={NODE_TYPES}
          onNodeClick={(event, node) => {
            onNodeClick?.(node.id);
          }}
          fitView={!savedLayout?.viewport}
          minZoom={0.35}
          maxZoom={1.8}
          defaultEdgeOptions={{ type: 'smoothstep' }}
          proOptions={{ hideAttribution: true }}
          className="relationship-graph-flow"
          onPointerDownCapture={handleFlowPointerDownCapture}
          onPointerMoveCapture={handleFlowPointerMoveCapture}
          onPointerUpCapture={handleFlowPointerEndCapture}
          onPointerCancelCapture={handleFlowPointerEndCapture}
        >
          <Background
            color="oklch(0.30 0.02 260)"
            gap={20}
            size={1}
          />
          <MiniMap
            className={`relationship-graph-minimap ${isMiniMapVisible ? 'visible' : ''}`}
            pannable
            zoomable
            bgColor="oklch(0.18 0.02 260)"
            maskColor="oklch(0.10 0.02 260 / 0.55)"
            style={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 6,
              overflow: 'hidden',
            }}
            nodeColor={(node) => {
              const roleColors: Record<string, string> = {
                protagonist: 'oklch(0.75 0.15 75)',
                antagonist: 'oklch(0.65 0.18 25)',
                supporting: 'oklch(0.55 0.12 150)',
                minor: 'oklch(0.55 0.02 260)',
                narrator: 'oklch(0.60 0.10 75)',
              };
              const role = (node.data as { role?: string })?.role ?? '';
              return roleColors[role] || 'oklch(0.35 0.03 260)';
            }}
          />
        </ReactFlow>
      </div>

      <button
        type="button"
        className="relationship-graph-resize-handle flex h-5 w-full items-center justify-center border-t"
        style={{
          borderColor: 'var(--color-border)',
          backgroundColor: 'var(--color-surface)',
          color: 'var(--color-muted)',
        }}
        onPointerDown={handleResizePointerDown}
        onKeyDown={handleResizeKeyDown}
        onDoubleClick={handleResizeReset}
        aria-label="调整关系图谱高度"
        title="拖动调整图谱高度，双击恢复默认高度"
      >
        <span className="h-1 w-12 rounded-full" style={{ backgroundColor: 'var(--color-border)' }} />
      </button>
    </div>
  );
}

function buildCharacterNodes(
  characters: Character[],
  savedLayout: SavedGraphLayout | null
): CharacterFlowNode[] {
  const columns = Math.min(Math.max(Math.ceil(Math.sqrt(characters.length)), 3), 5);

  return characters.map((char, index) => ({
    id: char.id,
    type: 'character',
    position: savedLayout?.nodes[char.id] ?? {
      x: 90 + (index % columns) * 170,
      y: 80 + Math.floor(index / columns) * 120,
    },
    data: {
      label: char.name,
      role: char.role,
      id: char.id,
    },
  }));
}

function buildRelationshipEdges(characters: Character[], timeline: TimelineEntry[]): Edge[] {
  const edges: Edge[] = [];
  const seen = new Set<string>();
  const characterLookup = buildCharacterLookup(characters);

  characters.forEach((char) => {
    const relationships = Array.isArray(char.relationships) ? char.relationships : [];
    relationships.forEach((rel: Relationship, relIndex) => {
      const targetId = resolveRelationshipTargetId(rel.target_id, characterLookup);
      if (!targetId || targetId === char.id) return;

      const pairKey = [char.id, targetId].sort().join('__');
      const directedKey = `${char.id}->${targetId}:${rel.type || relIndex}`;
      const edgeKey = rel.type ? directedKey : pairKey;
      if (seen.has(edgeKey)) return;
      seen.add(edgeKey);

      edges.push(createRelationshipEdge({
        id: `edge-${char.id}-${targetId}-${relIndex}`,
        source: char.id,
        target: targetId,
        label: rel.type || '关系',
        color: 'oklch(0.55 0.12 150)',
        labelColor: 'oklch(0.82 0.04 150)',
      }));
    });
  });

  if (edges.length > 0) return edges;

  const coAppearances = new Map<string, { source: string; target: string; count: number }>();
  timeline.forEach((entry) => {
    const characterIds = Array.from(
      new Set(
        (entry.characters || [])
          .map((value) => resolveRelationshipTargetId(value, characterLookup))
          .filter((value): value is string => Boolean(value))
      )
    );

    for (let i = 0; i < characterIds.length; i += 1) {
      for (let j = i + 1; j < characterIds.length; j += 1) {
        const [source, target] = [characterIds[i], characterIds[j]].sort();
        const key = `${source}__${target}`;
        const current = coAppearances.get(key);
        coAppearances.set(key, {
          source,
          target,
          count: (current?.count ?? 0) + 1,
        });
      }
    }
  });

  Array.from(coAppearances.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, Math.max(8, characters.length + 2))
    .forEach((item, index) => {
      edges.push(createRelationshipEdge({
        id: `coappear-${item.source}-${item.target}-${index}`,
        source: item.source,
        target: item.target,
        label: `共同事件 ${item.count}`,
        color: 'oklch(0.75 0.15 75)',
        labelColor: 'oklch(0.88 0.08 75)',
      }));
    });

  return edges;
}

function createRelationshipEdge({
  id,
  source,
  target,
  label,
  color,
  labelColor,
}: {
  id: string;
  source: string;
  target: string;
  label: string;
  color: string;
  labelColor: string;
}): Edge {
  return {
    id,
    source,
    target,
    type: 'smoothstep',
    label,
    labelBgPadding: [6, 3],
    labelBgBorderRadius: 4,
    labelBgStyle: {
      fill: 'oklch(0.22 0.03 260)',
      fillOpacity: 0.92,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 16,
      height: 16,
      color,
    },
    style: {
      stroke: color,
      strokeWidth: 1.8,
    },
    labelStyle: {
      fill: labelColor,
      fontSize: 11,
      fontWeight: 600,
    },
  };
}

function buildCharacterLookup(characters: Character[]) {
  const lookup = new Map<string, string>();
  characters.forEach((char) => {
    [char.id, char.name, ...(char.aliases || [])].forEach((value) => {
      const key = normalizeRelationshipKey(value);
      if (key) lookup.set(key, char.id);
    });
  });
  return lookup;
}

function resolveRelationshipTargetId(target: string, lookup: Map<string, string>) {
  return lookup.get(normalizeRelationshipKey(target));
}

function normalizeRelationshipKey(value: string | undefined | null) {
  return (value || '').trim().toLowerCase();
}

function getGraphStorageKey(characters: Character[], projectId?: string) {
  if (projectId) {
    return `novelscripter_relationship_graph_layout_v2:${projectId}`;
  }
  const characterKey = characters.map((char) => char.id).sort().join(',');
  return `novelscripter_relationship_graph_layout_v2:characters:${characterKey}`;
}

function readSavedGraphLayout(storageKey: string): SavedGraphLayout | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SavedGraphLayout>;
    return {
      nodes: parsed.nodes && typeof parsed.nodes === 'object' ? parsed.nodes : {},
      viewport: isViewport(parsed.viewport) ? parsed.viewport : undefined,
      height: typeof parsed.height === 'number'
        ? clamp(parsed.height, MIN_GRAPH_HEIGHT, MAX_GRAPH_HEIGHT)
        : undefined,
    };
  } catch {
    return null;
  }
}

function writeSavedGraphLayout(storageKey: string, layout: SavedGraphLayout) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(layout));
  } catch {
    // localStorage failures should not block graph editing.
  }
}

function isViewport(value: unknown): value is Viewport {
  if (!value || typeof value !== 'object') return false;
  const viewport = value as Partial<Viewport>;
  return (
    typeof viewport.x === 'number' &&
    typeof viewport.y === 'number' &&
    typeof viewport.zoom === 'number'
  );
}

function isPaneDragTarget(target: EventTarget | null) {
  return target instanceof Element &&
    Boolean(target.closest('.react-flow__pane')) &&
    !target.closest('.react-flow__node, .react-flow__edge, .react-flow__minimap');
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export default function RelationshipGraph(props: RelationshipGraphProps) {
  return (
    <ReactFlowProvider>
      <RelationshipGraphInner {...props} />
    </ReactFlowProvider>
  );
}
