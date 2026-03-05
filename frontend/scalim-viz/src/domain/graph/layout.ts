import type { Node, Edge } from '@xyflow/svelte';
import type { VizGraphSnapshot } from '$domain/types';

export type LayoutResult = {
  nodes: Node[];
  edges: Edge[];
};

const STAGE_X_GAP = 360;
const NODE_Y_GAP = 120;
const FIELD_GAP_MIN = 88;
const FIELD_GAP_MAX = 140;
const STAGE_BAND_PADDING = 60;
const STAGE_BAND_WIDTH = 320;
const STAGE_COLUMN_OFFSET = 80;
const FIELD_X_OFFSET = 40;
const LOADER_X = -STAGE_X_GAP;
const SOURCE_X = LOADER_X - 170;
const INGEST_BAND_PADDING = { x: 36, y: 26 };
const INGEST_BAND_MIN = { width: 240, height: 120 };
const LOADER_SIZE = { width: 170, height: 68 };
const SOURCE_SIZE = { width: 170, height: 68 };
const LOADER_CLUSTER_GAP = 150;
const LOADER_CLUSTER_GAP_MAX = 240;

const TYPE_ORDER: { [key: string]: number } = {
  stage: 0,
  field: 1,
  derived: 2,
  loader: 3,
  source: 4,
  default: 9
};

const normalizeVerticalPositions = (
  entries: Array<{ id: string; y: number }>,
  minGap: number,
  maxGap: number
) => {
  if (entries.length <= 1) return entries;
  const sorted = entries.slice().sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i += 1) {
    const minY = sorted[i - 1].y + minGap;
    if (sorted[i].y < minY) {
      sorted[i].y = minY;
    }
  }
  for (let i = sorted.length - 2; i >= 0; i -= 1) {
    const maxY = sorted[i + 1].y - maxGap;
    if (sorted[i].y < maxY) {
      sorted[i].y = maxY;
    }
  }
  for (let i = 1; i < sorted.length; i += 1) {
    const minY = sorted[i - 1].y + minGap;
    if (sorted[i].y < minY) {
      sorted[i].y = minY;
    }
  }
  return sorted;
};

export function layoutSnapshot(snapshot: VizGraphSnapshot): LayoutResult {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const rawNodes = snapshot.nodes ?? [];
  const nodeMap = new Map<string, typeof rawNodes[number]>();
  const stageByField = new Map<string, { stage_id: string; level: number }>();
  const stageLabelByLevel = new Map<number, string>();
  const levelsSet = new Set<number>();

  for (const node of rawNodes) {
    const nodeId = String(node.id ?? '');
    nodeMap.set(nodeId, node);
    const nodeType = String(node.type ?? 'default');
    if (nodeType === 'stage') {
      const levelValue = node.data?.level;
      if (levelValue !== undefined && levelValue !== null) {
        const level = Number(levelValue);
        if (!Number.isNaN(level)) {
          levelsSet.add(level);
          const label = String(node.data?.label ?? node.data?.stage_id ?? nodeId);
          if (!stageLabelByLevel.has(level)) {
            stageLabelByLevel.set(level, label);
          }
        }
      }
    }
  }

  const stages = snapshot.stages ?? [];
  for (const stage of stages) {
    levelsSet.add(stage.level);
    if (!stageLabelByLevel.has(stage.level)) {
      stageLabelByLevel.set(stage.level, stage.stage_id);
    }
    for (const key of stage.field_keys) {
      stageByField.set(key, { stage_id: stage.stage_id, level: stage.level });
    }
  }

  const levels = Array.from(levelsSet.values()).sort((a, b) => a - b);
  if (!levels.length) {
    levels.push(0);
  }

  const levelNodes = new Map<number, string[]>();
  const loaderIds: string[] = [];
  const sourceIds: string[] = [];

  for (const node of rawNodes) {
    const nodeId = String(node.id ?? '');
    const nodeType = String(node.type ?? 'default');
    if (nodeType === 'loader') {
      loaderIds.push(nodeId);
      continue;
    }
    if (nodeType === 'source') {
      sourceIds.push(nodeId);
      continue;
    }
    if (nodeType === 'field' || nodeType === 'derived') {
      const fieldKey = nodeId.startsWith('field:') ? nodeId.replace('field:', '') : node.data?.field_key;
      const stage = fieldKey ? stageByField.get(String(fieldKey)) : null;
      const level = stage ? stage.level : levels[0];
      const list = levelNodes.get(level) ?? [];
      list.push(nodeId);
      levelNodes.set(level, list);
    }
  }

  const edgeList = snapshot.edges ?? [];
  const sortKey = (nodeId: string) => {
    const node = nodeMap.get(nodeId);
    const type = String(node?.type ?? 'default');
    const label = String(node?.data?.label ?? node?.data?.field_key ?? nodeId);
    const order = TYPE_ORDER[type] ?? TYPE_ORDER.default;
    return `${order}-${label}`;
  };

  const orderLevelNodes = (ids: string[]) => {
    const set = new Set(ids);
    const indegree = new Map<string, number>();
    const outgoing = new Map<string, string[]>();
    for (const id of ids) {
      indegree.set(id, 0);
      outgoing.set(id, []);
    }
    for (const edge of edgeList) {
      const source = String(edge.source ?? '');
      const target = String(edge.target ?? '');
      if (!set.has(source) || !set.has(target)) continue;
      outgoing.get(source)?.push(target);
      indegree.set(target, (indegree.get(target) ?? 0) + 1);
    }
    const queue = ids.filter((id) => (indegree.get(id) ?? 0) === 0).sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    const result: string[] = [];
    while (queue.length) {
      const next = queue.shift()!;
      result.push(next);
      for (const target of outgoing.get(next) ?? []) {
        const value = (indegree.get(target) ?? 0) - 1;
        indegree.set(target, value);
        if (value === 0) {
          queue.push(target);
          queue.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
        }
      }
    }
    if (result.length !== ids.length) {
      const remaining = ids.filter((id) => result.indexOf(id) === -1).sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
      result.push(...remaining);
    }
    return result;
  };

  const levelIndexByLevel = new Map<number, number>();
  levels.forEach((level, index) => levelIndexByLevel.set(level, index));

  const initialOrderByIndex = new Map<number, string[]>();
  const layerIndexByNodeId = new Map<string, number>();
  for (const level of levels) {
    const index = levelIndexByLevel.get(level) ?? 0;
    const ordered = orderLevelNodes(levelNodes.get(level) ?? []);
    initialOrderByIndex.set(index, ordered);
    for (const nodeId of ordered) {
      layerIndexByNodeId.set(nodeId, index);
    }
  }

  const prevNeighbors = new Map<string, string[]>();
  const nextNeighbors = new Map<string, string[]>();
  const pushNeighbor = (map: Map<string, string[]>, key: string, neighbor: string) => {
    if (!key || !neighbor) return;
    const list = map.get(key);
    if (list) {
      list.push(neighbor);
    } else {
      map.set(key, [neighbor]);
    }
  };

  for (const edge of edgeList) {
    const source = String(edge.source ?? '');
    const target = String(edge.target ?? '');
    const sourceLayer = layerIndexByNodeId.get(source);
    const targetLayer = layerIndexByNodeId.get(target);
    if (sourceLayer === undefined || targetLayer === undefined) continue;
    if (sourceLayer + 1 === targetLayer) {
      pushNeighbor(prevNeighbors, target, source);
      pushNeighbor(nextNeighbors, source, target);
    } else if (targetLayer + 1 === sourceLayer) {
      pushNeighbor(prevNeighbors, source, target);
      pushNeighbor(nextNeighbors, target, source);
    }
  }

  const refineLayerOrder = (orderByIndex: Map<number, string[]>, sweepCount: number) => {
    const layerCount = levels.length;
    if (layerCount <= 1) return;
    const rankForLayer = (layerIndex: number) => {
      const list = orderByIndex.get(layerIndex) ?? [];
      const rank = new Map<string, number>();
      list.forEach((id, idx) => rank.set(id, idx));
      return rank;
    };
    const averageRank = (neighborIds: string[], neighborRank: Map<string, number>) => {
      if (!neighborIds.length) return null;
      let total = 0;
      let count = 0;
      for (const neighbor of neighborIds) {
        const r = neighborRank.get(neighbor);
        if (r === undefined) continue;
        total += r;
        count += 1;
      }
      if (!count) return null;
      return total / count;
    };
    const reorder = (layerIndex: number, neighborLayerIndex: number, neighborMap: Map<string, string[]>) => {
      const list = orderByIndex.get(layerIndex) ?? [];
      if (list.length <= 1) return;
      const neighborRank = rankForLayer(neighborLayerIndex);
      const currentIndex = new Map<string, number>();
      list.forEach((id, idx) => currentIndex.set(id, idx));
      const scored = list.map((id) => {
        const neighbors = neighborMap.get(id) ?? [];
        const avg = averageRank(neighbors, neighborRank);
        const fallback = currentIndex.get(id) ?? 0;
        const key = avg === null ? fallback : avg;
        return { id, key, sort: sortKey(id), fallback };
      });
      scored.sort((a, b) => {
        if (a.key !== b.key) return a.key - b.key;
        if (a.fallback !== b.fallback) return a.fallback - b.fallback;
        return a.sort.localeCompare(b.sort);
      });
      orderByIndex.set(layerIndex, scored.map((item) => item.id));
    };

    const passes = Math.max(0, sweepCount);
    for (let pass = 0; pass < passes; pass += 1) {
      for (let idx = 1; idx < layerCount; idx += 1) {
        reorder(idx, idx - 1, prevNeighbors);
      }
      for (let idx = layerCount - 2; idx >= 0; idx -= 1) {
        reorder(idx, idx + 1, nextNeighbors);
      }
    }
  };

  const orderedByIndex = new Map<number, string[]>();
  for (const [index, ordered] of initialOrderByIndex.entries()) {
    orderedByIndex.set(index, ordered.slice());
  }
  refineLayerOrder(orderedByIndex, 2);

  const positions = new Map<string, { x: number; y: number }>();
  const stageBaseY = 80;

  for (const level of levels) {
    const levelIndex = levelIndexByLevel.get(level) ?? 0;
    const ids = orderedByIndex.get(levelIndex) ?? [];
    const baseX = level * STAGE_X_GAP + STAGE_COLUMN_OFFSET;
    ids.forEach((id, index) => {
      positions.set(id, { x: baseX + FIELD_X_OFFSET, y: stageBaseY + index * NODE_Y_GAP });
    });
    const normalized = normalizeVerticalPositions(
      ids.map((id) => ({ id, y: positions.get(id)?.y ?? stageBaseY })),
      FIELD_GAP_MIN,
      FIELD_GAP_MAX
    );
    for (const entry of normalized) {
      positions.set(entry.id, { x: baseX + FIELD_X_OFFSET, y: entry.y });
    }
  }

  loaderIds.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
  sourceIds.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));

  const loaderIndexById = new Map<string, number>();
  loaderIds.forEach((id, idx) => loaderIndexById.set(id, idx));

  const loaderTargets = new Map<string, number[]>();
  const sourceToLoader = new Map<string, string>();
  const loaderToSource = new Map<string, string>();
  for (const edge of edgeList) {
    const source = String(edge.source ?? '');
    const target = String(edge.target ?? '');
    if (source.startsWith('loader:') && positions.has(target)) {
      const list = loaderTargets.get(source) ?? [];
      list.push(positions.get(target)!.y);
      loaderTargets.set(source, list);
    }
    if (source.startsWith('source:') && target.startsWith('loader:')) {
      sourceToLoader.set(source, target);
      loaderToSource.set(target, source);
    }
  }

  for (const loaderId of loaderIds) {
    const targets = loaderTargets.get(loaderId) ?? [];
    let y = stageBaseY + (loaderIndexById.get(loaderId) ?? 0) * NODE_Y_GAP;
    if (targets.length) {
      const total = targets.reduce((acc, value) => acc + value, 0);
      y = total / targets.length;
    }
    positions.set(loaderId, { x: LOADER_X, y });
  }

  for (const sourceId of sourceIds) {
    const loaderId = sourceToLoader.get(sourceId);
    const loaderPos = loaderId ? positions.get(loaderId) : undefined;
    const fallbackIndex = sourceIds.indexOf(sourceId);
    const y = loaderPos ? loaderPos.y : stageBaseY + fallbackIndex * NODE_Y_GAP;
    positions.set(sourceId, { x: SOURCE_X, y });
  }

  const loaderEntries = normalizeVerticalPositions(
    loaderIds.map((id) => ({ id, y: positions.get(id)?.y ?? stageBaseY })),
    LOADER_CLUSTER_GAP,
    LOADER_CLUSTER_GAP_MAX
  );
  for (const entry of loaderEntries) {
    positions.set(entry.id, { x: LOADER_X, y: entry.y });
    const sourceId = loaderToSource.get(entry.id);
    if (sourceId) {
      positions.set(sourceId, { x: SOURCE_X, y: entry.y });
    }
  }

  const miscX = (levels[levels.length - 1] ?? 0) * STAGE_X_GAP + STAGE_COLUMN_OFFSET + STAGE_X_GAP;
  let miscIndex = 0;
  for (const node of rawNodes) {
    const nodeId = String(node.id ?? '');
    if (positions.has(nodeId)) continue;
    positions.set(nodeId, { x: miscX, y: stageBaseY + miscIndex * NODE_Y_GAP });
    miscIndex += 1;
  }

  const levelBounds = new Map<number, { minY: number; maxY: number }>();
  const updateBounds = (level: number, y: number) => {
    const existing = levelBounds.get(level);
    if (!existing) {
      levelBounds.set(level, { minY: y, maxY: y });
      return;
    }
    if (y < existing.minY) {
      existing.minY = y;
    }
    if (y > existing.maxY) {
      existing.maxY = y;
    }
  };

  for (const node of rawNodes) {
    const nodeId = String(node.id ?? '');
    const nodeType = String(node.type ?? 'default');
    const data = node.data ?? {};
    let stageLevel: number | null = null;
    if (nodeType === 'stage') {
      continue;
    }
    if (nodeType === 'field' || nodeType === 'derived') {
      const fieldKey = nodeId.startsWith('field:') ? nodeId.replace('field:', '') : data.field_key;
      const stage = fieldKey ? stageByField.get(String(fieldKey)) : null;
      stageLevel = stage ? stage.level : null;
    }
    const nodeData = stageLevel !== null ? { ...data, stage_level: stageLevel } : data;
    const position = positions.get(nodeId) ?? { x: 0, y: 0 };
    if (stageLevel !== null) {
      updateBounds(stageLevel, position.y);
    }
    nodes.push({
      id: nodeId,
      type: nodeType,
      data: nodeData,
      position,
      zIndex: 5,
      class: "z-10"
    });
  }

  const ingestBands: Node[] = [];
  const getLabelForNode = (nodeId: string) => {
    const node = nodeMap.get(nodeId);
    if (!node) return '';
    const data = node.data ?? {};
    return String(data.label ?? data.loader_name ?? data.source_id ?? '');
  };
  const trimPrefix = (value: string, prefix: string) => {
    return value.startsWith(prefix) ? value.slice(prefix.length) : value;
  };

  for (const loaderId of loaderIds) {
    const sourceId = loaderToSource.get(loaderId);
    if (!sourceId) continue;
    const loaderPos = positions.get(loaderId);
    const sourcePos = positions.get(sourceId);
    if (!loaderPos || !sourcePos) continue;
    const minX = Math.min(loaderPos.x, sourcePos.x);
    const minY = Math.min(loaderPos.y, sourcePos.y);
    const maxX = Math.max(loaderPos.x + LOADER_SIZE.width, sourcePos.x + SOURCE_SIZE.width);
    const maxY = Math.max(loaderPos.y + LOADER_SIZE.height, sourcePos.y + SOURCE_SIZE.height);
    const width = Math.max(INGEST_BAND_MIN.width, maxX - minX + INGEST_BAND_PADDING.x * 2);
    const height = Math.max(INGEST_BAND_MIN.height, maxY - minY + INGEST_BAND_PADDING.y * 2);
    const loaderLabel = getLabelForNode(loaderId);
    const sourceLabel = getLabelForNode(sourceId);
    const baseLabel =
      loaderLabel ||
      sourceLabel ||
      trimPrefix(loaderId, 'loader:') ||
      trimPrefix(sourceId, 'source:') ||
      'ingest';
    ingestBands.push({
      id: `ingest-band:${loaderId}`,
      type: 'ingest_band',
      class: "z-0",
      position: {
        x: minX - INGEST_BAND_PADDING.x,
        y: minY - INGEST_BAND_PADDING.y
      },
      zIndex: -2,
      selectable: false,
      draggable: false,
      connectable: false,
      data: {
        width,
        height,
        label: `ingest ${baseLabel}`,
        variant: 'ingest',
        members: [sourceId, loaderId]
      }
    });
  }

  const stageBands: Node[] = [];
  for (const [level, bounds] of levelBounds.entries()) {
    const height = Math.max(NODE_Y_GAP, bounds.maxY - bounds.minY + STAGE_BAND_PADDING);
    const bandY = bounds.minY - STAGE_BAND_PADDING / 2;
    const bandX = level * STAGE_X_GAP + STAGE_COLUMN_OFFSET - STAGE_BAND_PADDING / 2;
    stageBands.push({
      id: `stage-band:${level}`,
      type: 'stage_band',
      class: "z-0",
      position: { x: bandX, y: bandY },
      zIndex: -1,
      selectable: true,
      draggable: false,
      connectable: false,
      data: {
        level,
        width: STAGE_BAND_WIDTH,
        height,
        label: stageLabelByLevel.get(level) ?? `stage ${level}`,
        variant: 'stage'
      }
    });
  }

  nodes.unshift(...stageBands);
  if (ingestBands.length) {
    nodes.unshift(...ingestBands);
  }

  const validIds = new Set(nodes.map((node) => node.id));
  for (const edge of snapshot.edges ?? []) {
    const source = String(edge.source ?? '');
    const target = String(edge.target ?? '');
    const type = String(edge.type ?? 'default');
    if (type === 'in_stage') continue;
    if (!validIds.has(source) || !validIds.has(target)) continue;
    edges.push({
      id: String(edge.id ?? ''),
      source,
      target,
      type,
      style: "stroke:#94a3b8;stroke-width:1.2;",
      data: edge.data ?? {}
    });
  }

  return { nodes, edges };
}

export function summarizeSnapshot(snapshot: VizGraphSnapshot) {
  return {
    nodeCount: snapshot.nodes?.length ?? 0,
    edgeCount: snapshot.edges?.length ?? 0,
    stageCount: snapshot.stages?.length ?? 0
  };
}
