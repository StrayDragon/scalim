import bundledDemandSchema from "../schema/demand.gen.json";
import { DIST_NAME, IMPORT_ROOT } from "../generated/project_constants";
import type { Issue } from "$domain/issues";

type ValidateRequest = {
  type: "validate";
  id: number;
  yamlText: string;
  strict: boolean;
};

type ValidateResponse =
  | { type: "validate_result"; id: number; ok: true; issues: Issue[] }
  | { type: "validate_result"; id: number; ok: false; error: string };

type PyodideIssue = {
  path?: string;
  message?: string;
  suggestions?: string[];
  line?: number;
  column?: number;
};

type PyodidePayload = {
  ok: boolean;
  errors?: PyodideIssue[];
  warnings?: PyodideIssue[];
};

const normalizeBasePath = (basePathRaw: string): string => {
  const basePath = String(basePathRaw || "/").trim() || "/";
  return basePath.endsWith("/") ? basePath : basePath + "/";
};

const basePath = normalizeBasePath((import.meta as any).env?.BASE_URL);
const originRaw = (self as any).location?.origin;
const origin = originRaw && originRaw !== "null" ? originRaw : "";

const loadScalimWheelUrl = async (): Promise<string> => {
  const manifestName = `${DIST_NAME}-wheel.json`;
  const manifestUrl = origin ? new URL(basePath + manifestName, origin).toString() : basePath + manifestName;
  const res = await fetch(manifestUrl, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Failed to load ${manifestName} (run build_scalim_wheel.sh): ${res.status}`);
  const data = (await res.json()) as any;
  const fileName = String(data?.fileName || "").trim();
  if (!fileName) throw new Error(`Invalid ${manifestName}: missing fileName (run build_scalim_wheel.sh)`);
  return origin ? new URL(basePath + "wheels/" + fileName, origin).toString() : basePath + "wheels/" + fileName;
};

const normalizeIndexUrl = (urlRaw: string): string => {
  const url = String(urlRaw || "").trim();
  if (!url) return "";
  return url.endsWith("/") ? url : url + "/";
};

const resolveIndexUrl = (urlRaw: string): string => {
  const url = normalizeIndexUrl(urlRaw);
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;

  if (url.startsWith("/")) return origin ? new URL(url, origin).toString() : url;

  const joined = basePath + url;
  return origin ? new URL(joined, origin).toString() : joined;
};

const DEFAULT_PYODIDE_CDN_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v0.25.1/full/";

const localPyodideIndexUrl = origin ? new URL(basePath + "pyodide/", origin).toString() : basePath + "pyodide/";
const cdnPyodideIndexUrl = DEFAULT_PYODIDE_CDN_INDEX_URL;

const envPyodideIndexUrlRaw = String((import.meta as any).env?.VITE_PYODIDE_INDEX_URL || "").trim();
const envPyodideIndexUrl = envPyodideIndexUrlRaw ? resolveIndexUrl(envPyodideIndexUrlRaw) : "";
const pyodideCandidates = envPyodideIndexUrl ? [envPyodideIndexUrl] : [localPyodideIndexUrl, cdnPyodideIndexUrl];

let pyodide: any | null = null;
let validateFn: any | null = null;
let initPromise: Promise<void> | null = null;

const ensurePyodide = async (): Promise<void> => {
  if (pyodide && validateFn) return;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    let lastErr: any = null;

    for (const indexURL of pyodideCandidates) {
      const moduleUrl = indexURL + "pyodide.mjs";
      try {
        const mod = await import(/* @vite-ignore */ moduleUrl);
        const loadPyodide = (mod as any).loadPyodide;
        if (typeof loadPyodide !== "function") throw new Error("pyodide loadPyodide missing");

        const instance = await loadPyodide({ indexURL });
        await instance.loadPackage(["micropip", "pyyaml"]);

        instance.FS.mkdirTree("/schema");
        instance.FS.writeFile("/schema/demand.gen.json", JSON.stringify(bundledDemandSchema));

        const wheelUrl = await loadScalimWheelUrl();
        instance.globals.set("_SCALIM_WHEEL_URL", wheelUrl);
        await instance.runPythonAsync(`
import micropip
await micropip.install(str(_SCALIM_WHEEL_URL), deps=False)
`);

        await instance.runPythonAsync(`
from ${IMPORT_ROOT}.dsl.by_yaml.config_parsing.validator import validate_yaml_text_json
`);

        const fn = instance.globals.get("validate_yaml_text_json");
        if (!fn) throw new Error("validate_yaml_text_json not found");

        pyodide = instance;
        validateFn = fn;
        return;
      } catch (err: any) {
        lastErr = err;
      }
    }

    const attempted = pyodideCandidates.join(", ");
    const suffix = lastErr?.message ? " (" + lastErr.message + ")" : "";
    throw new Error(
      "Failed to load Pyodide from: " +
        attempted +
        suffix +
        ". If CDN is blocked, run prepare_pyodide.sh to serve local assets at " +
        localPyodideIndexUrl
    );
  })();

  try {
    await initPromise;
  } catch (err) {
    initPromise = null;
    pyodide = null;
    try {
      validateFn?.destroy?.();
    } catch {
      // ignore
    }
    validateFn = null;
    throw err;
  }
};

const toIssue = (severity: "error" | "warning", item: PyodideIssue): Issue => {
  return {
    severity,
    source: "semantic",
    message: String(item.message || ""),
    path: item.path ? String(item.path) : undefined,
    suggestions: Array.isArray(item.suggestions) ? item.suggestions.map((s) => String(s)) : undefined,
    line: typeof item.line === "number" ? item.line : undefined,
    column: typeof item.column === "number" ? item.column : undefined
  };
};

let latestValidateId = 0;

self.addEventListener("message", async (event: MessageEvent) => {
  const msg = event.data as ValidateRequest;
  if (!msg || msg.type !== "validate") return;

  const id = Number(msg.id) || 0;
  latestValidateId = id;

  try {
    await ensurePyodide();
    if (id !== latestValidateId) {
      const res: ValidateResponse = { type: "validate_result", id, ok: true, issues: [] };
      self.postMessage(res);
      return;
    }

    const yamlText = String(msg.yamlText || "");
    const strict = Boolean(msg.strict);

    const raw = String(validateFn(yamlText, strict, "/schema/demand.gen.json") || "");
    const parsed = (raw ? (JSON.parse(raw) as PyodidePayload) : { ok: false }) as PyodidePayload;

    const issues: Issue[] = [];
    for (const item of parsed.errors || []) issues.push(toIssue("error", item));
    for (const item of parsed.warnings || []) issues.push(toIssue("warning", item));

    const res: ValidateResponse = { type: "validate_result", id, ok: true, issues };
    self.postMessage(res);
  } catch (err: any) {
    const res: ValidateResponse = {
      type: "validate_result",
      id,
      ok: false,
      error: String(err?.message || err || "pyodide validate failed")
    };
    self.postMessage(res);
  }
});
