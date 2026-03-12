import bundledDemandSchema from "../schema/demand.gen.json";
import bundledWorkflowSchema from "../schema/workflow.gen.json";

export type DemandSchema = Record<string, any>;
export type WorkflowSchema = Record<string, any>;

// Prefer bundling schema at build time so the editor works without any network fetches.
// (Fetching `/schema/demand.gen.json` can fail under `file://` or restrictive hosting setups.)
// Keep the runtime fetch as a fallback for advanced deployments.

let cached: Promise<DemandSchema> | null = null;
let cachedWorkflow: Promise<WorkflowSchema> | null = null;

export const loadDemandSchema = async (): Promise<DemandSchema> => {
  if (cached) return cached;
  cached = (async () => {
    if (bundledDemandSchema) return bundledDemandSchema as DemandSchema;
    const res = await fetch("/schema/demand.gen.json", { cache: "no-cache" });
    if (!res.ok) {
      throw new Error("Failed to load demand.gen.json: " + res.status);
    }
    return (await res.json()) as DemandSchema;
  })();
  try {
    return await cached;
  } catch (err) {
    cached = null;
    throw err;
  }
};

export const loadWorkflowSchema = async (): Promise<WorkflowSchema> => {
  if (cachedWorkflow) return cachedWorkflow;
  cachedWorkflow = (async () => {
    if (bundledWorkflowSchema) return bundledWorkflowSchema as WorkflowSchema;
    const res = await fetch("/schema/workflow.gen.json", { cache: "no-cache" });
    if (!res.ok) {
      throw new Error("Failed to load workflow.gen.json: " + res.status);
    }
    return (await res.json()) as WorkflowSchema;
  })();
  try {
    return await cachedWorkflow;
  } catch (err) {
    cachedWorkflow = null;
    throw err;
  }
};
