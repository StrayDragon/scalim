import { tick } from "svelte";
import type { Edge, Node } from "@xyflow/svelte";
import type { RunSource, VizEvent, VizGraphSnapshot, VizSchedulePlan } from "$domain/types";
import { formatTimestamp, parseJsonl } from "$domain/events/parse";
import { layoutSnapshot, summarizeSnapshot } from "$domain/graph/layout";
import { VIZ_REPLAY_ROUTE } from "../generated/project_constants";
import {
  applyTimelineLayout,
  buildAdjacency,
  buildSequenceVisibility,
  buildStageFilterSet,
  decorateEdges,
  decorateNodes,
  getNodeSize,
  getStageLevel,
  restoreBasePositions,
  statusFromEvent,
  updateIngestBands,
  updateStageBands
} from "$domain/graph/decorations";
import {
  buildRunsFromFiles,
  pickLatestRun,
  readFile,
  readFileTail
} from "$services/files";

type WorkflowNavReturn = {
  returnRunId: string;
  returnViewMode: "graph" | "timeline";
  returnPlaybackIndex: number;
  returnViewport: { x: number; y: number; zoom: number } | null;
  returnSelectedNodeId: string;
  returnSelectedStageLevel: number | null;
  returnSelectionSource: "none" | "user" | "playback";
  returnStageFilterEnabled: boolean;
  returnStageFilterMode: "auto" | "manual";
  returnManualStageLevel: number | null;
  returnFocusMode: "none" | "neighbors";
  returnFocusNodeId: string;
  sourceWorkflowNodeId: string;
  demandRunId: string;
};

export const state = $state({
  nodes: [] as Node[],
  edges: [] as Edge[],
  baseEdges: [] as Edge[],
  snapshot: null as VizGraphSnapshot | null,
  schedulePlan: null as VizSchedulePlan | null,
  events: [] as VizEvent[],
  eventsAll: [] as VizEvent[],
  baseEventsAll: [] as VizEvent[],
  traceEventsAll: [] as VizEvent[],
  eventRunIds: [] as string[],
  activeEventRunId: "",
  eventSourceMode: "events" as "events" | "events+trace",
  traceStatus: "idle" as "idle" | "loading" | "loaded" | "error" | "unavailable",
  hiddenEventTypes: [] as string[],
  traceCollapse: true,
  traceFilterDefaultsApplied: false,
  selectedNodeId: "",
  selectedStageLevel: null as number | null,
  selectionSource: "none" as "none" | "user" | "playback",
  status: "未加载",
  runSources: [] as RunSource[],
  activeRunId: "",
  runName: "",
  runEnv: "",
  directoryLabel: "",
  mode: "idle" as "idle" | "replay",
  viewMode: "graph" as "graph" | "timeline",
  edgeShowDependsOn: true,
  edgeShowRefLookup: true,
  edgeShowLoadsFrom: true,
  dataPanelOpen: false,
  inspectorOpen: true,
  lastUpdated: null as number | null,
  replayInput: null as HTMLInputElement | null,
  playbackIndex: 0,
  playbackPlaying: false,
  playbackIntervalMs: 800,
  playbackTimer: null as number | null,
  playbackEvent: null as VizEvent | null,
  playbackFocusRef: null as
    | { kind: "node"; id: string; nodeType: string }
    | { kind: "batch"; id: string; batchNum: number | null }
    | { kind: "pipeline"; id: string }
    | null,
  planLensOpen: false,
  planOverlayEnabled: false,
  planHighlightNodeIds: [] as string[],
  planSelectedLayerIndex: null as number | null,
  planSelectedTaskId: "",
  planLastSelection: null as
    | { layerIndex: number; taskId: string; highlightNodeIds: string[] }
    | null,
  focusMode: "none" as "none" | "neighbors",
  focusNodeId: "",
  adjacency: new Map<string, Set<string>>(),
  autoFollow: true,
  autoFitTimeline: true,
  autoPauseOnAlert: true,
  stageFilterEnabled: false,
  stageFilterMode: "auto" as "auto" | "manual",
  manualStageLevel: null as number | null,
  activeStageLevel: null as number | null,
  currentStageFilterLevel: null as number | null,
  playbackCompact: false,
  toolbarCollapsed: false,
  topBarBottom: 0,
  panelDockTop: 120,
  eventTypeOrder: [] as string[],
  eventTypeCounts: new Map<string, number>(),
  jumpEventTokens: [] as string[],
  jumpDropdownOpen: false,
  jumpDefaultsApplied: false,
  lastEventsRunId: "",
  valueDialogOpen: false,
  valueDialogTitle: "",
  valueDialogContent: "",
  valueDialogAnchorEl: null as HTMLElement | null,
  valueDialogRoot: null as HTMLDivElement | null,
  valueDialogPosition: null as { left: number; top: number; placement: "left" | "right"; maxHeight: number } | null,
  jumpDropdownAnchor: null as HTMLDivElement | null,
  jumpDropdownPlacement: "bottom" as "top" | "bottom",
  baseNodePositions: new Map<string, { x: number; y: number }>(),
  inspectorOffset: { x: 0, y: 0 },
  planLensOffset: { x: 0, y: 0 },
  playbackOffset: { x: 0, y: 0 },
  workflowNav: null as WorkflowNavReturn | null,
  planLensFollowTimeline: true,
  panelDrag: null as {
    panel: "inspector" | "planLens" | "playback";
    startX: number;
    startY: number;
    baseX: number;
    baseY: number;
  } | null,
  fitPending: false,
  fitToken: ""
});

const MIN_PLAYBACK_INTERVAL = 200;
const DEFAULT_PLAYBACK_INTERVAL = 800;
const MAX_EVENTS_IN_MEMORY = 20000;
const TRACE_TAIL_BYTES = 8 * 1024 * 1024;

const prefersReducedMotion = () => {
  try {
    if (typeof window === "undefined") return false;
    return Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  } catch (err) {
    return false;
  }
};

const motionDuration = (durationMs: number) => {
  if (durationMs <= 0) return 0;
  return prefersReducedMotion() ? 0 : durationMs;
};

const clamp = (value: number, min: number, max: number) => {
  return Math.min(Math.max(value, min), max);
};

const sanitizeInterval = (value: number, min: number, fallback: number) => {
  const normalized = Number(value);
  if (!Number.isFinite(normalized) || normalized < min) {
    return fallback;
  }
  return normalized;
};

type FlowApi = {
  setCenter?: (x: number, y: number, options?: any) => Promise<unknown>;
  fitView?: (options?: any) => Promise<unknown>;
  getViewport?: () => { x: number; y: number; zoom: number };
  setViewport?: (viewport: { x: number; y: number; zoom: number }, options?: any) => Promise<unknown>;
};

let flowApi: FlowApi | null = null;

export const registerFlowApi = (api: FlowApi | null) => {
  flowApi = api;
};

export const collapseAllPanels = () => {
  state.dataPanelOpen = false;
  state.inspectorOpen = false;
  state.planLensOpen = false;
  state.playbackCompact = true;
  state.toolbarCollapsed = true;
};

const getVisibleEvents = () => {
  if (state.viewMode === "timeline" && state.mode === "replay") {
    return state.events.slice(0, state.playbackIndex);
  }
  return state.events;
};

const visibleEventsValue = $derived(() => getVisibleEvents());
export const visibleEvents = () => visibleEventsValue();

const getActiveNodeId = () => {
  const nodeIds = new Set(state.nodes.map((node) => node.id));
  if (state.viewMode !== "timeline") {
    if (state.selectedNodeId && nodeIds.has(state.selectedNodeId)) {
      return state.selectedNodeId;
    }
    return "";
  }
  const candidate = (state.mode === "replay" && state.playbackEvent?.node_ref?.id) || "";
  if (candidate && nodeIds.has(candidate)) {
    return candidate;
  }
  const visible = getVisibleEvents();
  for (let i = visible.length - 1; i >= 0; i -= 1) {
    const id = visible[i]?.node_ref?.id;
    if (id && nodeIds.has(id)) {
      return id;
    }
  }
  return "";
};

const getFocusSet = (nodeId: string) => {
  if (!nodeId) return null;
  const set = new Set<string>([nodeId]);
  const neighbors = state.adjacency.get(nodeId);
  if (neighbors) {
    for (const neighbor of neighbors) {
      set.add(neighbor);
    }
  }
  return set;
};

const getEdgeType = (edge: Edge) => {
  const raw = (edge as any)?.data?.type ?? (edge as any)?.type ?? "";
  return String(raw);
};

const isEdgeTypeVisible = (edge: Edge) => {
  const type = getEdgeType(edge);
  if (!type) return true;
  if (type === "depends_on") return state.edgeShowDependsOn;
  if (type === "ref_lookup") return state.edgeShowRefLookup;
  if (type === "loads_from") return state.edgeShowLoadsFrom;
  return true;
};

const buildPlanOverlay = (baseNodes: Node[]) => {
  if (state.viewMode !== "graph") return { nodes: [] as Node[], edges: [] as Edge[] };
  if (!state.planOverlayEnabled) return { nodes: [] as Node[], edges: [] as Edge[] };
  const layerIndex = state.planSelectedLayerIndex;
  const taskId = state.planSelectedTaskId;
  if (layerIndex === null || layerIndex === undefined) return { nodes: [] as Node[], edges: [] as Edge[] };
  if (!taskId) return { nodes: [] as Node[], edges: [] as Edge[] };
  const fieldNodeIds = state.planHighlightNodeIds ?? [];
  if (!fieldNodeIds.length) return { nodes: [] as Node[], edges: [] as Edge[] };

  const nodeById = new Map<string, Node>();
  for (const node of baseNodes) {
    nodeById.set(String(node.id), node);
  }
  const fieldNodes = fieldNodeIds.map((id) => nodeById.get(id)).filter(Boolean) as Node[];
  if (!fieldNodes.length) return { nodes: [] as Node[], edges: [] as Edge[] };

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const node of fieldNodes) {
    const pos = node.position ?? { x: 0, y: 0 };
    const size = getNodeSize(node);
    minX = Math.min(minX, pos.x);
    minY = Math.min(minY, pos.y);
    maxX = Math.max(maxX, pos.x + size.width);
    maxY = Math.max(maxY, pos.y + size.height);
  }
  const centerY = (minY + maxY) / 2 - 28;
  const fanoutX = minX - 220;
  const joinX = maxX + 220;

  const selectedLayer = state.schedulePlan?.load_ref?.layers?.find((layer) => Number(layer?.layer_index) === Number(layerIndex));
  const barrier = Boolean(selectedLayer?.rows_binding_barrier);

  const fanoutId = `plan:L${layerIndex}:${taskId}:fanout`;
  const joinId = `plan:L${layerIndex}:${taskId}:join`;
  const overlayNodes: Node[] = [
    {
      id: fanoutId,
      type: "plan",
      position: { x: fanoutX, y: centerY },
      draggable: false,
      selectable: false,
      data: { label: `L${layerIndex} ${taskId}`, kind: "fanout" }
    },
    {
      id: joinId,
      type: "plan",
      position: { x: joinX, y: centerY },
      draggable: false,
      selectable: false,
      data: { label: barrier ? "join (rows barrier)" : "join", kind: "fanin" }
    }
  ];

  const overlayEdges: Edge[] = [];
  for (const nodeId of fieldNodeIds) {
    overlayEdges.push({
      id: `${fanoutId}=>${nodeId}`,
      source: fanoutId,
      target: nodeId,
      data: { type: "plan_overlay" }
    });
    overlayEdges.push({
      id: `${nodeId}=>${joinId}`,
      source: nodeId,
      target: joinId,
      data: { type: "plan_overlay" }
    });
  }
  return { nodes: overlayNodes, edges: overlayEdges };
};

export const applyDecorations = () => {
  const visibleBaseEdges = state.baseEdges.filter(isEdgeTypeVisible);
  state.adjacency = buildAdjacency(visibleBaseEdges);
  const rawNodes = state.nodes.filter((node) => node.type !== "plan");
  const focusSet = state.focusMode === "neighbors" && state.focusNodeId ? getFocusSet(state.focusNodeId) : null;
  const activeNodeId = getActiveNodeId();
  const activeNode = rawNodes.find((node) => node.id === activeNodeId) ?? null;
  state.activeStageLevel = activeNode ? getStageLevel(activeNode) : null;
  const visible = visibleEvents();
  const sequenceInfo = state.viewMode === "timeline" ? buildSequenceVisibility(rawNodes, state.baseEdges, visible) : null;
  const sequenceSet = sequenceInfo && sequenceInfo.visible.size ? sequenceInfo.visible : null;
  const sequenceStageLevels = sequenceInfo && sequenceInfo.visible.size ? sequenceInfo.stageLevels : null;
  const planHighlightSet = state.planHighlightNodeIds.length ? new Set(state.planHighlightNodeIds) : null;
  const stageFilterLevel =
    state.stageFilterEnabled
      ? state.stageFilterMode === "manual"
        ? state.manualStageLevel
        : state.selectedStageLevel ?? state.activeStageLevel
      : null;
  state.currentStageFilterLevel = stageFilterLevel ?? null;
  const stageFilterSet = stageFilterLevel !== null && stageFilterLevel !== undefined
    ? buildStageFilterSet(rawNodes, state.baseEdges, stageFilterLevel)
    : null;
  const baseNodesForDecorate =
    state.viewMode === "timeline" && sequenceSet
      ? applyTimelineLayout(rawNodes, sequenceSet, state.baseNodePositions)
      : restoreBasePositions(rawNodes, state.baseNodePositions);
  const overlay = buildPlanOverlay(baseNodesForDecorate);
  const nodesForDecorate = overlay.nodes.length ? [...baseNodesForDecorate, ...overlay.nodes] : baseNodesForDecorate;
  const edgesForDecorate = overlay.edges.length ? [...visibleBaseEdges, ...overlay.edges] : visibleBaseEdges;
  state.nodes = decorateNodes(nodesForDecorate, visible, state.selectedStageLevel, {
    focusSet,
    focusNodeId: state.focusNodeId,
    activeNodeId,
    activeStageLevel: state.activeStageLevel,
    stageFilterSet,
    stageFilterLevel: stageFilterLevel ?? null,
    sequenceSet,
    sequenceStageLevels,
    planHighlightSet
  });
  state.edges = decorateEdges(edgesForDecorate, focusSet, activeNodeId, stageFilterSet, sequenceSet);
  if (state.viewMode === "timeline" && sequenceStageLevels && sequenceStageLevels.size) {
    state.nodes = updateStageBands(state.nodes, sequenceStageLevels);
  } else if (state.stageFilterEnabled && stageFilterLevel !== null && stageFilterLevel !== undefined) {
    state.nodes = updateStageBands(state.nodes, new Set([stageFilterLevel]));
  }
  state.nodes = updateIngestBands(state.nodes);
  if (state.viewMode === "timeline") {
    scheduleTimelineFit();
  }
};

export const resetGraphState = () => {
  state.snapshot = null;
  state.schedulePlan = null;
  state.nodes = [];
  state.edges = [];
  state.baseEdges = [];
  state.runName = "";
  state.runEnv = "";
  state.planHighlightNodeIds = [];
  state.planSelectedLayerIndex = null;
  state.planSelectedTaskId = "";
  state.planOverlayEnabled = false;
  state.planLastSelection = null;
  state.events = [];
  state.eventsAll = [];
  state.baseEventsAll = [];
  state.traceEventsAll = [];
  state.eventRunIds = [];
  state.activeEventRunId = "";
  state.traceStatus = "idle";
  state.hiddenEventTypes = [];
  state.traceCollapse = true;
  state.traceFilterDefaultsApplied = false;
  state.adjacency = new Map<string, Set<string>>();
};

const followNode = async (nodeId: string) => {
  if (!state.autoFollow) return;
  if (!nodeId) return;
  const node = state.nodes.find((item) => item.id === nodeId);
  if (!node) return;
  if ((node as any).hidden) return;
  if ((node.data as any)?.sequence_hidden) return;
  const size = getNodeSize(node);
  const x = (node.position?.x ?? 0) + size.width / 2;
  const y = (node.position?.y ?? 0) + size.height / 2;
  try {
    if (flowApi?.setCenter) {
      await flowApi.setCenter(x, y, { duration: motionDuration(220) });
    }
  } catch (err) {
    // ignore viewport errors
  }
};

const normalizeNodeRefId = (nodeId: string, knownIds: Set<string>) => {
  const raw = String(nodeId ?? "").trim();
  if (!raw) return "";
  if (knownIds.has(raw)) return raw;

  const spaceIndex = raw.indexOf(" ");
  if (spaceIndex > 0) {
    const trimmed = raw.slice(0, spaceIndex).trim();
    if (trimmed && knownIds.has(trimmed)) return trimmed;
  }

  if (raw.startsWith("field:")) {
    const prefix = `${raw}_`;
    const candidates: string[] = [];
    for (const id of knownIds) {
      if (id.startsWith(prefix)) {
        candidates.push(id);
      }
    }
    if (candidates.length) {
      const value = candidates.find((id) => id.endsWith("_value"));
      if (value) return value;
      candidates.sort();
      return candidates[0];
    }
  }

  return raw;
};

const normalizeVizEvents = (events: VizEvent[]) => {
  if (!events.length) return events;
  const knownIds = new Set(state.nodes.map((node) => String(node.id)));
  if (!knownIds.size) return events;
  for (const evt of events) {
    const rawId = evt?.node_ref?.id ?? "";
    if (!rawId) continue;
    const normalized = normalizeNodeRefId(rawId, knownIds);
    if (normalized && normalized !== rawId) {
      evt.node_ref.id = normalized;
    }
  }
  return events;
};

const parseBatchNumFromNodeRefId = (nodeRefId: string) => {
  const raw = String(nodeRefId ?? "").trim();
  if (!raw) return null;
  if (!raw.startsWith("batch:")) return null;
  const rest = raw.slice("batch:".length).trim();
  if (!rest) return null;
  const first = rest.split(" ", 1)[0];
  const num = Number(first);
  if (!Number.isFinite(num)) return null;
  return num;
};

export const resolveEventBatchNum = (evt: VizEvent | null) => {
  if (!evt) return null;
  const payloadNum = (evt.payload as any)?.batch_num;
  if (payloadNum !== undefined && payloadNum !== null && payloadNum !== "") {
    const num = Number(payloadNum);
    if (Number.isFinite(num)) return num;
  }
  const ref = evt.node_ref?.id ?? "";
  return parseBatchNumFromNodeRefId(ref);
};

const buildPlaybackFocusRef = (evt: VizEvent) => {
  const refType = evt.node_ref?.type ?? "";
  const refId = evt.node_ref?.id ?? "";
  if (refType === "batch") {
    return { kind: "batch" as const, id: refId, batchNum: resolveEventBatchNum(evt) };
  }
  if (refType === "pipeline") {
    return { kind: "pipeline" as const, id: refId };
  }
  return { kind: "node" as const, id: refId, nodeType: refType };
};

const focusPlaybackEvent = (evt: VizEvent | null) => {
  if (state.viewMode !== "timeline") {
    applyDecorations();
    return;
  }
  if (!evt) {
    state.playbackFocusRef = null;
    state.selectedNodeId = "";
    state.selectedStageLevel = null;
    state.selectionSource = "none";
    applyDecorations();
    return;
  }
  state.playbackFocusRef = buildPlaybackFocusRef(evt);
  const candidate = evt.node_ref?.id ?? "";
  const node = candidate ? state.nodes.find((item) => item.id === candidate) ?? null : null;
  if (node) {
    state.selectedNodeId = candidate;
    state.selectedStageLevel = getStageLevel(node);
    state.selectionSource = "playback";
  } else if (state.selectionSource === "playback") {
    state.selectedNodeId = "";
    state.selectedStageLevel = null;
    state.selectionSource = "none";
  }
  applyDecorations();
  if (node) {
    void followNode(candidate);
  }
};

export const relayoutNodes = () => {
  if (!state.snapshot) return;
  applySnapshot(state.snapshot);
};

export const resetView = () => {
  try {
    if (flowApi?.fitView) {
      void flowApi.fitView({ padding: 0.2, duration: motionDuration(260) });
    }
  } catch (err) {
    // ignore viewport errors
  }
};

export const setPlaybackIndex = (nextIndex: number, focus = true, force = false) => {
  if (!force && state.viewMode !== "timeline") {
    return;
  }
  const clamped = clamp(nextIndex, 0, state.events.length);
  state.playbackIndex = clamped;
  state.playbackEvent = clamped > 0 ? state.events[clamped - 1] : null;
  if (focus && state.viewMode === "timeline") {
    focusPlaybackEvent(state.playbackEvent);
  } else {
    applyDecorations();
  }
};

export const stepPlayback = (direction: number) => {
  if (state.viewMode !== "timeline") {
    return;
  }
  setPlaybackIndex(state.playbackIndex + direction);
};

export const stopPlayback = () => {
  state.playbackPlaying = false;
  if (state.playbackTimer !== null) {
    window.clearInterval(state.playbackTimer);
    state.playbackTimer = null;
  }
};

export const resetPlayback = (data: VizEvent[]) => {
  stopPlayback();
  state.playbackIndex = data.length;
  state.playbackEvent = data.length ? data[data.length - 1] : null;
  applyDecorations();
};

let activePlaybackIntervalMs = sanitizeInterval(state.playbackIntervalMs, MIN_PLAYBACK_INTERVAL, DEFAULT_PLAYBACK_INTERVAL);

const restartPlaybackTimer = () => {
  if (state.viewMode !== "timeline") {
    stopPlayback();
    return;
  }
  if (!state.playbackPlaying) return;
  const nextInterval = sanitizeInterval(state.playbackIntervalMs, MIN_PLAYBACK_INTERVAL, DEFAULT_PLAYBACK_INTERVAL);
  if (nextInterval === activePlaybackIntervalMs && state.playbackTimer !== null) return;
  activePlaybackIntervalMs = nextInterval;
  if (state.playbackTimer !== null) {
    window.clearInterval(state.playbackTimer);
  }
  state.playbackTimer = window.setInterval(() => {
    if (state.playbackIndex >= state.events.length) {
      stopPlayback();
      return;
    }
    const nextIndex = state.playbackIndex + 1;
    const nextEvent = state.events[nextIndex - 1] ?? null;
    setPlaybackIndex(nextIndex, true, false);
    if (nextEvent && state.autoPauseOnAlert && isAlertEvent(nextEvent.event_type)) {
      stopPlayback();
    }
  }, activePlaybackIntervalMs);
};

export const ensurePlaybackTimer = () => {
  if (state.playbackPlaying) {
    restartPlaybackTimer();
  }
};

export const startPlayback = () => {
  if (state.viewMode !== "timeline") {
    return;
  }
  if (state.playbackPlaying) return;
  state.playbackPlaying = true;
  restartPlaybackTimer();
};

export const togglePlayback = () => {
  if (state.viewMode !== "timeline") {
    return;
  }
  if (state.playbackPlaying) {
    stopPlayback();
  } else {
    startPlayback();
  }
};

const jumpToEvent = (direction: 1 | -1, predicate: (evt: VizEvent) => boolean) => {
  if (state.viewMode !== "timeline") return;
  if (!state.events.length) return;
  let index = direction > 0 ? state.playbackIndex : state.playbackIndex - 2;
  while (index >= 0 && index < state.events.length) {
    const evt = state.events[index];
    if (evt && predicate(evt)) {
      setPlaybackIndex(index + 1);
      return;
    }
    index += direction;
  }
};

export const jumpToEventIndex = (eventIndex: number) => {
  const idx = Number(eventIndex);
  if (!Number.isFinite(idx)) return;
  if (!state.events.length) return;
  const clamped = clamp(Math.floor(idx), 0, state.events.length - 1);
  stopPlayback();
  state.viewMode = "timeline";
  setPlaybackIndex(clamped + 1, true, true);
};

export const jumpToCustom = (direction: 1 | -1, tokens: string[]) => {
  if (state.viewMode !== "timeline") return;
  if (!tokens.length) return;
  jumpToEvent(direction, (evt) => tokens.some((token) => matchJumpToken(evt.event_type, token)));
};

export const jumpToBatchBoundary = (direction: 1 | -1) => {
  if (state.viewMode !== "timeline") return;
  jumpToEvent(direction, (evt) => evt.event_type === "batch_started");
};

export const jumpToNodeBoundary = (direction: 1 | -1) => {
  if (state.viewMode !== "timeline") return;
  if (!state.events.length) return;
  const currentNode = state.playbackEvent?.node_ref?.id ?? "";
  if (direction > 0) {
    let index = Math.max(state.playbackIndex, 0);
    while (index < state.events.length && state.events[index]?.node_ref?.id === currentNode) {
      index += 1;
    }
    if (index < state.events.length) {
      setPlaybackIndex(index + 1);
    }
    return;
  }
  let index = Math.min(state.playbackIndex - 2, state.events.length - 1);
  while (index >= 0 && state.events[index]?.node_ref?.id === currentNode) {
    index -= 1;
  }
  if (index < 0) return;
  const targetNode = state.events[index]?.node_ref?.id;
  while (index - 1 >= 0 && state.events[index - 1]?.node_ref?.id === targetNode) {
    index -= 1;
  }
  setPlaybackIndex(index + 1);
};

const isAlertEvent = (eventType: string) => {
  const value = String(eventType || "").toLowerCase();
  return value.includes("error") || value.includes("failed") || value.includes("warn");
};

export const openJumpDropdown = () => {
  if (state.jumpDropdownAnchor) {
    const rect = state.jumpDropdownAnchor.getBoundingClientRect();
    const menuHeight = 240;
    const bottomSpace = window.innerHeight - rect.bottom;
    const topSpace = rect.top;
    if (bottomSpace < menuHeight && topSpace > bottomSpace) {
      state.jumpDropdownPlacement = "top";
    } else {
      state.jumpDropdownPlacement = "bottom";
    }
  }
  state.jumpDropdownOpen = true;
};

export const toggleJumpEvent = (eventType: string) => {
  if (!eventType) return;
  if (state.jumpEventTokens.includes(eventType)) {
    state.jumpEventTokens = state.jumpEventTokens.filter((item) => item !== eventType);
    return;
  }
  const options = jumpOptions();
  const orderMap = new Map(options.map((option, index) => [option.value, index]));
  const next = [...state.jumpEventTokens, eventType];
  next.sort((a, b) => (orderMap.get(a) ?? 0) - (orderMap.get(b) ?? 0));
  state.jumpEventTokens = next;
};

export const clearJumpEvents = () => {
  state.jumpEventTokens = [];
};

export const matchJumpToken = (eventType: string, token: string) => {
  return eventType.toLowerCase() === token.toLowerCase();
};

export const badgeVariantFromStatus = (status: string) => {
  if (status === "success") return "success";
  if (status === "warn") return "warning";
  if (status === "error") return "destructive";
  return "secondary";
};

export const getEventMessage = (evt: VizEvent | null) => {
  if (!evt) return "";
  const payload = evt.payload ?? {};
  if (evt.event_type === "diagnostic_warning") {
    return String(payload.message || "诊断告警");
  }
  if (evt.event_type === "error") {
    return String(payload.message || payload.error_type || "执行异常");
  }
  if (evt.event_type === "workflow_started") {
    const workflowId = String((payload as any)?.workflow_id ?? "").trim();
    const maxConc = (payload as any)?.max_concurrency;
    const parts: string[] = [];
    if (workflowId) parts.push(workflowId);
    if (maxConc !== undefined && maxConc !== null && maxConc !== "") parts.push(`max_concurrency=${maxConc}`);
    return parts.length ? `workflow 开始 (${parts.join(", ")})` : "workflow 开始";
  }
  if (evt.event_type === "workflow_finished") {
    const total = (payload as any)?.total_duration_ms;
    const dur = total !== undefined && total !== null && total !== "" ? `${total}ms` : "";
    return dur ? `workflow 完成 (dur=${dur})` : "workflow 完成";
  }
  if (evt.event_type === "workflow_node_started") {
    const nodeId = String(evt.node_ref?.id ?? "").trim();
    const attempt = (payload as any)?.attempt;
    const windowId = (payload as any)?.parallel_window;
    const parts: string[] = [];
    if (attempt !== undefined && attempt !== null && attempt !== "") parts.push(`attempt=${attempt}`);
    if (windowId !== undefined && windowId !== null && windowId !== "") parts.push(`window=${windowId}`);
    const label = nodeId ? getNodeLabel(nodeId) : "workflow_node";
    return parts.length ? `${label} 开始 (${parts.join(", ")})` : `${label} 开始`;
  }
  if (evt.event_type === "workflow_node_completed") {
    const nodeId = String(evt.node_ref?.id ?? "").trim();
    const durMs = (payload as any)?.duration_ms;
    const attempt = (payload as any)?.attempt;
    const parts: string[] = [];
    if (durMs !== undefined && durMs !== null && durMs !== "") parts.push(`dur=${durMs}ms`);
    if (attempt !== undefined && attempt !== null && attempt !== "") parts.push(`attempt=${attempt}`);
    const label = nodeId ? getNodeLabel(nodeId) : "workflow_node";
    return parts.length ? `${label} 完成 (${parts.join(", ")})` : `${label} 完成`;
  }
  if (evt.event_type === "run_started") {
    const targets = Array.isArray(payload.targets) ? payload.targets.length : null;
    const batchSize = payload.batch_size ?? null;
    const parts: string[] = [];
    if (targets !== null) parts.push(`targets=${targets}`);
    if (batchSize !== null) parts.push(`batch=${batchSize}`);
    return parts.length ? `开始执行 (${parts.join(", ")})` : "开始执行";
  }
  if (evt.event_type === "run_finished") {
    const totalBatches = payload.total_batches ?? null;
    const duration = payload.total_duration_ms !== undefined ? `${payload.total_duration_ms}ms` : null;
    const parts: string[] = [];
    if (totalBatches !== null) parts.push(`batches=${totalBatches}`);
    if (duration) parts.push(`dur=${duration}`);
    return parts.length ? `执行完成 (${parts.join(", ")})` : "执行完成";
  }
  if (evt.event_type === "output_target_finished") {
    const targetId = String(payload.target_id ?? "").trim();
    const rows = payload.row_count ?? null;
    const errors = payload.error_count ?? null;
    const duration = payload.duration_ms !== undefined ? `${payload.duration_ms}ms` : null;
    const sheet = String(payload.sheet_name ?? "").trim();
    const disabled = payload.disabled === true;
    const parts: string[] = [];
    if (rows !== null) parts.push(`rows=${rows}`);
    if (errors !== null) parts.push(`errors=${errors}`);
    if (duration) parts.push(`dur=${duration}`);
    if (sheet) parts.push(`sheet=${sheet}`);
    if (disabled) parts.push("disabled");
    const label = targetId ? `输出 ${targetId} 完成` : "输出完成";
    return parts.length ? `${label} (${parts.join(", ")})` : label;
  }
  if (evt.event_type === "batch_started") {
    const num = payload.batch_num ?? null;
    const rows = payload.row_count ?? null;
    if (num !== null && rows !== null) return `批次 ${num} 开始 (rows=${rows})`;
    if (num !== null) return `批次 ${num} 开始`;
    return "批次开始";
  }
  if (evt.event_type === "batch_finished") {
    const num = payload.batch_num ?? null;
    const duration = payload.duration_ms !== undefined ? `${payload.duration_ms}ms` : null;
    if (num !== null && duration) return `批次 ${num} 完成 (dur=${duration})`;
    if (num !== null) return `批次 ${num} 完成`;
    return "批次完成";
  }
  if (evt.event_type === "stage_span") {
    const stage = String((payload as any)?.stage ?? "").trim();
    const num = resolveEventBatchNum(evt);
    const duration = (payload as any)?.duration_ms;
    const durationText = duration !== undefined && duration !== null ? `${duration}ms` : "";
    const parts = [num !== null ? `批次 ${num}` : "", stage ? stage : "", durationText].filter(Boolean);
    return parts.length ? parts.join(" ") : "阶段耗时";
  }
  if (evt.event_type === "adaptive_scheduler_decision") {
    const num = resolveEventBatchNum(evt);
    const layer = (payload as any)?.layer_index;
    const decision = String((payload as any)?.decision ?? "").trim();
    const backend = String((payload as any)?.backend ?? "").trim();
    const reason = String((payload as any)?.reason ?? "").trim();
    const tasks = (payload as any)?.layer_task_count;
    const parts: string[] = [];
    if (num !== null) parts.push(`批次 ${num}`);
    if (layer !== undefined && layer !== null && layer !== "") parts.push(`L${layer}`);
    if (decision) parts.push(decision);
    if (backend) parts.push(`(${backend})`);
    if (tasks !== undefined && tasks !== null && tasks !== "") parts.push(`tasks=${tasks}`);
    if (reason) parts.push(`reason=${reason}`);
    return parts.length ? parts.join(" ") : "调度决策";
  }
  if (evt.event_type === "loader_called") {
    const result = payload.result_count ?? payload.result_size ?? payload.row_count;
    if (result !== undefined) {
      return `load ${payload.loader_name ?? ""} (${result})`;
    }
  }
  if (evt.event_type === "field_computed") {
    const fieldKey = payload.field_key ?? "";
    const count = payload.cluster_count ?? null;
    if (count !== null && count !== undefined && Number(count) > 1) {
      return fieldKey ? `${fieldKey} x${count}` : `field_computed x${count}`;
    }
    return String(fieldKey || "");
  }
  if (evt.event_type === "row_written") {
    const batchNum = payload.batch_num ?? null;
    const count = payload.cluster_count ?? null;
    const label = batchNum !== null ? `批次 ${batchNum}` : "批次";
    if (count !== null && count !== undefined && Number(count) > 1) {
      return `${label} 写出行 x${count}`;
    }
    return `${label} 写出行`;
  }
  if (evt.event_type === "row_released") {
    const batchNum = payload.batch_num ?? null;
    const count = payload.cluster_count ?? null;
    const label = batchNum !== null ? `批次 ${batchNum}` : "批次";
    if (count !== null && count !== undefined && Number(count) > 1) {
      return `${label} 释放行缓存 x${count}`;
    }
    return `${label} 释放行缓存`;
  }
  if (evt.event_type === "relation_lookup") {
    const fieldKey = payload.field_key ?? "";
    const target = payload.target_source ?? "";
    const count = payload.cluster_count ?? null;
    const base = target ? `${fieldKey} -> ${target}` : String(fieldKey || "relation_lookup");
    if (count !== null && count !== undefined && Number(count) > 1) {
      return `${base} x${count}`;
    }
    return base;
  }
  if (evt.event_type === "memory_released") {
    const fieldKey = payload.field_key ?? "";
    const batchNum = payload.batch_num !== undefined ? `batch=${payload.batch_num}` : "";
    const remaining = payload.remaining_fields !== undefined ? `remaining=${payload.remaining_fields}` : "";
    const reason = payload.reason ? String(payload.reason) : "";
    const parts = [batchNum, remaining, reason].filter(Boolean);
    if (fieldKey) {
      return parts.length ? `释放 ${fieldKey} (${parts.join(", ")})` : `释放 ${fieldKey}`;
    }
    return parts.length ? `释放内存 (${parts.join(", ")})` : "释放内存";
  }
  return "";
};

export const getEventTone = (evt: VizEvent | null) => {
  if (!evt) return "text-slate-500";
  if (evt.event_type === "error") return "text-rose-600";
  if (evt.event_type === "diagnostic_warning") return "text-amber-600";
  if (evt.event_type === "output_target_finished") {
    const payload = evt.payload ?? {};
    const errorCount = Number((payload as any)?.error_count ?? 0);
    const disabled = Boolean((payload as any)?.disabled);
    if ((Number.isFinite(errorCount) && errorCount > 0) || disabled) {
      return "text-rose-600";
    }
    return "text-emerald-700";
  }
  return "text-slate-500";
};

export const getEventActionLabel = (eventType: string) => {
  const labels: Record<string, string> = {
    workflow_started: "workflow 开始",
    workflow_finished: "workflow 完成",
    workflow_node_started: "workflow 节点开始",
    workflow_node_completed: "workflow 节点完成",
    run_started: "开始执行",
    run_finished: "执行完成",
    batch_started: "开始批次",
    batch_finished: "完成批次",
    output_target_finished: "输出目标完成",
    loader_called: "加载数据",
    field_computed: "计算字段",
    column_written: "写出字段",
    row_written: "写出行",
    row_released: "释放行缓存",
    relation_lookup: "引用查询",
    memory_released: "释放内存",
    stage_span: "阶段耗时",
    adaptive_scheduler_decision: "调度决策",
    diagnostic_warning: "诊断告警",
    error: "执行错误"
  };
  return labels[eventType] ?? eventType;
};

const resetEventTypeStats = (data: VizEvent[]) => {
  const order: string[] = [];
  const counts = new Map<string, number>();
  for (const evt of data) {
    const eventType = evt.event_type;
    if (!eventType) continue;
    const rawCount = (evt.payload as any)?.cluster_count;
    let increment = 1;
    if (rawCount !== undefined && rawCount !== null) {
      const parsed = Number(rawCount);
      if (Number.isFinite(parsed) && parsed > 1) {
        increment = parsed;
      }
    }
    if (!counts.has(eventType)) {
      order.push(eventType);
      counts.set(eventType, increment);
    } else {
      counts.set(eventType, (counts.get(eventType) ?? 0) + increment);
    }
  }
  state.eventTypeOrder = order;
  state.eventTypeCounts = counts;
};

const formatValue = (value: any) => {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

const trimEvents = (data: VizEvent[]) => {
  if (data.length <= MAX_EVENTS_IN_MEMORY) {
    return { events: data, trimmed: 0 };
  }
  const trimmed = data.length - MAX_EVENTS_IN_MEMORY;
  return { events: data.slice(trimmed), trimmed };
};

export const isExpandableValue = (value: string) => {
  if (!value) return false;
  return value.length > 28 || value.includes(",") || value.includes("\n");
};

const VALUE_DIALOG_WIDTH = 380;
const VALUE_DIALOG_DEFAULT_HEIGHT = 280;

const computeValueDialogPosition = () => {
  const margin = 12;
  const gap = 8;
  const vw = typeof window !== "undefined" ? window.innerWidth : 0;
  const vh = typeof window !== "undefined" ? window.innerHeight : 0;

  const anchorEl = state.valueDialogAnchorEl;
  const anchorRect = anchorEl ? anchorEl.getBoundingClientRect() : null;

  const safeTop = Math.max(margin, state.panelDockTop);
  const maxHeight = Math.max(160, Math.min(VALUE_DIALOG_DEFAULT_HEIGHT, vh - safeTop - margin));

  let placement: "left" | "right" = "right";
  let left = margin;
  let top = safeTop;

  if (anchorRect && vw && vh) {
    // Prefer opening away from the screen edge:
    // - Anchor on left -> open to the right
    // - Anchor on right -> open to the left
    const preferRight = anchorRect.left < vw / 2;
    placement = preferRight ? "right" : "left";

    left = preferRight ? anchorRect.right + gap : anchorRect.left - gap - VALUE_DIALOG_WIDTH;
    left = clamp(left, margin, vw - margin - VALUE_DIALOG_WIDTH);

    top = clamp(anchorRect.top, safeTop, vh - margin - maxHeight);
  }

  return { left, top, placement, maxHeight };
};

export const repositionValueDialog = () => {
  if (!state.valueDialogOpen) return;
  const pos = computeValueDialogPosition();
  state.valueDialogPosition = { left: pos.left, top: pos.top, placement: pos.placement, maxHeight: pos.maxHeight };
};

export const closeValueDialog = () => {
  state.valueDialogOpen = false;
  state.valueDialogTitle = "";
  state.valueDialogContent = "";
  state.valueDialogAnchorEl = null;
  state.valueDialogPosition = null;
};

export const registerValueDialogRoot = (root: HTMLDivElement | null) => {
  state.valueDialogRoot = root;
};

export const openValueDialog = (title: string, value: string, anchorEl?: HTMLElement | null) => {
  state.valueDialogTitle = title;
  state.valueDialogContent = value;
  state.valueDialogAnchorEl = anchorEl ?? null;
  state.valueDialogOpen = true;
  repositionValueDialog();
};

const isInteractiveTarget = (target: EventTarget | null) => {
  if (!(target instanceof Element)) return false;
  const interactive = target.closest(
    "button, a, input, textarea, select, option, label, summary, details, [data-no-drag]"
  );
  return Boolean(interactive);
};

export const startPanelDrag = (
  panel: "inspector" | "planLens" | "playback",
  event: PointerEvent,
  root?: HTMLElement | null
) => {
  if (event.button !== 0) return;
  if (isInteractiveTarget(event.target)) return;

  if (root) {
    const rect = root.getBoundingClientRect();
    const border = 14;
    const header = 52;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const inBorder = x <= border || x >= rect.width - border || y <= border || y >= rect.height - border;
    const inHeader = y <= header;
    if (!inBorder && !inHeader) return;
  }
  const base =
    panel === "inspector"
      ? state.inspectorOffset
      : panel === "planLens"
        ? state.planLensOffset
        : state.playbackOffset;
  state.panelDrag = {
    panel,
    startX: event.clientX,
    startY: event.clientY,
    baseX: base.x,
    baseY: base.y
  };
  event.preventDefault();
};

export const handlePanelMove = (event: PointerEvent) => {
  if (!state.panelDrag) return;
  const dx = event.clientX - state.panelDrag.startX;
  const dy = event.clientY - state.panelDrag.startY;
  if (state.panelDrag.panel === "inspector") {
    state.inspectorOffset = { x: state.panelDrag.baseX + dx, y: state.panelDrag.baseY + dy };
    if (state.valueDialogOpen && state.valueDialogAnchorEl) repositionValueDialog();
    return;
  }
  if (state.panelDrag.panel === "planLens") {
    state.planLensOffset = { x: state.panelDrag.baseX + dx, y: state.panelDrag.baseY + dy };
    if (state.valueDialogOpen && state.valueDialogAnchorEl) repositionValueDialog();
    return;
  }
  state.playbackOffset = { x: state.panelDrag.baseX + dx, y: state.panelDrag.baseY + dy };
  if (state.valueDialogOpen && state.valueDialogAnchorEl) repositionValueDialog();
};

export const handlePanelUp = () => {
  state.panelDrag = null;
};

const fitTimelineView = () => {
  if (state.viewMode !== "timeline") return;
  const visibleNodes = state.nodes.filter((node) => {
    if ((node as any).hidden) return false;
    if ((node.data as any)?.sequence_hidden) return false;
    return true;
  });
  if (!visibleNodes.length) return;
  try {
    if (flowApi?.fitView) {
      // @ts-ignore fitView accepts nodes list in SvelteFlow.
      void flowApi.fitView({ padding: 0.18, duration: motionDuration(280), nodes: visibleNodes });
    }
  } catch (err) {
    try {
      if (flowApi?.fitView) {
        void flowApi.fitView({ padding: 0.18, duration: motionDuration(280) });
      }
    } catch {
      // ignore viewport errors
    }
  }
};

const scheduleTimelineFit = () => {
  if (!state.autoFitTimeline || state.viewMode !== "timeline") return;
  const token = `${state.playbackIndex}-${state.nodes.length}-${state.events.length}-${state.stageFilterEnabled}-${state.currentStageFilterLevel ?? ""}`;
  if (token === state.fitToken) return;
  state.fitToken = token;
  if (state.fitPending) return;
  state.fitPending = true;
  window.requestAnimationFrame(() => {
    state.fitPending = false;
    fitTimelineView();
  });
};

export const getEventSummaryItems = (evt: VizEvent | null) => {
  if (!evt) return [];
  const payload = evt.payload ?? {};
  const items: Array<{ label: string; value: string }> = [];
  const push = (label: string, value: any) => {
    if (value === undefined || value === null || value === "") return;
    items.push({ label, value: formatValue(value) });
  };
  if (evt.event_type === "loader_called") {
    push("loader", payload.loader_name);
    push("结果数", payload.result_count);
    push("缓存", payload.cache_status);
    push("keys", payload.lookup_key_count);
    push("字段", payload.field_keys);
    push("耗时", payload.duration_ms !== undefined ? `${payload.duration_ms}ms` : null);
    push("batch", payload.batch_num);
  } else if (evt.event_type === "field_computed") {
    push("count", payload.cluster_count);
    push("field", payload.field_key);
    push("row", payload.row_id);
    push("row_first", (payload as any).cluster_first_row_id);
    push("row_last", (payload as any).cluster_last_row_id);
    push("类型", payload.result_type);
    push("为空", payload.is_null);
  } else if (evt.event_type === "batch_started") {
    push("batch", payload.batch_num);
    push("行数", payload.row_count);
  } else if (evt.event_type === "batch_finished") {
    push("batch", payload.batch_num);
    push("耗时", payload.duration_ms !== undefined ? `${payload.duration_ms}ms` : null);
  } else if (evt.event_type === "column_written") {
    push("field", payload.field_key);
    push("行数", payload.row_count);
    push("batch", payload.batch_num);
  } else if (evt.event_type === "row_written") {
    push("count", payload.cluster_count);
    push("row", payload.row_id);
    push("row_first", (payload as any).cluster_first_row_id);
    push("row_last", (payload as any).cluster_last_row_id);
    push("列数", payload.field_count);
    push("行号", payload.row_index);
    push("batch", payload.batch_num);
  } else if (evt.event_type === "row_released") {
    push("count", payload.cluster_count);
    push("row", payload.row_id);
    push("row_first", (payload as any).cluster_first_row_id);
    push("row_last", (payload as any).cluster_last_row_id);
    push("释放", payload.released_fields_count);
    push("保留", payload.retained_fields_count);
    push("batch", payload.batch_num);
  } else if (evt.event_type === "relation_lookup") {
    push("count", payload.cluster_count);
    push("field", payload.field_key);
    push("row", payload.row_id);
    push("row_first", (payload as any).cluster_first_row_id);
    push("row_last", (payload as any).cluster_last_row_id);
    push("target", payload.target_source);
    push("error", payload.error_message);
  } else if (evt.event_type === "memory_released") {
    push("field", payload.field_key);
    push("loader", payload.loader_name);
    push("原因", payload.reason);
    push("剩余", payload.remaining_fields);
    push("提取", payload.extracted_fields_count);
    push("batch", payload.batch_num);
  } else if (evt.event_type === "run_started") {
    push("batch_size", payload.batch_size);
    push("targets", payload.targets);
  } else if (evt.event_type === "run_finished") {
    push("批次", payload.total_batches);
    push("耗时", payload.total_duration_ms !== undefined ? `${payload.total_duration_ms}ms` : null);
  } else if (evt.event_type === "workflow_started") {
    push("workflow", (payload as any)?.workflow_id);
    push("max_concurrency", (payload as any)?.max_concurrency);
  } else if (evt.event_type === "workflow_finished") {
    push("耗时", (payload as any)?.total_duration_ms !== undefined ? `${(payload as any)?.total_duration_ms}ms` : null);
  } else if (evt.event_type === "workflow_node_started") {
    push("attempt", (payload as any)?.attempt);
    push("worker", (payload as any)?.worker);
    push("parallel_window", (payload as any)?.parallel_window);
    push("artifact", (payload as any)?.artifact);
  } else if (evt.event_type === "workflow_node_completed") {
    push("耗时", (payload as any)?.duration_ms !== undefined ? `${(payload as any)?.duration_ms}ms` : null);
    push("attempt", (payload as any)?.attempt);
    push("artifact", (payload as any)?.artifact);
  } else if (evt.event_type === "stage_span") {
    push("batch", resolveEventBatchNum(evt));
    push("stage", (payload as any)?.stage);
    push("耗时", (payload as any)?.duration_ms !== undefined ? `${(payload as any)?.duration_ms}ms` : null);
  } else if (evt.event_type === "adaptive_scheduler_decision") {
    push("batch", (payload as any)?.batch_num ?? resolveEventBatchNum(evt));
    push("layer", (payload as any)?.layer_index);
    push("decision", (payload as any)?.decision);
    push("backend", (payload as any)?.backend);
    push("reason", (payload as any)?.reason);
    push("tasks", (payload as any)?.layer_task_count);
    push("process_failure", (payload as any)?.process_failure_mode);
    push("pool_limits", (payload as any)?.pool_limits);
    push("pool_wait_ms_total", (payload as any)?.pool_wait_ms_total);
    push("pool_wait_ms_max", (payload as any)?.pool_wait_ms_max);
    push("pool_wait_count", (payload as any)?.pool_wait_count);
  } else if (evt.event_type === "output_target_finished") {
    push("target", payload.target_id);
    push("行数", payload.row_count);
    push("错误", payload.error_count);
    push("禁用", payload.disabled);
    push("耗时", payload.duration_ms !== undefined ? `${payload.duration_ms}ms` : null);
    push("sheet", payload.sheet_name);
    push("path", payload.output_path);
    push("error_type", payload.error_type);
    push("error_message", payload.error_message);
  }
  return items;
};

export const getPlaybackClusterInfo = (index: number, data: VizEvent[]) => {
  if (index <= 0 || !data.length) return null;
  const idx = index - 1;
  const nodeId = data[idx]?.node_ref?.id;
  if (!nodeId) return null;
  let start = idx;
  while (start - 1 >= 0 && data[start - 1]?.node_ref?.id === nodeId) {
    start -= 1;
  }
  let end = idx;
  while (end + 1 < data.length && data[end + 1]?.node_ref?.id === nodeId) {
    end += 1;
  }
  if (end - start <= 0) return null;
  return { position: idx - start + 1, size: end - start + 1 };
};

const getNodeLabel = (nodeId: string) => {
  if (!nodeId) return "-";
  const node = state.nodes.find((item) => item.id === nodeId);
  const label = node?.data?.label ?? node?.data?.field_key ?? node?.data?.source_id ?? node?.data?.loader_name ?? "";
  return label ? `${label} (${nodeId})` : nodeId;
};

export const handleNodeDragStart = () => {
  // no-op
};

export const handleNodeDrag = ({ targetNode, nodes: dragNodes }: { targetNode: Node | null; nodes: Node[] }) => {
  const candidates = targetNode ? [targetNode] : dragNodes;
  const levels = new Set<number>();
  for (const node of candidates) {
    const level = getStageLevel(node);
    if (level !== null) {
      levels.add(level);
    }
  }
  if (levels.size) {
    state.nodes = updateStageBands(state.nodes, levels);
  }
  state.nodes = updateIngestBands(state.nodes);
};

export const handleNodeDragStop = ({ targetNode, nodes: dragNodes }: { targetNode: Node | null; nodes: Node[] }) => {
  const candidates = targetNode ? [targetNode] : dragNodes;
  const levels = new Set<number>();
  for (const node of candidates) {
    const level = getStageLevel(node);
    if (level !== null) {
      levels.add(level);
    }
  }
  if (state.viewMode === "graph") {
    for (const node of candidates) {
      if (node?.position) {
        state.baseNodePositions.set(node.id, { x: node.position.x, y: node.position.y });
      }
    }
  }
  state.nodes = updateStageBands(state.nodes, levels.size ? levels : undefined);
  state.nodes = updateIngestBands(state.nodes);
  if (state.viewMode === "graph") {
    for (const node of state.nodes) {
      if (node.type !== "stage_band" && node.type !== "ingest_band") continue;
      if (!node.position) continue;
      state.baseNodePositions.set(node.id, { x: node.position.x, y: node.position.y });
    }
  }
};

const applySnapshot = (data: VizGraphSnapshot) => {
  state.snapshot = data;
  const vizMeta = (data?.meta as any)?.viz ?? null;
  state.runName = typeof vizMeta?.run_name === "string" ? String(vizMeta.run_name) : "";
  state.runEnv = typeof vizMeta?.env === "string" ? String(vizMeta.env) : "";
  const layout = layoutSnapshot(data);
  state.nodes = layout.nodes;
  state.baseEdges = layout.edges;
  state.baseNodePositions = new Map(layout.nodes.map((node) => [node.id, { x: node.position.x, y: node.position.y }]));
  state.adjacency = buildAdjacency(layout.edges);
  applyDecorations();
  state.nodes = updateStageBands(state.nodes);
  state.nodes = updateIngestBands(state.nodes);
  if (state.viewMode === "graph") {
    // Stage/ingest band nodes are auto-updated (size/position) based on member nodes.
    // Keep their post-update positions as the base so later `applyDecorations()` does not snap them back.
    for (const node of state.nodes) {
      if (node.type !== "stage_band" && node.type !== "ingest_band") continue;
      if (!node.position) continue;
      state.baseNodePositions.set(node.id, { x: node.position.x, y: node.position.y });
    }
  }
  void tick().then(() => {
    state.nodes = updateStageBands(state.nodes);
    state.nodes = updateIngestBands(state.nodes);
    if (state.viewMode === "graph") {
      for (const node of state.nodes) {
        if (node.type !== "stage_band" && node.type !== "ingest_band") continue;
        if (!node.position) continue;
        state.baseNodePositions.set(node.id, { x: node.position.x, y: node.position.y });
      }
    }
  });
};

const sortEvents = (events: VizEvent[]) => {
  const copied = [...events];
  copied.sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
  return copied;
};

const COLLAPSIBLE_TRACE_EVENT_TYPES = new Set(["field_computed", "row_written", "row_released", "relation_lookup"]);

const cloneEvent = (evt: VizEvent): VizEvent => {
  return {
    ...evt,
    node_ref: evt.node_ref ? { ...evt.node_ref } : { type: "", id: "" },
    payload: evt.payload ? { ...evt.payload } : {}
  };
};

const collapseTraceEvents = (events: VizEvent[]) => {
  const result: VizEvent[] = [];
  let cluster: { key: string; base: VizEvent; count: number; firstTs: number; lastTs: number } | null = null;

  const flush = () => {
    if (!cluster) return;
    if (cluster.count > 1) {
      cluster.base.payload = {
        ...(cluster.base.payload ?? {}),
        cluster_count: cluster.count,
        cluster_first_ts: cluster.firstTs,
        cluster_last_ts: cluster.lastTs
      };
      cluster.base.timestamp = cluster.lastTs;
    }
    result.push(cluster.base);
    cluster = null;
  };

  for (const evt of events) {
    const eventType = evt?.event_type ?? "";
    if (!COLLAPSIBLE_TRACE_EVENT_TYPES.has(eventType)) {
      flush();
      result.push(evt);
      continue;
    }
    const nodeId = evt?.node_ref?.id ?? "";
    const batchNum = (evt?.payload as any)?.batch_num ?? "";
    const key = `${eventType}|${evt?.run_id ?? ""}|${nodeId}|${batchNum}`;
    if (cluster && cluster.key === key) {
      cluster.count += 1;
      cluster.lastTs = evt.timestamp ?? cluster.lastTs;
      const rowId = (evt?.payload as any)?.row_id;
      if (rowId !== undefined && rowId !== null && rowId !== "") {
        (cluster.base.payload as any).cluster_last_row_id = String(rowId);
      }
      continue;
    }
    flush();
    const base = cloneEvent(evt);
    const ts = base.timestamp ?? 0;
    const rowId = (base?.payload as any)?.row_id;
    if (rowId !== undefined && rowId !== null && rowId !== "") {
      (base.payload as any).cluster_first_row_id = String(rowId);
      (base.payload as any).cluster_last_row_id = String(rowId);
    }
    cluster = { key, base, count: 1, firstTs: ts, lastTs: ts };
  }
  flush();
  return result;
};

const buildEffectiveEvents = () => {
  const base = state.baseEventsAll ?? [];
  const includeTrace = state.eventSourceMode === "events+trace" && state.traceEventsAll.length > 0;
  const merged = includeTrace ? [...base, ...state.traceEventsAll] : [...base];
  const hidden = new Set(state.hiddenEventTypes ?? []);
  const filtered = hidden.size ? merged.filter((evt) => !hidden.has(evt.event_type)) : merged;
  const sorted = sortEvents(filtered);
  if (includeTrace && state.traceCollapse) {
    return collapseTraceEvents(sorted);
  }
  return sorted;
};

const applyEvents = (data: VizEvent[]) => {
  const trimmed = trimEvents(data);
  state.eventsAll = trimmed.events;

  const runIds: string[] = [];
  const seen = new Set<string>();
  for (const evt of state.eventsAll) {
    const runId = evt.run_id ?? "";
    if (!runId) continue;
    if (!seen.has(runId)) {
      seen.add(runId);
      runIds.push(runId);
    }
  }
  state.eventRunIds = runIds;

  if (state.activeEventRunId && !seen.has(state.activeEventRunId)) {
    state.activeEventRunId = "";
  }
  if (!state.activeEventRunId) {
    if (runIds.length === 1) {
      state.activeEventRunId = runIds[0];
    } else if (runIds.length > 1) {
      state.activeEventRunId = runIds[runIds.length - 1];
    }
  }

  state.events = state.activeEventRunId
    ? state.eventsAll.filter((evt) => evt.run_id === state.activeEventRunId)
    : state.eventsAll;

  const nextRunId = state.events[0]?.run_id ?? "";
  if (nextRunId !== state.lastEventsRunId) {
    state.jumpDefaultsApplied = false;
    state.jumpEventTokens = [];
    state.lastEventsRunId = nextRunId;
  }
  resetEventTypeStats(state.events);
  if (!state.jumpDefaultsApplied && state.jumpEventTokens.length === 0) {
    const available = new Set(state.eventTypeOrder ?? []);
    const defaults = [
      "error",
      "diagnostic_warning",
      "workflow_node_started",
      "workflow_node_completed",
      "workflow_started",
      "workflow_finished",
      "batch_started",
      "batch_finished",
      "loader_called",
      "stage_span"
    ];
    state.jumpEventTokens = defaults.filter((token) => available.has(token));
    state.jumpDefaultsApplied = true;
  }

  const nextIndex = clamp(state.playbackIndex, 0, state.events.length);
  setPlaybackIndex(nextIndex, false, true);
  state.lastUpdated = Date.now() / 1000;
};

const applyEffectiveEvents = () => {
  applyEvents(buildEffectiveEvents());
};

const ensureTraceLoaded = async (run: RunSource) => {
  if (!run.traceFile) {
    state.traceEventsAll = [];
    state.traceStatus = "unavailable";
    return;
  }
  if (state.traceStatus === "loaded") {
    return;
  }
  state.traceStatus = "loading";
  try {
    const text = await readFileTail(run.traceFile, TRACE_TAIL_BYTES);
    const parsed = parseJsonl(text);
    state.traceEventsAll = normalizeVizEvents(parsed);
    state.traceStatus = "loaded";
  } catch (err) {
    console.error("read trace file failed", err);
    state.traceEventsAll = [];
    state.traceStatus = "error";
  }
};

const applyTraceFilterDefaults = () => {
  if (state.traceFilterDefaultsApplied) {
    return;
  }
  const next = new Set(state.hiddenEventTypes ?? []);
  next.add("row_released");
  next.add("relation_lookup");
  state.hiddenEventTypes = Array.from(next);
  state.traceFilterDefaultsApplied = true;
};

export const onPickReplay = async () => {
  if (!state.replayInput) return;
  state.replayInput.value = "";
  state.replayInput.click();
};

export const onVizFolder = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (!files.length) return;
  const { directoryLabel, runs } = buildRunsFromFiles(files);
  await setRunSources(directoryLabel, runs);
};

const DEV_REPLAY_ENDPOINT = VIZ_REPLAY_ROUTE;

const fetchReplayFileText = async (path: string): Promise<string | null> => {
  try {
    const url = new URL(DEV_REPLAY_ENDPOINT, window.location.origin);
    url.searchParams.set("path", path);
    const resp = await fetch(url.toString());
    if (!resp.ok) return null;
    return await resp.text();
  } catch (err) {
    console.error("fetch replay file failed", err);
    return null;
  }
};

export const autoloadReplayFromQuery = async () => {
  if (!import.meta.env.DEV) return;
  if (typeof window === "undefined") return;

  const bundleMatch = (window.location.search || "").match(/(?:\?|&)bundle=([^&]*)/);
  const bundleManifest = bundleMatch ? decodeURIComponent(bundleMatch[1]) : null;
  if (bundleManifest) {
    const manifestPath = String(bundleManifest).replace(/^\/+/, "");
    const text = await fetchReplayFileText(manifestPath);
    if (!text) {
      state.status = "bundle manifest 未找到";
      return;
    }
    let manifest: any = null;
    try {
      manifest = JSON.parse(text);
    } catch (err) {
      console.error("parse bundle manifest failed", err);
      state.status = "bundle manifest 解析失败";
      return;
    }

    const runsRaw = Array.isArray(manifest?.runs) ? manifest.runs : [];
    const directoryLabel =
      typeof manifest?.directoryLabel === "string" && manifest.directoryLabel.trim()
        ? String(manifest.directoryLabel).trim()
        : (() => {
            const first = runsRaw[0]?.path;
            const parts = typeof first === "string" ? String(first).replace(/^\/+/, "").split("/").filter(Boolean) : [];
            return parts.length > 1 ? parts.slice(0, -1).join("/") : String(first || "");
          })();

    const now = Date.now();
    const runSources: RunSource[] = [];
    for (const item of runsRaw) {
      const runId = typeof item?.id === "string" ? String(item.id).trim() : "";
      const runDir = typeof item?.path === "string" ? String(item.path).replace(/^\/+/, "").trim() : "";
      if (!runId || !runDir) continue;

      const [snapshotText, eventsText, scheduleText, traceText] = await Promise.all([
        fetchReplayFileText(`${runDir}/viz_snapshot.json`),
        fetchReplayFileText(`${runDir}/viz_events.jsonl`),
        fetchReplayFileText(`${runDir}/viz_schedule_plan.json`),
        fetchReplayFileText(`${runDir}/viz_trace.jsonl`)
      ]);

      if (!snapshotText && !eventsText && !scheduleText) {
        continue;
      }

      runSources.push({
        id: runId,
        label: runId,
        snapshotFile: snapshotText ? new File([snapshotText], "viz_snapshot.json", { type: "application/json", lastModified: now }) : undefined,
        eventsFile: eventsText ? new File([eventsText], "viz_events.jsonl", { type: "application/x-ndjson", lastModified: now }) : undefined,
        schedulePlanFile: scheduleText
          ? new File([scheduleText], "viz_schedule_plan.json", { type: "application/json", lastModified: now })
          : undefined,
        traceFile: traceText ? new File([traceText], "viz_trace.jsonl", { type: "application/x-ndjson", lastModified: now }) : undefined,
        lastModified: now
      });
    }

    if (!runSources.length) {
      state.status = "bundle manifest 无有效 runs";
      return;
    }

    await setRunSources(directoryLabel, runSources);
    return;
  }

  const match = (window.location.search || "").match(/(?:\?|&)replay=([^&]*)/);
  const dir = match ? decodeURIComponent(match[1]) : null;
  if (!dir) return;

  let replayDir = String(dir).replace(/^\/+/, "");
  const parts = replayDir.split("/").filter(Boolean);
  if (parts.length && (parts[parts.length - 1].endsWith(".json") || parts[parts.length - 1].endsWith(".jsonl"))) {
    parts.pop();
    replayDir = parts.join("/");
  }
  if (!replayDir) {
    state.status = "回放路径无效";
    return;
  }
  const replayParts = replayDir.split("/").filter(Boolean);
  const runLabel = replayParts.length ? replayParts[replayParts.length - 1] : replayDir;
  const directoryLabel = replayParts.length > 1 ? replayParts.slice(0, -1).join("/") : replayDir;
  const now = Date.now();

  const [snapshotText, eventsText, scheduleText, traceText] = await Promise.all([
    fetchReplayFileText(`${replayDir}/viz_snapshot.json`),
    fetchReplayFileText(`${replayDir}/viz_events.jsonl`),
    fetchReplayFileText(`${replayDir}/viz_schedule_plan.json`),
    fetchReplayFileText(`${replayDir}/viz_trace.jsonl`)
  ]);

  if (!snapshotText && !eventsText && !scheduleText) {
    state.status = "回放路径未找到";
    return;
  }

  const run: RunSource = {
    id: runLabel,
    label: runLabel,
    snapshotFile: snapshotText ? new File([snapshotText], "viz_snapshot.json", { type: "application/json", lastModified: now }) : undefined,
    eventsFile: eventsText ? new File([eventsText], "viz_events.jsonl", { type: "application/x-ndjson", lastModified: now }) : undefined,
    schedulePlanFile: scheduleText
      ? new File([scheduleText], "viz_schedule_plan.json", { type: "application/json", lastModified: now })
      : undefined,
    traceFile: traceText ? new File([traceText], "viz_trace.jsonl", { type: "application/x-ndjson", lastModified: now }) : undefined,
    lastModified: now
  };

  await setRunSources(directoryLabel, [run]);
};

const setRunSources = async (label: string, runs: RunSource[]) => {
  state.runSources = runs;
  state.directoryLabel = label;
  const pickWorkflowRun = () => {
    for (const run of runs) {
      const id = String(run?.id ?? "").toLowerCase();
      const name = String(run?.label ?? "").toLowerCase();
      if (id === "workflow" || name === "workflow") return run;
      if (id.endsWith(":workflow") || name.endsWith(":workflow")) return run;
    }
    return null;
  };
  const selected = pickWorkflowRun() ?? pickLatestRun(runs);
  state.activeRunId = selected?.id ?? runs[0]?.id ?? "";
  state.status = selected ? "已加载目录" : "目录为空";
  if (selected) {
    await activateRun(selected);
  } else {
    resetGraphState();
  }
};

const activateRun = async (run: RunSource) => {
  state.status = "正在加载";
  state.mode = "idle";
  state.baseEventsAll = [];
  state.traceEventsAll = [];
  state.schedulePlan = null;
  state.planHighlightNodeIds = [];
  state.planSelectedLayerIndex = null;
  state.planSelectedTaskId = "";
  state.planOverlayEnabled = false;
  state.planLastSelection = null;
  state.traceStatus = run.traceFile ? "idle" : "unavailable";
  state.hiddenEventTypes = ["memory_released"];
  state.traceCollapse = true;
  state.traceFilterDefaultsApplied = false;
  let snapshotText: string | null = null;
  let eventsText: string | null = null;
  let schedulePlanText: string | null = null;
  try {
    if (run.snapshotFile) {
      snapshotText = await readFile(run.snapshotFile);
    }
    if (run.eventsFile) {
      eventsText = await readFile(run.eventsFile);
    }
    if (run.schedulePlanFile) {
      schedulePlanText = await readFile(run.schedulePlanFile);
    }
  } catch (err) {
    console.error("read viz files failed", err);
  }

  if (snapshotText) {
    try {
      applySnapshot(JSON.parse(snapshotText) as VizGraphSnapshot);
    } catch (err) {
      state.status = "snapshot 解析失败";
    }
  } else {
    resetGraphState();
  }

  if (eventsText) {
    const parsed = parseJsonl(eventsText);
    if (parsed.length) {
      state.mode = "replay";
      state.baseEventsAll = normalizeVizEvents(parsed);
      applyEffectiveEvents();
    }
  }
  if (state.mode !== "replay") {
    state.viewMode = "graph";
    state.events = [];
    state.eventsAll = [];
    state.baseEventsAll = [];
    state.traceEventsAll = [];
    state.eventRunIds = [];
    state.activeEventRunId = "";
    state.playbackIndex = 0;
    state.playbackEvent = null;
  }

  if (schedulePlanText) {
    try {
      state.schedulePlan = JSON.parse(schedulePlanText) as VizSchedulePlan;
    } catch (err) {
      console.error("schedule plan 解析失败", err);
      state.schedulePlan = null;
    }
  }

  const wantsTrace = state.eventSourceMode === "events+trace";
  if (wantsTrace) {
    if (!run.traceFile) {
      state.eventSourceMode = "events";
    } else {
      applyTraceFilterDefaults();
      await ensureTraceLoaded(run);
      applyEffectiveEvents();
    }
  }

  state.status = "已加载";
};

export const onRunSelect = async () => {
  const run = state.runSources.find((item) => item.id === state.activeRunId);
  if (run) {
    await activateRun(run);
  }
};

export const onEventSourceSelect = async () => {
  stopPlayback();
  const run = activeRun();
  if (!run) return;
  if (state.eventSourceMode === "events+trace") {
    if (!run.traceFile) {
      state.eventSourceMode = "events";
      state.traceStatus = "unavailable";
      applyEffectiveEvents();
      return;
    }
    applyTraceFilterDefaults();
    await ensureTraceLoaded(run);
  }
  applyEffectiveEvents();
  state.lastUpdated = Date.now() / 1000;
};

export const toggleHiddenEventType = (eventType: string) => {
  stopPlayback();
  const token = String(eventType || "");
  if (!token) return;
  const hidden = new Set(state.hiddenEventTypes ?? []);
  if (hidden.has(token)) {
    hidden.delete(token);
  } else {
    hidden.add(token);
  }
  state.hiddenEventTypes = Array.from(hidden);
  applyEffectiveEvents();
  state.lastUpdated = Date.now() / 1000;
};

export const onTraceCollapseToggle = () => {
  stopPlayback();
  applyEffectiveEvents();
  state.lastUpdated = Date.now() / 1000;
};

export const onEventRunSelect = () => {
  stopPlayback();
  if (!state.eventsAll.length) return;
  const runIds = state.eventRunIds ?? [];
  if (state.activeEventRunId && !runIds.includes(state.activeEventRunId)) {
    state.activeEventRunId = runIds.length ? runIds[runIds.length - 1] : "";
  }
  state.events = state.activeEventRunId
    ? state.eventsAll.filter((evt) => evt.run_id === state.activeEventRunId)
    : state.eventsAll;
  const nextRunId = state.events[0]?.run_id ?? "";
  if (nextRunId !== state.lastEventsRunId) {
    state.jumpDefaultsApplied = false;
    state.jumpEventTokens = [];
    state.lastEventsRunId = nextRunId;
  }
  resetEventTypeStats(state.events);
  setPlaybackIndex(0, false, true);
  state.lastUpdated = Date.now() / 1000;
};

export const clearSelection = () => {
  state.selectedNodeId = "";
  state.selectedStageLevel = null;
  state.selectionSource = "none";
  state.focusMode = "none";
  state.focusNodeId = "";
  applyDecorations();
};

export const clearPlanLensSelection = () => {
  if (state.planSelectedLayerIndex !== null && state.planSelectedTaskId) {
    state.planLastSelection = {
      layerIndex: state.planSelectedLayerIndex,
      taskId: state.planSelectedTaskId,
      highlightNodeIds: [...state.planHighlightNodeIds]
    };
  }
  state.planSelectedLayerIndex = null;
  state.planSelectedTaskId = "";
  state.planHighlightNodeIds = [];
  state.planOverlayEnabled = false;
  applyDecorations();
};

export const restorePlanLensSelection = () => {
  const last = state.planLastSelection;
  if (!last) return;
  state.planSelectedLayerIndex = last.layerIndex;
  state.planSelectedTaskId = last.taskId;
  state.planHighlightNodeIds = [...(last.highlightNodeIds ?? [])];
  applyDecorations();
};

export const selectPlanTaskGroup = (opts: { layerIndex: number; taskId: string; fieldKeys: string[] }) => {
  const layerIndex = Number(opts.layerIndex);
  const taskId = String(opts.taskId || "");
  const fieldKeys = Array.isArray(opts.fieldKeys) ? opts.fieldKeys : [];
  if (!Number.isFinite(layerIndex) || !taskId) return;
  state.planSelectedLayerIndex = layerIndex;
  state.planSelectedTaskId = taskId;
  const knownIds = new Set(state.nodes.map((node) => String(node.id)));
  const nodeIds = fieldKeys.map((key) => `field:${key}`).filter((id) => knownIds.has(id));
  state.planHighlightNodeIds = nodeIds;
  applyDecorations();
};

export const toggleFocus = (nodeId: string) => {
  if (!nodeId) return;
  if (state.focusMode === "neighbors" && state.focusNodeId === nodeId) {
    state.focusMode = "none";
    state.focusNodeId = "";
  } else {
    state.focusMode = "neighbors";
    state.focusNodeId = nodeId;
  }
  applyDecorations();
};

export const selectNode = (node: Node | null) => {
  if (!node) return;
  if (node.type === "stage_band") {
    const level = getStageLevel(node);
    state.selectedStageLevel = level;
    state.selectedNodeId = "";
    state.selectionSource = "user";
  } else {
    state.selectedNodeId = node.id;
    state.selectedStageLevel = null;
    state.selectionSource = "user";
  }
  applyDecorations();
};

export const selectNodeById = (nodeId?: string | null) => {
  if (!nodeId) return;
  const node = state.nodes.find((item) => item.id === nodeId);
  if (node) {
    if (state.focusMode !== "none") {
      state.focusMode = "none";
      state.focusNodeId = "";
    }
    selectNode(node);
  }
};

export const openDemandFromWorkflow = async (opts: { demandRunId: string; sourceWorkflowNodeId?: string }) => {
  const demandRunId = String(opts?.demandRunId ?? "").trim();
  if (!demandRunId) return;
  const target = state.runSources.find((item) => item.id === demandRunId) ?? null;
  if (!target) return;

  const viewport = (() => {
    try {
      return flowApi?.getViewport ? flowApi.getViewport() : null;
    } catch {
      return null;
    }
  })();

  state.workflowNav = {
    returnRunId: state.activeRunId,
    returnViewMode: state.viewMode,
    returnPlaybackIndex: state.playbackIndex,
    returnViewport: viewport,
    returnSelectedNodeId: state.selectedNodeId,
    returnSelectedStageLevel: state.selectedStageLevel,
    returnSelectionSource: state.selectionSource,
    returnStageFilterEnabled: state.stageFilterEnabled,
    returnStageFilterMode: state.stageFilterMode,
    returnManualStageLevel: state.manualStageLevel,
    returnFocusMode: state.focusMode,
    returnFocusNodeId: state.focusNodeId,
    sourceWorkflowNodeId: String(opts?.sourceWorkflowNodeId ?? state.selectedNodeId ?? ""),
    demandRunId
  };

  stopPlayback();
  // Entering a demand scope should not inherit workflow-only filters/focus.
  state.stageFilterEnabled = false;
  state.focusMode = "none";
  state.focusNodeId = "";
  state.viewMode = "graph";
  state.activeRunId = demandRunId;
  await onRunSelect();
  clearSelection();
  resetView();
};

export const returnToWorkflow = async () => {
  const nav = state.workflowNav;
  if (!nav) return;
  const target = state.runSources.find((item) => item.id === nav.returnRunId) ?? null;
  if (!target) {
    state.workflowNav = null;
    return;
  }

  stopPlayback();
  state.activeRunId = nav.returnRunId;
  state.viewMode = nav.returnViewMode;
  state.stageFilterEnabled = nav.returnStageFilterEnabled;
  state.stageFilterMode = nav.returnStageFilterMode;
  state.manualStageLevel = nav.returnManualStageLevel;

  await onRunSelect();

  const focusPlayback = nav.returnViewMode === "timeline" && nav.returnSelectionSource === "playback";
  setPlaybackIndex(nav.returnPlaybackIndex, focusPlayback, true);

  if (!focusPlayback) {
    if (nav.returnSelectionSource === "none") {
      state.selectedNodeId = "";
      state.selectedStageLevel = null;
      state.selectionSource = "none";
    } else if (nav.returnSelectedNodeId) {
      selectNodeById(nav.returnSelectedNodeId);
    } else if (nav.returnSelectedStageLevel !== null && nav.returnSelectedStageLevel !== undefined) {
      const bandId = `stage-band:${nav.returnSelectedStageLevel}`;
      if (state.nodes.some((node) => node.id === bandId)) {
        selectNodeById(bandId);
      } else {
        state.selectedNodeId = "";
        state.selectedStageLevel = nav.returnSelectedStageLevel;
        state.selectionSource = nav.returnSelectionSource;
        applyDecorations();
      }
    } else {
      state.selectedNodeId = "";
      state.selectedStageLevel = null;
      state.selectionSource = nav.returnSelectionSource;
      applyDecorations();
    }

    // Restore focus after selection (selectNodeById clears focus).
    state.focusMode = nav.returnFocusMode;
    state.focusNodeId = nav.returnFocusNodeId;
    applyDecorations();
  }

  if (nav.returnViewMode === "graph" && nav.returnViewport && flowApi?.setViewport) {
    try {
      await tick();
      await flowApi.setViewport(nav.returnViewport, { duration: motionDuration(220) });
    } catch {
      // ignore viewport errors
    }
  }

  state.workflowNav = null;
};

export const onNodeClick = (event: any) => {
  const payload = event?.detail ?? event ?? {};
  const node = payload?.node ?? payload;
  if (node?.type === "ingest_band") {
    return;
  }
  const rawEvent = payload?.event ?? event?.event ?? event?.detail?.event;
  const useFocus = Boolean(rawEvent?.altKey);
  if (useFocus && node?.id) {
    toggleFocus(node.id);
  } else if (state.focusMode !== "none") {
    state.focusMode = "none";
    state.focusNodeId = "";
  }
  selectNode(node);
};

export const handleDocumentPointerDown = (event: PointerEvent) => {
  const target = event.target;
  if (!(target instanceof globalThis.Node)) return;

  if (state.jumpDropdownOpen && state.jumpDropdownAnchor && !state.jumpDropdownAnchor.contains(target)) {
    state.jumpDropdownOpen = false;
  }

  if (state.valueDialogOpen) {
    const root = state.valueDialogRoot;
    const anchor = state.valueDialogAnchorEl;
    const hitRoot = root ? root.contains(target) : false;
    const hitAnchor = anchor ? anchor.contains(target) : false;
    if (!hitRoot && !hitAnchor) closeValueDialog();
  }
};

const runIdValue = $derived(() => {
  if (state.viewMode === "timeline" && state.playbackEvent?.run_id) {
    return state.playbackEvent.run_id;
  }
  const events = visibleEvents();
  if (!events.length) return "N/A";
  return events[events.length - 1]?.run_id || "N/A";
});
export const runId = () => runIdValue();
const runLabelValue = $derived(() => {
  const name = String(state.runName || "").trim();
  if (name) return name;
  return runIdValue();
});
export const runLabel = () => runLabelValue();
const runEnvValue = $derived(() => String(state.runEnv || "").trim());
export const runEnv = () => runEnvValue();
const snapshotStatsValue = $derived(() => (state.snapshot ? summarizeSnapshot(state.snapshot) : null));
export const snapshotStats = () => snapshotStatsValue();
const modeLabelValue = $derived(() => (state.mode === "replay" ? "回放" : "未运行"));
export const modeLabel = () => modeLabelValue();
const activeRunValue = $derived(() => state.runSources.find((item) => item.id === state.activeRunId) ?? null);
export const activeRun = () => activeRunValue();
const eventModeLabelValue = $derived(() => {
  return state.eventSourceMode === "events+trace" ? "events+trace" : "events-only";
});
export const eventModeLabel = () => eventModeLabelValue();
const atLatestValue = $derived(() => state.playbackIndex >= state.events.length);
export const atLatest = () => atLatestValue();
const stageOptionsValue = $derived(() => {
  const labelByLevel = new Map<number, string>();
  if (state.snapshot?.stages) {
    for (const stage of state.snapshot.stages) {
      if (stage?.level === undefined || stage?.level === null) continue;
      const level = Number(stage.level);
      if (Number.isNaN(level)) continue;
      const label = String(stage.stage_id ?? `stage ${level}`);
      if (!labelByLevel.has(level)) {
        labelByLevel.set(level, label);
      }
    }
  }
  for (const node of state.nodes) {
    if (node.type === "output_target") {
      continue;
    }
    const level = getStageLevel(node);
    if (level !== null && !labelByLevel.has(level)) {
      labelByLevel.set(level, `stage ${level}`);
    }
  }
  return Array.from(labelByLevel.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([level, label]) => ({ level, label }));
});
export const stageOptions = () => stageOptionsValue();
const displaySourceLabelValue = $derived(() => {
  if (!state.directoryLabel) return "未设置";
  if (state.directoryLabel === "内置样例") return state.directoryLabel;
  const currentRun = activeRun();
  if (currentRun && currentRun.label && currentRun.label !== state.directoryLabel && currentRun.label !== "root") {
    return `${state.directoryLabel}/${currentRun.label}`;
  }
  return state.directoryLabel;
});
export const displaySourceLabel = () => displaySourceLabelValue();
const selectedNodeLastEventValue = $derived(() => {
  const events = visibleEvents();
  if (!state.selectedNodeId || !events.length) return null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const evt = events[i];
    if (evt.node_ref?.id === state.selectedNodeId) {
      return evt;
    }
  }
  return null;
});
export const selectedNodeLastEvent = () => selectedNodeLastEventValue();
const selectedNodeLastEventIndexValue = $derived(() => {
  if (!state.selectedNodeId || !state.events.length) return null;
  for (let i = state.events.length - 1; i >= 0; i -= 1) {
    const evt = state.events[i];
    if (evt?.node_ref?.id === state.selectedNodeId) {
      return i;
    }
  }
  return null;
});
export const selectedNodeLastEventIndex = () => selectedNodeLastEventIndexValue();
const selectedStageSummaryValue = $derived(() => {
  if (!state.selectedStageLevel) return null;
  const level = state.selectedStageLevel;
  const stage = state.snapshot?.stages?.find((item) => Number(item.level) === level);
  const label =
    stage?.stage_id ?? stageOptions().find((item) => item.level === level)?.label ?? `stage ${level}`;
  const fieldKeys = stage?.field_keys ?? [];
  const stageNodes = state.nodes.filter((node) => {
    if (node.type === "stage_band" || node.type === "ingest_band") {
      return false;
    }
    return getStageLevel(node) === level;
  });
  const loaderCount = stageNodes.filter((node) => node.type === "loader").length;
  const fieldCount = stageNodes.filter((node) => node.type === "field" || node.type === "derived").length;
  return {
    level,
    label,
    fieldKeys,
    fieldKeysText: formatValue(fieldKeys),
    nodeCount: stageNodes.length,
    loaderCount,
    fieldCount: fieldKeys.length ? fieldKeys.length : fieldCount
  };
});
export const selectedStageSummary = () => selectedStageSummaryValue();
const nodeSummaryValue = $derived(() => (state.selectedNodeId ? state.nodes.find((node) => node.id === state.selectedNodeId) ?? null : null));
export const nodeSummary = () => nodeSummaryValue();
const hasSelectionValue = $derived(() => Boolean(state.selectedNodeId || selectedStageSummary()));
export const hasSelection = () => hasSelectionValue();
const playbackEventMessageValue = $derived(() => getEventMessage(state.playbackEvent));
export const playbackEventMessage = () => playbackEventMessageValue();
const playbackEventToneValue = $derived(() => getEventTone(state.playbackEvent));
export const playbackEventTone = () => playbackEventToneValue();
const selectedNodeEventMessageValue = $derived(() => getEventMessage(selectedNodeLastEvent()));
export const selectedNodeEventMessage = () => selectedNodeEventMessageValue();
const selectedNodeEventToneValue = $derived(() => getEventTone(selectedNodeLastEvent()));
export const selectedNodeEventTone = () => selectedNodeEventToneValue();
const playbackSummaryItemsValue = $derived(() => getEventSummaryItems(state.playbackEvent));
export const playbackSummaryItems = () => playbackSummaryItemsValue();
const playbackClusterInfoValue = $derived(() => getPlaybackClusterInfo(state.playbackIndex, state.events));
export const playbackClusterInfo = () => playbackClusterInfoValue();
const playbackNodeLabelValue = $derived(() => getNodeLabel(state.playbackEvent?.node_ref?.id ?? ""));
export const playbackNodeLabel = () => playbackNodeLabelValue();
const jumpOptionsValue = $derived(() => {
  return state.eventTypeOrder.map((value) => ({
    value,
    count: state.eventTypeCounts.get(value) ?? null,
    kind: "event" as const
  }));
});
export const jumpOptions = () => jumpOptionsValue();

type BatchStageSpan = {
  batchNum: number;
  loaderMs: number;
  computeMs: number;
  writeMs: number;
  totalMs: number;
  stages: Record<string, number>;
};

const stageSpansByBatchValue = $derived(() => {
  const map = new Map<number, Record<string, number>>();
  for (const evt of state.events) {
    if (evt.event_type !== "stage_span") continue;
    const payload = evt.payload ?? {};
    const batchNum = resolveEventBatchNum(evt);
    if (batchNum === null || batchNum === undefined) continue;
    const stage = String((payload as any)?.stage ?? "").trim();
    if (!stage) continue;
    const durationMs = Number((payload as any)?.duration_ms);
    if (!Number.isFinite(durationMs)) continue;
    const stages = map.get(batchNum) ?? {};
    stages[stage] = (stages[stage] ?? 0) + durationMs;
    map.set(batchNum, stages);
  }
  const items: BatchStageSpan[] = [];
  for (const [batchNum, stages] of map.entries()) {
    const loaderMs = Number(stages.loader ?? 0) || 0;
    const computeMs = Number(stages.compute ?? 0) || 0;
    const writeMs = Number(stages.write ?? 0) || 0;
    const totalMs = loaderMs + computeMs + writeMs;
    items.push({ batchNum, loaderMs, computeMs, writeMs, totalMs, stages });
  }
  items.sort((a, b) => a.batchNum - b.batchNum);
  return items;
});
export const stageSpansByBatch = () => stageSpansByBatchValue();

export type AdaptiveSchedulerDecision = {
  index: number;
  batchNum: number | null;
  layerIndex: number | null;
  decision: string;
  backend: string;
  reason: string;
  layerTaskCount: number | null;
  processFailureMode: string;
  poolWaitMsTotal: number | null;
  poolWaitMsMax: number | null;
  poolWaitCount: number | null;
  poolLimits: any;
};

const adaptiveSchedulerDecisionsValue = $derived(() => {
  const items: AdaptiveSchedulerDecision[] = [];
  const events = state.events ?? [];
  for (let i = 0; i < events.length; i += 1) {
    const evt = events[i];
    if (!evt || evt.event_type !== "adaptive_scheduler_decision") continue;
    const payload = evt.payload ?? {};
    const batchNumRaw = (payload as any)?.batch_num;
    const batchNum = batchNumRaw === undefined || batchNumRaw === null ? null : Number(batchNumRaw);
    const layerIndexRaw = (payload as any)?.layer_index;
    const layerIndex = layerIndexRaw === undefined || layerIndexRaw === null ? null : Number(layerIndexRaw);
    const decision = String((payload as any)?.decision ?? "");
    const backend = String((payload as any)?.backend ?? "");
    const reason = String((payload as any)?.reason ?? "");
    const layerTaskCountRaw = (payload as any)?.layer_task_count;
    const layerTaskCount =
      layerTaskCountRaw === undefined || layerTaskCountRaw === null || layerTaskCountRaw === "" ? null : Number(layerTaskCountRaw);
    const processFailureMode = String((payload as any)?.process_failure_mode ?? "");
    const poolWaitMsTotalRaw = (payload as any)?.pool_wait_ms_total;
    const poolWaitMsTotal =
      poolWaitMsTotalRaw === undefined || poolWaitMsTotalRaw === null || poolWaitMsTotalRaw === "" ? null : Number(poolWaitMsTotalRaw);
    const poolWaitMsMaxRaw = (payload as any)?.pool_wait_ms_max;
    const poolWaitMsMax =
      poolWaitMsMaxRaw === undefined || poolWaitMsMaxRaw === null || poolWaitMsMaxRaw === "" ? null : Number(poolWaitMsMaxRaw);
    const poolWaitCountRaw = (payload as any)?.pool_wait_count;
    const poolWaitCount =
      poolWaitCountRaw === undefined || poolWaitCountRaw === null || poolWaitCountRaw === "" ? null : Number(poolWaitCountRaw);
    items.push({
      index: i,
      batchNum: Number.isFinite(batchNum) ? batchNum : null,
      layerIndex: Number.isFinite(layerIndex) ? layerIndex : null,
      decision,
      backend,
      reason,
      layerTaskCount: Number.isFinite(layerTaskCount) ? layerTaskCount : null,
      processFailureMode,
      poolWaitMsTotal: Number.isFinite(poolWaitMsTotal) ? poolWaitMsTotal : null,
      poolWaitMsMax: Number.isFinite(poolWaitMsMax) ? poolWaitMsMax : null,
      poolWaitCount: Number.isFinite(poolWaitCount) ? poolWaitCount : null,
      poolLimits: (payload as any)?.pool_limits ?? null
    });
  }
  return items;
});
export const adaptiveSchedulerDecisions = () => adaptiveSchedulerDecisionsValue();

const adaptiveSchedulerSummaryValue = $derived(() => {
  const backendCounts = new Map<string, number>();
  const reasonCounts = new Map<string, number>();
  for (const item of adaptiveSchedulerDecisions()) {
    const backend = item.backend || "-";
    backendCounts.set(backend, (backendCounts.get(backend) ?? 0) + 1);
    const reason = item.reason || "-";
    reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
  }
  const toSorted = (map: Map<string, number>) =>
    Array.from(map.entries())
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
  return {
    backendCounts: toSorted(backendCounts),
    reasonCounts: toSorted(reasonCounts)
  };
});
export const adaptiveSchedulerSummary = () => adaptiveSchedulerSummaryValue();

const playbackBatchNumByIndexValue = $derived(() => {
  const events = state.events ?? [];
  const items: Array<number | null> = new Array(events.length);
  let current: number | null = null;
  for (let i = 0; i < events.length; i += 1) {
    const evt = events[i];
    if (evt && evt.event_type === "batch_started") {
      current = resolveEventBatchNum(evt);
    }
    items[i] = current;
    if (evt && evt.event_type === "batch_finished") {
      current = null;
    }
  }
  return items;
});

const currentBatchNumValue = $derived(() => {
  if (state.viewMode !== "timeline" || state.mode === "idle") return null;
  const idx = state.playbackIndex - 1;
  const byIndex = playbackBatchNumByIndexValue();
  if (idx >= 0 && idx < byIndex.length) {
    const inferred = byIndex[idx];
    if (inferred !== null && inferred !== undefined) {
      return inferred;
    }
  }
  const focus = state.playbackFocusRef;
  if (focus && focus.kind === "batch" && focus.batchNum !== null && focus.batchNum !== undefined) {
    return focus.batchNum;
  }
  return resolveEventBatchNum(state.playbackEvent);
});
export const currentBatchNum = () => currentBatchNumValue();

const currentBatchStageSpansValue = $derived(() => {
  const batchNum = currentBatchNum();
  if (batchNum === null || batchNum === undefined) return null;
  return stageSpansByBatch().find((item) => item.batchNum === batchNum) ?? null;
});
export const currentBatchStageSpans = () => currentBatchStageSpansValue();

const currentBatchDecisionsValue = $derived(() => {
  const batchNum = currentBatchNum();
  if (batchNum === null || batchNum === undefined) return [];
  return adaptiveSchedulerDecisions().filter((item) => item.batchNum === batchNum);
});
export const currentBatchDecisions = () => currentBatchDecisionsValue();

const currentPlanLayerIndexValue = $derived(() => {
  if (state.viewMode !== "timeline" || state.mode === "idle") return null;
  const decisions = currentBatchDecisions();
  if (!decisions.length) return null;
  const cutoff = state.playbackIndex - 1;
  let current: number | null = null;
  for (const item of decisions) {
    if (!item) continue;
    if (item.index > cutoff) break;
    if (item.layerIndex !== null && item.layerIndex !== undefined) {
      current = item.layerIndex;
    }
  }
  return current;
});
export const currentPlanLayerIndex = () => currentPlanLayerIndexValue();

const reachedPlanLayerIndicesValue = $derived(() => {
  const reached = new Set<number>();
  if (state.viewMode !== "timeline" || state.mode === "idle") return reached;
  const decisions = currentBatchDecisions();
  if (!decisions.length) return reached;
  const cutoff = state.playbackIndex - 1;
  for (const item of decisions) {
    if (!item) continue;
    if (item.index > cutoff) break;
    if (item.layerIndex !== null && item.layerIndex !== undefined) {
      reached.add(item.layerIndex);
    }
  }
  return reached;
});
export const reachedPlanLayerIndices = () => reachedPlanLayerIndicesValue();

export { formatTimestamp, statusFromEvent };
