// Worker bootstrap for monaco-yaml.
//
// In Vite dev, some transitive deps (e.g. path-browserify) expect a Node-like `process` global.
// We polyfill the minimum needed before loading the actual monaco-yaml worker module.

import bundledDemandSchema from "../../schema/demand.gen.json";

const g = globalThis as any;

if (!g.process) {
  g.process = {
    env: {},
    cwd: () => "/"
  };
}

// The YAML language service supports `# yaml-language-server: $schema=...`.
// Those URLs are commonly repo-relative paths that aren't served by the static editor, causing noisy warnings.
// Intercept same-origin schema requests for our canonical demand schema and serve the bundled schema instead.
const schemaJsonText = JSON.stringify(bundledDemandSchema);
const originalFetch: typeof fetch | null = typeof g.fetch === "function" ? g.fetch.bind(g) : null;

const shouldServeBundledSchema = (urlRaw: string): boolean => {
  const raw = String(urlRaw || "").trim();
  if (!raw) return false;
  try {
    const base = (self as any).location?.href || "http://localhost/";
    const origin = (self as any).location?.origin || "";
    const url = new URL(raw, base);
    // Only intercept same-origin (or file://) schema URLs so we don't break custom remote schemas.
    if (url.protocol !== "file:" && origin && url.origin !== origin) return false;
    const p = url.pathname || "";
    if (p.endsWith("/schema/demand.gen.json")) return true;
    if (p.endsWith("/scalim/dsl/by_yaml/schema/demand.gen.json")) return true;
    if (p.endsWith("/demand.gen.json")) return true;
    return false;
  } catch {
    return false;
  }
};

if (originalFetch) {
  g.fetch = async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input && typeof input.url === "string" ? input.url : "";
    if (shouldServeBundledSchema(url)) {
      return new Response(schemaJsonText, {
        status: 200,
        headers: { "content-type": "application/json; charset=utf-8" }
      });
    }
    return originalFetch(input as any, init);
  };
}

const queued: any[] = [];
let bootPromise: Promise<void> | null = null;

const ensureBoot = () => {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    await import("monaco-yaml/yaml.worker");
    // Flush queued messages. `monaco-worker-manager/worker.initialize()` replaces `self.onmessage`
    // after the first message, so we must re-read the handler each iteration.
    while (queued.length) {
      const handler = self.onmessage;
      if (typeof handler !== "function") break;
      handler.call(self as any, { data: queued.shift() } as any);
    }
  })();
  return bootPromise;
};

self.onmessage = (event: MessageEvent) => {
  queued.push((event as any).data);
  void ensureBoot();
};
