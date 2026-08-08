export type RunStatsStages = {
  stream?: number;
  loader?: number;
  compute?: number;
  write?: number;
  [key: string]: number | undefined;
};

export type RunStatsLoader = {
  name?: string;
  calls?: number;
  total_s?: number;
  records?: number;
  cache_hits?: number;
  cache_misses?: number;
  cache_hit_rate?: number;
};

export type RunStatsOutput = {
  target_id?: string;
  rows?: number;
  duration_s?: number;
  path?: string;
  sheet_name?: string | null;
  error_count?: number;
  disabled?: boolean;
};

export type RunStatsNode = {
  demand_id?: string | null;
  run_id?: string | null;
  name?: string | null;
  stages_total?: RunStatsStages;
  loaders?: RunStatsLoader[];
  outputs?: RunStatsOutput[];
  memory?: {
    peak_mb?: number | null;
    start_mb?: number | null;
    end_mb?: number | null;
    increase_mb?: number | null;
  };
  pipeline?: {
    total_duration_s?: number;
    total_rows_in?: number;
    total_batches?: number;
    batch_size?: number;
  };
};

export type RunStatsV1 = {
  schema: string;
  meta?: {
    profile?: string;
    profile_meta?: {
      profile?: string;
      collectors?: string[];
      sampling_interval?: number;
    };
    [key: string]: unknown;
  };
  pipeline?: {
    total_duration_s?: number;
    total_batches?: number;
    total_rows_in?: number;
    throughput_rows_s?: number;
    node_count?: number;
  };
  memory?: {
    peak_mb?: number;
    start_mb?: number;
    end_mb?: number;
    increase_mb?: number;
  };
  stages_total?: RunStatsStages;
  loaders?: RunStatsLoader[];
  nodes?: RunStatsNode[];
  notes?: Record<string, unknown>;
};

export const RUN_STATS_SCHEMA_V1 = "scalim_run_stats/v1";

export const parseRunStatsJson = (text: string): RunStatsV1 | null => {
  try {
    const data = JSON.parse(text) as RunStatsV1;
    if (!data || typeof data !== "object") return null;
    if (data.schema !== RUN_STATS_SCHEMA_V1) return null;
    return data;
  } catch {
    return null;
  }
};

export const runStatsProfileLabel = (stats: RunStatsV1 | null | undefined): string => {
  if (!stats) return "";
  const fromMeta = stats.meta?.profile;
  if (typeof fromMeta === "string" && fromMeta.trim()) return fromMeta.trim();
  const nested = stats.meta?.profile_meta?.profile;
  if (typeof nested === "string" && nested.trim()) return nested.trim();
  return "";
};

export const isHighImpactRunStatsProfile = (profile: string): boolean => {
  const p = profile.trim().toLowerCase();
  return p === "debug" || p === "probe";
};

const uniq = (ids: string[]) => {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of ids) {
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
};

const inferKeysFromOutputs = (outputs: RunStatsOutput[] | undefined): string[] => {
  const keys: string[] = [];
  for (const output of outputs ?? []) {
    const tid = String(output?.target_id ?? "").trim();
    if (!tid) continue;
    const matched = tid.match(/^(.*?)_(sheet|csv|book)$/);
    keys.push(matched ? matched[1] : tid);
  }
  return keys;
};

export const runStatsNodeLabel = (node: RunStatsNode | null | undefined, index: number): string => {
  const raw = String(node?.name || node?.demand_id || node?.run_id || "").trim();
  if (raw) return raw;
  const inferred = inferKeysFromOutputs(node?.outputs)[0];
  if (inferred) return inferred;
  return `n${index}`;
};

export const resolveGraphNodeIdsForRunStatsNode = (
  node: RunStatsNode | null | undefined,
  graphNodeIds: string[],
  nodeIndex: number
): string[] => {
  const known = new Set(graphNodeIds);
  const keys = uniq([
    String(node?.demand_id ?? "").trim(),
    String(node?.name ?? "").trim(),
    String(node?.run_id ?? "").trim(),
    ...inferKeysFromOutputs(node?.outputs)
  ]);
  const candidates: string[] = [];
  for (const key of keys) {
    candidates.push(key, `workflow_node:${key}`);
  }
  const hits = candidates.filter((id) => known.has(id));
  if (hits.length) return uniq(hits);

  const demandNodes = graphNodeIds.filter(
    (id) => id.startsWith("workflow_node:") && !id.includes("__wf__write")
  );
  if (nodeIndex >= 0 && nodeIndex < demandNodes.length) return [demandNodes[nodeIndex]];
  return [];
};

export const resolveGraphNodeIdsForLoader = (
  loaderName: string,
  graphNodeIds: string[],
  statsNodes: RunStatsNode[] = []
): string[] => {
  const known = new Set(graphNodeIds);
  const name = String(loaderName || "").trim();
  if (!name) return [];
  const direct = [`loader:${name}`, name, `source:${name}`].filter((id) => known.has(id));
  if (direct.length) return uniq(direct);

  const related: string[] = [];
  statsNodes.forEach((node, index) => {
    const used = (node.loaders ?? []).some((loader) => String(loader?.name ?? "") === name);
    if (!used) return;
    related.push(...resolveGraphNodeIdsForRunStatsNode(node, graphNodeIds, index));
  });
  return uniq(related);
};
