import bundledDemandSchema from "../schema/demand.gen.json";

export type DemandSchema = Record<string, any>;

// Prefer bundling schema at build time so the editor works without any network fetches.
// (Fetching `/schema/demand.gen.json` can fail under `file://` or restrictive hosting setups.)
// Keep the runtime fetch as a fallback for advanced deployments.

let cached: Promise<DemandSchema> | null = null;

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
