export type VizGraphSnapshot = {
  nodes: Array<Record<string, any>>;
  edges: Array<Record<string, any>>;
  meta?: {
    schema_version?: string;
    created_at?: number;
    target_fields?: string[];
    metadata?: Record<string, any>;
  };
  stages?: Array<{ stage_id: string; level: number; field_keys: string[] }>;
};

export type VizEvent = {
  schema_version: string;
  run_id: string;
  event_type: string;
  timestamp: number;
  node_ref: { type: string; id: string };
  payload: Record<string, any>;
};

export type VizSchedulePlan = {
  meta?: {
    schema_version?: string;
    created_at?: number;
    target_fields?: string[];
  };
  targets?: string[];
  load_ref?: {
    op_count?: number;
    layer_count?: number;
    layers?: Array<{
      layer_index: number;
      op_count: number;
      rows_binding_barrier?: boolean;
      task_group_count?: number;
      tasks?: Array<{
        task_id: string;
        chain?: string[];
        fields?: string[];
        rows_binding?: boolean;
      }>;
    }>;
  };
};

export type RunSource = {
  id: string;
  label: string;
  snapshotFile?: File;
  eventsFile?: File;
  traceFile?: File;
  schedulePlanFile?: File;
  /** Optional sibling next to viz_* files; see docs/doc/viz/run-stats.md */
  runStatsFile?: File;
  lastModified?: number;
};
