import type { Edge, Node } from "@xyflow/svelte";
import type { VizEvent } from "$domain/types";

const NODE_SIZE_FALLBACK: { [key: string]: { width: number; height: number } } = {
  stage: { width: 190, height: 64 },
  source: { width: 170, height: 68 },
  loader: { width: 170, height: 68 },
  field: { width: 170, height: 68 },
  derived: { width: 170, height: 68 },
  output_target: { width: 180, height: 72 },
  default: { width: 160, height: 64 }
};

const STAGE_BAND_PADDING = { x: 60, y: 40 };
const INGEST_BAND_PADDING = { x: 36, y: 26 };
const TIMELINE_COLUMN_GAP_MIN = 60;
const TIMELINE_COLUMN_GAP_MAX = 140;
const TIMELINE_ROW_GAP_MIN = 120;
const TIMELINE_ROW_GAP_MAX = 170;
const TIMELINE_ROW_PADDING = INGEST_BAND_PADDING.y * 2 + 16;
const TIMELINE_START = { x: 80, y: 80 };

const EDGE_STYLE_BASE = "stroke:#94a3b8;stroke-width:1.2;";
const EDGE_STYLE_REF_LOOKUP = "stroke:#64748b;stroke-width:1.1;stroke-dasharray:2 5;opacity:0.65;";
const EDGE_STYLE_LOADS_FROM = "stroke:#64748b;stroke-width:1.1;stroke-dasharray:6 4;opacity:0.55;";
const EDGE_STYLE_PLAN_OVERLAY = "stroke:#22c55e;stroke-width:1.4;stroke-dasharray:4 5;opacity:0.75;";
const EDGE_STYLE_FOCUS = "stroke:#2563eb;stroke-width:2;";
const EDGE_STYLE_ACTIVE = "stroke:#0ea5e9;stroke-width:2.4;";
const EDGE_STYLE_DIM = "stroke:#cbd5e1;stroke-width:1;opacity:0.35;";
const EDGE_STYLE_HIDDEN = "stroke:#cbd5e1;stroke-width:1;opacity:0;";

const clamp = (value: number, min: number, max: number) => {
  return Math.min(Math.max(value, min), max);
};

export const getStageLevel = (node: Node): number | null => {
  const raw = node.data?.level ?? node.data?.stage_level;
  if (raw === undefined || raw === null || Number.isNaN(Number(raw))) {
    return null;
  }
  return Number(raw);
};

export const getNodeSize = (node: Node) => {
  const measured = (node as any).measured;
  const fallback = NODE_SIZE_FALLBACK[node.type ?? "default"] || NODE_SIZE_FALLBACK.default;
  const width = measured?.width ?? (node as any).width ?? fallback.width;
  const height = measured?.height ?? (node as any).height ?? fallback.height;
  return { width, height };
};

export const getBandMembers = (node: Node) => {
  const members = (node.data as any)?.members;
  if (Array.isArray(members)) {
    return members.filter((item) => typeof item === "string");
  }
  return [];
};

export const statusFromEvent = (eventType: string) => {
  if (!eventType) return "";
  if (eventType.indexOf("error") >= 0 || eventType.indexOf("failed") >= 0) {
    return "error";
  }
  if (
    eventType.indexOf("completed") >= 0 ||
    eventType.indexOf("computed") >= 0 ||
    eventType.indexOf("written") >= 0
  ) {
    return "success";
  }
  if (eventType.indexOf("started") >= 0 || eventType.indexOf("called") >= 0) {
    return "warn";
  }
  return "info";
};

export const restoreBasePositions = (
  list: Node[],
  baseNodePositions: Map<string, { x: number; y: number }>
) => {
  if (!baseNodePositions.size) return list;
  return list.map((node) => {
    const base = baseNodePositions.get(node.id);
    if (!base) return node;
    return { ...node, position: { x: base.x, y: base.y } };
  });
};

export const applyTimelineLayout = (
  list: Node[],
  sequenceSet: Set<string>,
  baseNodePositions: Map<string, { x: number; y: number }>
) => {
  if (!sequenceSet.size) return list;
  const groups = new Map<number, Node[]>();
  const groupMeta = new Map<number, { maxWidth: number; maxHeight: number }>();
  for (const node of list) {
    if (node.type === "stage_band" || node.type === "stage" || node.type === "ingest_band") {
      continue;
    }
    if (!sequenceSet.has(node.id)) continue;
    const level = getStageLevel(node);
    const key = level === null ? -1 : level;
    const bucket = groups.get(key) ?? [];
    bucket.push(node);
    groups.set(key, bucket);
    const size = getNodeSize(node);
    const meta = groupMeta.get(key) ?? { maxWidth: 0, maxHeight: 0 };
    meta.maxWidth = Math.max(meta.maxWidth, size.width);
    meta.maxHeight = Math.max(meta.maxHeight, size.height);
    groupMeta.set(key, meta);
  }
  const orderedLevels = Array.from(groups.keys()).sort((a, b) => a - b);
  const positions = new Map<string, { x: number; y: number }>();
  let cursorX = TIMELINE_START.x;
  orderedLevels.forEach((level) => {
    const items = groups.get(level) ?? [];
    const sorted = items.slice().sort((a, b) => {
      const ay = baseNodePositions.get(a.id)?.y ?? a.position?.y ?? 0;
      const by = baseNodePositions.get(b.id)?.y ?? b.position?.y ?? 0;
      return ay - by;
    });
    const meta = groupMeta.get(level) ?? { maxWidth: 170, maxHeight: 68 };
    const bandWidth = meta.maxWidth + STAGE_BAND_PADDING.x * 2;
    const gap = clamp(Math.round(bandWidth * 0.2), TIMELINE_COLUMN_GAP_MIN, TIMELINE_COLUMN_GAP_MAX);
    const rowGap = clamp(Math.round(meta.maxHeight + TIMELINE_ROW_PADDING), TIMELINE_ROW_GAP_MIN, TIMELINE_ROW_GAP_MAX);
    let y = TIMELINE_START.y;
    const x = cursorX;
    for (const item of sorted) {
      positions.set(item.id, { x, y });
      y += rowGap;
    }
    cursorX += bandWidth + gap;
  });
  return list.map((node) => {
    const next = positions.get(node.id);
    if (next) {
      return { ...node, position: { x: next.x, y: next.y } };
    }
    return node;
  });
};

export const updateStageBands = (nodes: Node[], levels?: Set<number>) => {
  if (!nodes.length) return nodes;
  const bounds = new Map<number, { minX: number; minY: number; maxX: number; maxY: number }>();

  for (const node of nodes) {
    if (node.type === "stage_band" || node.type === "stage") continue;
    if ((node as any).hidden) continue;
    if ((node.data as any)?.sequence_hidden) continue;
    const level = getStageLevel(node);
    if (level === null) continue;
    if (levels && !levels.has(level)) continue;
    const pos = node.position ?? { x: 0, y: 0 };
    const size = getNodeSize(node);
    const minX = pos.x;
    const minY = pos.y;
    const maxX = pos.x + size.width;
    const maxY = pos.y + size.height;
    const current = bounds.get(level);
    if (!current) {
      bounds.set(level, { minX, minY, maxX, maxY });
    } else {
      current.minX = Math.min(current.minX, minX);
      current.minY = Math.min(current.minY, minY);
      current.maxX = Math.max(current.maxX, maxX);
      current.maxY = Math.max(current.maxY, maxY);
    }
  }

  if (!bounds.size) return nodes;

  const bandPositions = new Map<number, { x: number; y: number; width: number; height: number }>();
  for (const [level, range] of bounds.entries()) {
    const width = Math.max(120, range.maxX - range.minX + STAGE_BAND_PADDING.x * 2);
    const height = Math.max(90, range.maxY - range.minY + STAGE_BAND_PADDING.y * 2);
    bandPositions.set(level, {
      x: range.minX - STAGE_BAND_PADDING.x,
      y: range.minY - STAGE_BAND_PADDING.y,
      width,
      height
    });
  }

  return nodes.map((node) => {
    const level = getStageLevel(node);
    if (level === null) return node;
    if (levels && !levels.has(level)) return node;
    const range = bandPositions.get(level);
    if (!range) return node;
    if (node.type === "stage_band") {
      return {
        ...node,
        position: { x: range.x, y: range.y },
        data: {
          ...(node.data ?? {}),
          width: range.width,
          height: range.height
        }
      };
    }
    return node;
  });
};

export const updateIngestBands = (nodes: Node[]) => {
  if (!nodes.length) return nodes;
  const nodeById = new Map<string, Node>();
  for (const node of nodes) {
    nodeById.set(node.id, node);
  }
  let changed = false;
  const nextNodes = nodes.map((node) => {
    if (node.type !== "ingest_band") return node;
    const members = getBandMembers(node);
    if (!members.length) return node;
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    let visibleCount = 0;
    for (const id of members) {
      const member = nodeById.get(id);
      if (!member) continue;
      if ((member as any).hidden) continue;
      if ((member.data as any)?.sequence_hidden) continue;
      const pos = member.position ?? { x: 0, y: 0 };
      const size = getNodeSize(member);
      minX = Math.min(minX, pos.x);
      minY = Math.min(minY, pos.y);
      maxX = Math.max(maxX, pos.x + size.width);
      maxY = Math.max(maxY, pos.y + size.height);
      visibleCount += 1;
    }
    if (!visibleCount) return node;
    const width = Math.max(240, maxX - minX + INGEST_BAND_PADDING.x * 2);
    const height = Math.max(120, maxY - minY + INGEST_BAND_PADDING.y * 2);
    changed = true;
    return {
      ...node,
      position: {
        x: minX - INGEST_BAND_PADDING.x,
        y: minY - INGEST_BAND_PADDING.y
      },
      data: {
        ...(node.data ?? {}),
        width,
        height
      }
    };
  });
  return changed ? nextNodes : nodes;
};

export const buildAdjacency = (edgesList: Edge[]) => {
  const map = new Map<string, Set<string>>();
  for (const edge of edgesList) {
    const source = String(edge.source ?? "");
    const target = String(edge.target ?? "");
    if (!source || !target) continue;
    const srcSet = map.get(source) ?? new Set<string>();
    const tgtSet = map.get(target) ?? new Set<string>();
    srcSet.add(target);
    tgtSet.add(source);
    map.set(source, srcSet);
    map.set(target, tgtSet);
  }
  return map;
};

export const buildStageFilterSet = (nodes: Node[], baseEdges: Edge[], level: number) => {
  const primaryIds = new Set<string>();
  for (const node of nodes) {
    if (node.type === "stage_band") {
      if (getStageLevel(node) === level) {
        primaryIds.add(node.id);
      }
      continue;
    }
    const nodeLevel = getStageLevel(node);
    if (nodeLevel === level) {
      primaryIds.add(node.id);
    }
  }
  if (!primaryIds.size) {
    return null;
  }
  const expanded = new Set<string>(primaryIds);
  for (const edge of baseEdges) {
    const source = String(edge.source ?? "");
    const target = String(edge.target ?? "");
    if (primaryIds.has(source) || primaryIds.has(target)) {
      expanded.add(source);
      expanded.add(target);
    }
  }
  return expanded;
};

export const buildSequenceVisibility = (nodes: Node[], baseEdges: Edge[], data: VizEvent[]) => {
  const visible = new Set<string>();
  const stageLevels = new Set<number>();
  if (!nodes.length) {
    return { visible, stageLevels };
  }
  const nodeById = new Map<string, Node>();
  for (const node of nodes) {
    nodeById.set(node.id, node);
  }

  const isWorkflowNodeId = (nodeId: string) => {
    return nodeId.startsWith("workflow_node:") || nodeId.startsWith("workflow_resource:");
  };

  // Workflow runs should keep their topology visible in timeline mode. Without this,
  // the timeline "sequence visibility" filter would hide all workflow nodes because
  // they don't match the source/loader/field prefixes.
  const workflowNodes = nodes.filter((node) => isWorkflowNodeId(String(node.id)));
  if (workflowNodes.length) {
    for (const node of workflowNodes) {
      visible.add(String(node.id));
    }
  }

  const mainSource = nodes.find((node) => node.type === "source" && (node.data as any)?.is_main);
  if (mainSource) {
    visible.add(mainSource.id);
    if (mainSource.id.startsWith("source:")) {
      const loaderId = `loader:${mainSource.id.slice("source:".length)}`;
      if (nodes.some((node) => node.id === loaderId)) {
        visible.add(loaderId);
      }
    }
  }
  const addFieldsForSource = (sourceId: string) => {
    for (const node of nodes) {
      if (node.type !== "field") continue;
      const nodeSource = (node.data as any)?.source_id;
      if (nodeSource && String(nodeSource) === sourceId) {
        visible.add(node.id);
      }
    }
  };
  for (const evt of data) {
    const nodeId = evt.node_ref?.id ?? "";
    if (!nodeId) continue;
    if (nodeId.startsWith("output_target:")) {
      visible.add(nodeId);
      continue;
    }
    if (nodeId.startsWith("loader:")) {
      visible.add(nodeId);
      const sourceKey = nodeId.slice("loader:".length);
      const sourceId = `source:${sourceKey}`;
      visible.add(sourceId);
      addFieldsForSource(sourceKey);
      continue;
    }
    if (nodeId.startsWith("source:")) {
      visible.add(nodeId);
      continue;
    }
    if (nodeId.startsWith("field:")) {
      visible.add(nodeId);
      continue;
    }

    if (nodeById.has(nodeId)) {
      visible.add(nodeId);
    }
  }
  const depsByTarget = new Map<string, Set<string>>();
  for (const edge of baseEdges) {
    if (edge.type !== "depends_on") continue;
    const source = String(edge.source ?? "");
    const target = String(edge.target ?? "");
    if (!source || !target) continue;
    const targetNode = nodeById.get(target);
    if (!targetNode || targetNode.type !== "derived") continue;
    const deps = depsByTarget.get(target) ?? new Set<string>();
    deps.add(source);
    depsByTarget.set(target, deps);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const [target, deps] of depsByTarget.entries()) {
      if (visible.has(target)) continue;
      let ready = true;
      for (const dep of deps) {
        if (!visible.has(dep)) {
          ready = false;
          break;
        }
      }
      if (ready) {
        visible.add(target);
        changed = true;
      }
    }
  }
  for (const node of nodes) {
    if (!visible.has(node.id)) continue;
    const level = getStageLevel(node);
    if (level !== null) {
      stageLevels.add(level);
    }
  }
  return { visible, stageLevels };
};

export const updateNodesFromEvents = (baseNodes: Node[], data: VizEvent[]) => {
  if (!baseNodes.length || !data.length) {
    return baseNodes.map((node) => {
      const nextData = { ...(node.data ?? {}) } as Record<string, any>;
      delete nextData.last_event_type;
      delete nextData.last_event_at;
      delete nextData.status;
      return { ...node, data: nextData };
    });
  }
  const latestById = new Map<string, VizEvent>();
  for (const evt of data) {
    if (evt.node_ref?.id) {
      latestById.set(evt.node_ref.id, evt);
    }
  }

  return baseNodes.map((node) => {
    const nextData = { ...(node.data ?? {}) } as Record<string, any>;
    const evt = latestById.get(node.id);
    if (!evt) {
      delete nextData.last_event_type;
      delete nextData.last_event_at;
      delete nextData.status;
      return { ...node, data: nextData };
    }
    nextData.last_event_type = evt.event_type;
    nextData.last_event_at = evt.timestamp;
    let status = statusFromEvent(evt.event_type);
    if (evt.event_type === "output_target_finished") {
      const payload = evt.payload ?? {};
      const errorCount = Number((payload as any)?.error_count ?? 0);
      const disabled = Boolean((payload as any)?.disabled);
      if ((Number.isFinite(errorCount) && errorCount > 0) || disabled) {
        status = "error";
      } else {
        status = "success";
      }
    }
    nextData.status = status;
    return { ...node, data: nextData };
  });
};

export const decorateEdges = (
  edgesList: Edge[],
  focusSet: Set<string> | null,
  activeNodeId: string,
  stageFilterSet: Set<string> | null,
  sequenceSet: Set<string> | null
  ) => {
  const styleForType = (edge: Edge) => {
    const type = String((edge as any)?.data?.type ?? (edge as any)?.type ?? "");
    if (type === "ref_lookup") return EDGE_STYLE_REF_LOOKUP;
    if (type === "loads_from") return EDGE_STYLE_LOADS_FROM;
    if (type === "plan_overlay") return EDGE_STYLE_PLAN_OVERLAY;
    return EDGE_STYLE_BASE;
  };
  return edgesList.map((edge) => {
    const source = String(edge.source ?? "");
    const target = String(edge.target ?? "");
    const inFocus = focusSet ? focusSet.has(source) && focusSet.has(target) : true;
    const isActive = activeNodeId && (source === activeNodeId || target === activeNodeId);
    const edgeType = String((edge as any)?.data?.type ?? (edge as any)?.type ?? "");
    const isOverlay = edgeType === "plan_overlay";
    const hidden = isOverlay ? false : stageFilterSet ? !(stageFilterSet.has(source) && stageFilterSet.has(target)) : false;
    const sequenceHidden = isOverlay ? false : sequenceSet ? !(sequenceSet.has(source) && sequenceSet.has(target)) : false;
    let style = styleForType(edge);
    if (hidden || sequenceHidden) {
      style = EDGE_STYLE_HIDDEN;
    } else if (focusSet && !inFocus) {
      style = EDGE_STYLE_DIM;
    } else if (isActive) {
      style = EDGE_STYLE_ACTIVE;
    } else if (focusSet && inFocus) {
      style = EDGE_STYLE_FOCUS;
    }
    return { ...edge, style, hidden: hidden || sequenceHidden };
  });
};

export const decorateNodes = (
  baseNodes: Node[],
  data: VizEvent[],
  stageLevel: number | null,
  focusInfo: {
    focusSet: Set<string> | null;
    focusNodeId: string;
    activeNodeId: string;
    activeStageLevel: number | null;
    stageFilterSet: Set<string> | null;
    stageFilterLevel: number | null;
    sequenceSet: Set<string> | null;
    sequenceStageLevels: Set<number> | null;
    planHighlightSet: Set<string> | null;
  }
) => {
  const next = updateNodesFromEvents(baseNodes, data);
  const focusSet = focusInfo?.focusSet ?? null;
  const focusNode = focusInfo?.focusNodeId ?? "";
  const activeNodeId = focusInfo?.activeNodeId ?? "";
  const planHighlightSet = focusInfo?.planHighlightSet ?? null;
  const focusStageLevels = new Set<number>();
  const activeStageLevel = focusInfo?.activeStageLevel ?? null;
  const stageFilterSet = focusInfo?.stageFilterSet ?? null;
  const sequenceSet = focusInfo?.sequenceSet ?? null;
  const sequenceStageLevels = focusInfo?.sequenceStageLevels ?? null;

  if (focusSet) {
    for (const node of next) {
      if (!focusSet.has(node.id)) continue;
      const level = getStageLevel(node);
      if (level !== null) {
        focusStageLevels.add(level);
      }
    }
  }

  return next.map((node) => {
    const isStageNode = node.type === "stage" || node.type === "stage_band";
    const isPlanNode = node.type === "plan";
    const isIngestBand = node.type === "ingest_band";
    const members = isIngestBand ? getBandMembers(node) : [];
    let inFocus = true;
    if (focusSet) {
      if (isStageNode) {
        const level = getStageLevel(node);
        inFocus = level !== null && focusStageLevels.has(level);
      } else if (isIngestBand) {
        inFocus = members.some((id) => focusSet.has(id));
      } else {
        inFocus = focusSet.has(node.id);
      }
    }
    const dimmed = focusSet ? !inFocus : false;
    const highlighted = focusSet ? inFocus : false;
    const isFocusNode = focusSet ? node.id === focusNode : false;
    const isActive = activeNodeId && node.id === activeNodeId;
    let focus = false;

    if (isStageNode) {
      const level = getStageLevel(node);
      focus =
        (stageLevel !== null && stageLevel !== undefined && level === stageLevel) ||
        (activeStageLevel !== null && level === activeStageLevel) ||
        (focusStageLevels.size > 0 && level !== null && focusStageLevels.has(level));
    } else if (isIngestBand) {
      focus = members.some((id) => id === activeNodeId);
    }

    let sequenceHidden = false;
    if (sequenceSet) {
      if (isPlanNode) {
        sequenceHidden = false;
      } else if (node.type === "stage_band") {
        const level = getStageLevel(node);
        sequenceHidden = !(level !== null && sequenceStageLevels && sequenceStageLevels.has(level));
      } else if (isIngestBand) {
        sequenceHidden = !members.some((id) => sequenceSet.has(id));
      } else {
        sequenceHidden = !sequenceSet.has(node.id);
      }
    }

    let stageHidden = false;
    if (stageFilterSet) {
      if (isPlanNode) {
        stageHidden = false;
      } else if (isIngestBand) {
        stageHidden = !members.some((id) => stageFilterSet.has(id));
      } else {
        stageHidden = !stageFilterSet.has(node.id);
      }
    }

    let planHighlighted = false;
    let planDimmed = false;
    if (planHighlightSet && planHighlightSet.size) {
      if (isIngestBand) {
        planHighlighted = members.some((id) => planHighlightSet.has(id));
      } else if (!isStageNode && !isPlanNode) {
        planHighlighted = planHighlightSet.has(node.id);
      }
      if (!isStageNode && !isPlanNode) {
        planDimmed = !planHighlighted;
      }
    }

    return {
      ...node,
      hidden: stageHidden || (sequenceSet ? sequenceHidden : false),
      data: {
        ...(node.data ?? {}),
        focus,
        highlighted: highlighted || planHighlighted,
        dimmed: dimmed || planDimmed,
        is_focus: isFocusNode,
        active: isActive,
        sequence_hidden: sequenceHidden
      }
    };
  });
};
