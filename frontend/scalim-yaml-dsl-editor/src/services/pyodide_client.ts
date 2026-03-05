import type { Issue } from "$domain/issues";

import PyodideValidateWorker from "./pyodide_validate.worker?worker";

export type PyodideValidateResult = { ok: true; issues: Issue[] } | { ok: false; error: string };

type WorkerValidateRequest = {
  type: "validate";
  id: number;
  yamlText: string;
  strict: boolean;
};

type WorkerValidateResponse =
  | { type: "validate_result"; id: number; ok: true; issues: Issue[] }
  | { type: "validate_result"; id: number; ok: false; error: string };

type Pending = {
  resolve: (value: PyodideValidateResult) => void;
};

let worker: Worker | null = null;
let seq = 0;
const pending = new Map<number, Pending>();

const failAll = (error: string) => {
  const msg: PyodideValidateResult = { ok: false, error: String(error || "pyodide validate failed") };
  for (const item of pending.values()) item.resolve(msg);
  pending.clear();
};

const resetWorker = (reason: string) => {
  try {
    worker?.terminate();
  } catch {
    // ignore
  }
  worker = null;
  failAll(reason);
};

const ensureWorker = (): Worker => {
  if (worker) return worker;
  const w = new PyodideValidateWorker();

  w.onmessage = (event: MessageEvent) => {
    const data = event.data as WorkerValidateResponse;
    if (!data || data.type !== "validate_result") return;
    const item = pending.get(data.id);
    if (!item) return;
    pending.delete(data.id);
    if (data.ok) item.resolve({ ok: true, issues: data.issues || [] });
    else item.resolve({ ok: false, error: String(data.error || "pyodide validate failed") });
  };

  w.onerror = () => {
    resetWorker("pyodide worker crashed");
  };

  w.onmessageerror = () => {
    resetWorker("pyodide worker message error");
  };

  worker = w;
  return w;
};

export const pyodideValidate = async (
  yamlText: string,
  opts?: { strict?: boolean; timeoutMs?: number }
): Promise<PyodideValidateResult> => {
  const w = ensureWorker();
  const id = (seq += 1);
  const strict = Boolean(opts?.strict);
  const timeoutMs = Math.max(200, Number(opts?.timeoutMs) || 0);

  const result = await new Promise<PyodideValidateResult>((resolve) => {
    pending.set(id, { resolve });
    const req: WorkerValidateRequest = { type: "validate", id, yamlText: String(yamlText || ""), strict };
    w.postMessage(req);

    if (!timeoutMs) return;

    window.setTimeout(() => {
      if (!pending.has(id)) return;
      pending.delete(id);
      resetWorker("pyodide validate timeout");
      resolve({ ok: false, error: "pyodide validate timeout" });
    }, timeoutMs);
  });

  return result;
};

