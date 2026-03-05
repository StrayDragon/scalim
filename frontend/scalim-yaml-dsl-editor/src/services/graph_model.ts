export type GraphSeverity = "ok" | "warning" | "error";

export type GraphNode = {
  id: string;
  label: string;
  kind?: "main" | "source" | "derived" | "input" | "unknown";
  severity?: GraphSeverity;
  path?: string;
};

export type GraphEdge = {
  id: string;
  from: string;
  to: string;
  label?: string;
  severity?: GraphSeverity;
  path?: string;
};

export type DirectedGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const isRecord = (value: unknown): value is Record<string, any> => {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
};

const isIdentifier = (value: string): boolean => {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
};

const parseSourceFieldExpr = (expr: unknown): { sourceId: string; fieldId: string } | null => {
  if (typeof expr !== "string") return null;
  const raw = expr.trim();
  if (!raw) return null;
  const idx = raw.indexOf(".");
  if (idx <= 0 || idx >= raw.length - 1) return null;
  const sourceId = raw.slice(0, idx).trim();
  const fieldId = raw.slice(idx + 1).trim();
  if (!sourceId || !fieldId) return null;
  return { sourceId, fieldId };
};

const parseSourceFieldGroup = (value: unknown): { sourceId: string; fieldIds: string[] } | null => {
  if (typeof value === "string") {
    const parsed = parseSourceFieldExpr(value);
    if (!parsed) return null;
    return { sourceId: parsed.sourceId, fieldIds: [parsed.fieldId] };
  }
  if (Array.isArray(value) && value.length) {
    let sourceId = "";
    const fieldIds: string[] = [];
    for (const item of value) {
      const parsed = parseSourceFieldExpr(item);
      if (!parsed) return null;
      if (!sourceId) sourceId = parsed.sourceId;
      if (sourceId !== parsed.sourceId) return null;
      fieldIds.push(parsed.fieldId);
    }
    if (!sourceId) return null;
    return { sourceId, fieldIds };
  }
  return null;
};

const hasBindParam = (bindRaw: unknown): boolean => {
  if (!isRecord(bindRaw)) return false;
  const useRows = bindRaw.use_rows;
  const useKeys = bindRaw.use_keys;
  const rowsParam = isRecord(useRows) ? String(useRows.param || "").trim() : "";
  const keysParam = isRecord(useKeys) ? String(useKeys.param || "").trim() : "";
  return Boolean(rowsParam || keysParam);
};

const extractDeps = (expr: string): string[] => {
  const raw = String(expr || "");
  const tokens = raw.match(/\b[a-zA-Z_][a-zA-Z0-9_]*\b/g) || [];
  const stop = new Set([
    "and",
    "or",
    "not",
    "in",
    "is",
    "if",
    "else",
    "for",
    "while",
    "return",
    "lambda",
    "True",
    "False",
    "None",
    "ctx",
    "deps",
    "values",
    "row_id",
    "batch_num",
    "field_id",
  ]);
  const out: string[] = [];
  for (const t of tokens) {
    if (stop.has(t)) continue;
    if (out.indexOf(t) >= 0) continue;
    out.push(t);
  }
  return out;
};

export const buildRelationsGraph = (config: unknown): DirectedGraph => {
  if (!isRecord(config)) return { nodes: [], edges: [] };

  const mainSourceRaw = config.main_source;
  const mainSource = isRecord(mainSourceRaw) ? mainSourceRaw : null;
  const mainSourceId = mainSource && typeof mainSource.source_id === "string" ? mainSource.source_id.trim() : "";

  const nodes: GraphNode[] = [];
  const nodeIds = new Set<string>();
  if (mainSourceId) {
    nodes.push({ id: mainSourceId, label: mainSourceId, kind: "main", severity: "ok", path: "main_source" });
    nodeIds.add(mainSourceId);
  }

  const sourcesRaw = config.sources;
  const sources = isRecord(sourcesRaw) ? sourcesRaw : null;

  const sourcesInfo: Record<string, { bind: boolean; preload: boolean }> = {};
  if (sources) {
    for (const [sourceId, sourceDataRaw] of Object.entries(sources)) {
      const cleanedId = String(sourceId || "").trim();
      if (!cleanedId) continue;
      nodeIds.add(cleanedId);
      nodes.push({ id: cleanedId, label: cleanedId, kind: "source", severity: "ok", path: "sources." + cleanedId });

      const sourceData = isRecord(sourceDataRaw) ? sourceDataRaw : null;
      const cacheMode = sourceData ? String(sourceData.cache_mode || "").trim() : "";
      const preload = cacheMode === "preload_forever";
      const bind = sourceData ? hasBindParam(sourceData.bind) : false;
      sourcesInfo[cleanedId] = { bind, preload };
    }
  }

  nodes.sort((a, b) => {
    if (a.kind === "main" && b.kind !== "main") return -1;
    if (b.kind === "main" && a.kind !== "main") return 1;
    return a.label.localeCompare(b.label);
  });

  const edges: GraphEdge[] = [];

  const relationsRaw = config.relations;
  const relations = isRecord(relationsRaw) ? relationsRaw : null;
  if (!relations) return { nodes, edges };

  for (const [relIdRaw, relDataRaw] of Object.entries(relations)) {
    const relId = String(relIdRaw || "").trim();
    if (!relId) continue;
    const relData = isRecord(relDataRaw) ? relDataRaw : null;
    const steps = relData && Array.isArray(relData.steps) ? relData.steps : [];

    let prevTo: string | null = null;
    for (let idx = 0; idx < steps.length; idx += 1) {
      const stepRaw = steps[idx];
      const step = isRecord(stepRaw) ? stepRaw : null;
      const fromInfo = step ? parseSourceFieldGroup(step.from) : null;
      const toInfo = step ? parseSourceFieldGroup(step.to) : null;
      const fromSource = fromInfo ? fromInfo.sourceId : "";
      const toSource = toInfo ? toInfo.sourceId : "";

      const edgeId = relId + ":" + String(idx);
      const edgePath = "relations." + relId + ".steps." + String(idx);
      const label = relId + "[" + String(idx) + "]";

      let severity: GraphSeverity = "ok";
      if (!fromSource || !toSource) severity = "error";
      if (fromSource && !nodeIds.has(fromSource)) severity = "error";
      if (toSource && !nodeIds.has(toSource)) severity = "error";
      if (prevTo && fromSource && fromSource !== prevTo) severity = "error";

      const toBindPresent = step ? hasBindParam(step.to_bind) : false;
      const toSourceInfo = sourcesInfo[toSource];
      if (toSourceInfo && !toSourceInfo.preload && !(toBindPresent || toSourceInfo.bind)) severity = "error";

      edges.push({
        id: edgeId,
        from: fromSource,
        to: toSource,
        label,
        severity,
        path: edgePath,
      });

      prevTo = toSource || prevTo;
    }
  }

  return { nodes, edges };
};

export const buildDerivedDepsGraph = (config: unknown): DirectedGraph => {
  if (!isRecord(config)) return { nodes: [], edges: [] };

  const knownFieldIds = new Set<string>();
  const derivedFieldIds = new Set<string>();

  const mainSource = isRecord(config.main_source) ? (config.main_source as any) : null;
  const mainFields = mainSource && isRecord(mainSource.fields) ? (mainSource.fields as any) : null;
  if (mainFields) for (const k of Object.keys(mainFields)) knownFieldIds.add(String(k));

  const sources = isRecord(config.sources) ? (config.sources as any) : null;
  if (sources) {
    for (const srcCfgRaw of Object.values(sources)) {
      const srcCfg = isRecord(srcCfgRaw) ? (srcCfgRaw as any) : null;
      const srcFields = srcCfg && isRecord(srcCfg.fields) ? (srcCfg.fields as any) : null;
      if (!srcFields) continue;
      for (const k of Object.keys(srcFields)) knownFieldIds.add(String(k));
    }
  }

  const derived = isRecord(config.fields) ? (config.fields as any) : null;
  if (derived) {
    for (const k of Object.keys(derived)) {
      const id = String(k);
      knownFieldIds.add(id);
      derivedFieldIds.add(id);
    }
  }

  if (!derived) return { nodes: [], edges: [] };

  const nodesById: Record<string, GraphNode> = {};
  const edges: GraphEdge[] = [];

  const ensureNode = (id: string, kind: GraphNode["kind"], severity: GraphSeverity): GraphNode => {
    if (nodesById[id]) return nodesById[id] as GraphNode;
    const n: GraphNode = { id, label: id, kind, severity, path: kind === "derived" ? "fields." + id : undefined };
    nodesById[id] = n;
    return n;
  };

  for (const fieldId of Array.from(derivedFieldIds)) {
    ensureNode(fieldId, "derived", "ok");
  }

  for (const [fieldIdRaw, cfgRaw] of Object.entries(derived)) {
    const fieldId = String(fieldIdRaw || "").trim();
    if (!fieldId) continue;
    const cfg = isRecord(cfgRaw) ? (cfgRaw as any) : {};

    const compute = typeof cfg.compute === "string" ? cfg.compute : "";
    const callBy = typeof cfg.call_by === "string" ? cfg.call_by : "";
    const mode = callBy && !compute ? "call_by" : "compute";

    let tokens: string[] = [];
    if (mode === "compute") {
      tokens = extractDeps(compute);
    } else {
      const m = callBy.match(/\((.*)\)\s*$/);
      const args = m ? m[1] : "";
      tokens = extractDeps(args);
    }

    for (const dep of tokens) {
      if (!isIdentifier(dep)) continue;
      const edgeId = dep + "->" + fieldId;
      const edgePath = "fields." + fieldId;
      if (knownFieldIds.has(dep)) {
        if (derivedFieldIds.has(dep)) ensureNode(dep, "derived", "ok");
        else ensureNode(dep, "input", "ok");
        edges.push({ id: edgeId, from: dep, to: fieldId, severity: "ok", path: edgePath });
      } else {
        ensureNode(dep, "unknown", "error");
        edges.push({ id: edgeId, from: dep, to: fieldId, severity: "error", path: edgePath });
        const cur = ensureNode(fieldId, "derived", "ok");
        cur.severity = cur.severity === "error" ? "error" : "warning";
      }
    }
  }

  const nodes = Object.values(nodesById);

  // Cycle detection (derived-only).
  const derivedIds = nodes.filter((n) => n.kind === "derived").map((n) => n.id);
  const indeg: Record<string, number> = {};
  const out: Record<string, string[]> = {};
  for (const id of derivedIds) {
    indeg[id] = 0;
    out[id] = [];
  }
  for (const e of edges) {
    if (!derivedFieldIds.has(e.from) || !derivedFieldIds.has(e.to)) continue;
    out[e.from].push(e.to);
    indeg[e.to] += 1;
  }
  const q: string[] = [];
  for (const id of derivedIds) if (!indeg[id]) q.push(id);
  const seen: string[] = [];
  while (q.length) {
    const cur = q.shift() as string;
    seen.push(cur);
    for (const nxt of out[cur] || []) {
      indeg[nxt] -= 1;
      if (indeg[nxt] === 0) q.push(nxt);
    }
  }
  if (seen.length !== derivedIds.length) {
    const cycleSet = new Set(derivedIds.filter((id) => seen.indexOf(id) < 0));
    for (const n of nodes) {
      if (n.kind !== "derived") continue;
      if (!cycleSet.has(n.id)) continue;
      n.severity = "error";
    }
    for (const e of edges) {
      if (cycleSet.has(e.from) && cycleSet.has(e.to)) e.severity = "error";
    }
  }

  nodes.sort((a, b) => {
    const ka = a.kind || "unknown";
    const kb = b.kind || "unknown";
    const order = (k: string) => (k === "input" ? 0 : k === "derived" ? 1 : k === "unknown" ? 2 : 3);
    const d = order(ka) - order(kb);
    if (d) return d;
    return a.label.localeCompare(b.label);
  });

  return { nodes, edges };
};

export type GraphLayout = {
  width: number;
  height: number;
  nodePos: Record<string, { x: number; y: number; w: number; h: number; depth: number }>;
};

export const layoutLayered = (
  graph: DirectedGraph,
  opts?: {
    rootIds?: string[];
    nodeWidth?: number;
    nodeHeight?: number;
    colGap?: number;
    rowGap?: number;
    margin?: number;
  }
): GraphLayout => {
  const nodeWidth = opts?.nodeWidth ?? 164;
  const nodeHeight = opts?.nodeHeight ?? 42;
  const colGap = opts?.colGap ?? 64;
  const rowGap = opts?.rowGap ?? 24;
  const margin = opts?.margin ?? 16;

  const nodeIds = new Set(graph.nodes.map((n) => n.id));

  const out: Record<string, string[]> = {};
  for (const n of graph.nodes) out[n.id] = [];
  for (const e of graph.edges) {
    if (!nodeIds.has(e.from) || !nodeIds.has(e.to)) continue;
    out[e.from].push(e.to);
  }

  const depth: Record<string, number> = {};
  const q: string[] = [];

  const roots = (opts?.rootIds || []).filter((id) => nodeIds.has(id));
  if (roots.length) {
    for (const r of roots) {
      depth[r] = 0;
      q.push(r);
    }
  } else {
    // Multi-root: start from nodes with no incoming edges.
    const indeg: Record<string, number> = {};
    for (const n of graph.nodes) indeg[n.id] = 0;
    for (const e of graph.edges) {
      if (!nodeIds.has(e.from) || !nodeIds.has(e.to)) continue;
      indeg[e.to] += 1;
    }
    for (const [id, v] of Object.entries(indeg)) {
      if (!v) {
        depth[id] = 0;
        q.push(id);
      }
    }
  }

  while (q.length) {
    const cur = q.shift() as string;
    const nextDepth = (depth[cur] as number) + 1;
    for (const nxt of out[cur] || []) {
      if (depth[nxt] == null || depth[nxt] > nextDepth) {
        depth[nxt] = nextDepth;
        q.push(nxt);
      }
    }
  }

  let maxDepth = 0;
  for (const n of graph.nodes) {
    if (depth[n.id] != null) maxDepth = Math.max(maxDepth, depth[n.id] as number);
  }
  for (const n of graph.nodes) {
    if (depth[n.id] == null) depth[n.id] = maxDepth + 1;
  }

  const byDepth: Record<string, GraphNode[]> = {};
  for (const n of graph.nodes) {
    const d = depth[n.id] as number;
    const key = String(d);
    if (!byDepth[key]) byDepth[key] = [];
    byDepth[key].push(n);
  }
  for (const group of Object.values(byDepth)) {
    group.sort((a, b) => a.label.localeCompare(b.label));
  }

  const nodePos: GraphLayout["nodePos"] = {};
  const depths = Object.keys(byDepth)
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x))
    .sort((a, b) => a - b);
  let maxRows = 1;
  for (const d of depths) maxRows = Math.max(maxRows, (byDepth[String(d)] || []).length);

  for (const d of depths) {
    const items = byDepth[String(d)] || [];
    const x = margin + d * (nodeWidth + colGap);
    for (let i = 0; i < items.length; i += 1) {
      const y = margin + i * (nodeHeight + rowGap);
      nodePos[items[i].id] = { x, y, w: nodeWidth, h: nodeHeight, depth: d };
    }
  }

  const width = margin * 2 + (Math.max(...depths, 0) + 1) * nodeWidth + Math.max(...depths, 0) * colGap;
  const height = margin * 2 + maxRows * nodeHeight + Math.max(0, maxRows - 1) * rowGap;

  return { width: Math.max(320, Math.round(width)), height: Math.max(160, Math.round(height)), nodePos };
};

