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

export type RunStatsNode = {
  demand_id?: string;
  run_id?: string;
  name?: string;
  stages_total?: RunStatsStages;
  pipeline?: {
    total_duration_s?: number;
    total_rows_in?: number;
    total_batches?: number;
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
