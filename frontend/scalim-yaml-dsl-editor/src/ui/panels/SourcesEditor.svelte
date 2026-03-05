<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { composePatchResults } from "$services/patch_compose";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import {
    ensureEmptyMapAtPathDeep,
    removeKeyAtPath,
    setInlineValueAtPath,
    setScalarAtPathDeep
  } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import SourceFieldsEditor from "$ui/panels/SourceFieldsEditor.svelte";
  import { parse as parseYaml } from "yaml";

  type LookupCastName = "auto" | "int" | "str" | "sep_first";
  type BindKind = "none" | "use_keys" | "use_rows";
  type ParamKind = "string" | "number" | "boolean" | "null" | "complex";
  type ParamDraft = { key: string; kind: ParamKind; value: string };

  type SourceDraft = {
    sourceId: string;
    loaderDraft: string;
    keyDraft: string;
    cacheModePresent: boolean;
    cacheModeDraft: "none" | "preload_forever";

    lookupCastPresent: boolean;
    lookupCastName: LookupCastName | "";
    lookupCastSepPresent: boolean;
    lookupCastSepDraft: string;

    lookupChunkPresent: boolean;
    lookupChunkDraft: string;

    bindPresent: boolean;
    bindKind: BindKind;
    bindParamDraft: string;
    bindAsDraft: "set" | "list";
    bindCacheModeDraft: "batch" | "none";

    paramsPresent: boolean;
    paramsDrafts: ParamDraft[];
  };

  type Parsed = { ok: true; data: any } | { ok: false; error: string };

  const parsed = $derived((): Parsed => {
    try {
      return { ok: true as const, data: parseYaml(appState.yamlText) };
    } catch (err: any) {
      return { ok: false as const, error: String(err?.message || err || "YAML parse failed") };
    }
  });

  let demandSchema = $state<any | null>(null);
  const helpText = (path: string[]) => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, path);
  };

  let lastError = $state<string>("");
  let drafts = $state<SourceDraft[]>([]);
  let relationOptions = $state<string[]>([]);

  let addSourceId = $state<string>("");
  let addSourceLoader = $state<string>("");
  let addSourceKey = $state<string>("");

  let addParamDrafts = $state<Record<string, { key: string; kind: Exclude<ParamKind, "complex">; value: string }>>({});

  const ensureAddParamDraft = (sourceId: string) => {
    if (!sourceId) return { key: "", kind: "string" as const, value: "" };
    if (!addParamDrafts[sourceId]) addParamDrafts[sourceId] = { key: "", kind: "string", value: "" };
    return addParamDrafts[sourceId];
  };

  const csvToItems = (raw: string): string[] => {
    return String(raw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  };

  const itemsToInline = (items: string[]): string => {
    if (!items.length) return "";
    if (items.length === 1) return items[0] as string;
    return "[" + items.join(", ") + "]";
  };

  const parseParamKind = (value: any): ParamKind => {
    if (value == null) return "null";
    if (typeof value === "string") return "string";
    if (typeof value === "number") return "number";
    if (typeof value === "boolean") return "boolean";
    return "complex";
  };

  const stringifyParamValue = (kind: ParamKind, value: any): string => {
    if (kind === "null") return "";
    if (kind === "boolean") return value ? "true" : "false";
    if (kind === "number") return value == null ? "" : String(value);
    if (kind === "string") return value == null ? "" : String(value);
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    const sources = data.sources && typeof data.sources === "object" && !Array.isArray(data.sources) ? data.sources : {};
    const relations = data.relations && typeof data.relations === "object" && !Array.isArray(data.relations) ? data.relations : {};
    relationOptions = Object.keys(relations)
      .map((k) => String(k))
      .sort((a, b) => a.localeCompare(b));

    const next: SourceDraft[] = [];
    for (const [sidRaw, cfgRaw] of Object.entries(sources)) {
      const sourceId = String(sidRaw);
      const cfg = cfgRaw && typeof cfgRaw === "object" && !Array.isArray(cfgRaw) ? (cfgRaw as any) : {};

      const loaderDraft = typeof cfg.loader === "string" ? cfg.loader : "";
      const keyDraft = Array.isArray(cfg.key) ? cfg.key.map((x: any) => String(x)).join(", ") : typeof cfg.key === "string" ? cfg.key : "";

      const cacheModePresent = Object.prototype.hasOwnProperty.call(cfg, "cache_mode");
      const cacheModeDraft: "none" | "preload_forever" = cfg.cache_mode === "preload_forever" ? "preload_forever" : "none";

      const lookupCastPresent = Object.prototype.hasOwnProperty.call(cfg, "lookup_cast");
      const lc = cfg.lookup_cast && typeof cfg.lookup_cast === "object" ? (cfg.lookup_cast as any) : {};
      const lookupCastName: LookupCastName | "" =
        lc.name === "auto" || lc.name === "int" || lc.name === "str" || lc.name === "sep_first" ? lc.name : "";
      const lookupCastSepPresent = Object.prototype.hasOwnProperty.call(lc, "sep");
      const lookupCastSepDraft = typeof lc.sep === "string" ? lc.sep : "";

      const lookupChunkPresent = Object.prototype.hasOwnProperty.call(cfg, "lookup_chunk_size");
      const lookupChunkDraft = cfg.lookup_chunk_size == null ? "" : String(cfg.lookup_chunk_size);

      const bindPresent = Object.prototype.hasOwnProperty.call(cfg, "bind");
      const bind = cfg.bind && typeof cfg.bind === "object" ? (cfg.bind as any) : {};
      let bindKind: BindKind = "none";
      let bindParamDraft = "";
      let bindAsDraft: "set" | "list" = "set";
      let bindCacheModeDraft: "batch" | "none" = "batch";
      if (bind.use_keys && typeof bind.use_keys === "object") {
        bindKind = "use_keys";
        bindParamDraft = typeof bind.use_keys.param === "string" ? bind.use_keys.param : "";
        bindAsDraft = bind.use_keys.as === "list" ? "list" : "set";
      } else if (bind.use_rows && typeof bind.use_rows === "object") {
        bindKind = "use_rows";
        bindParamDraft = typeof bind.use_rows.param === "string" ? bind.use_rows.param : "";
        bindCacheModeDraft = bind.use_rows.cache_mode === "none" ? "none" : "batch";
      }

      const paramsPresent = Object.prototype.hasOwnProperty.call(cfg, "params");
      const params = cfg.params && typeof cfg.params === "object" && !Array.isArray(cfg.params) ? (cfg.params as any) : {};
      const paramsDrafts: ParamDraft[] = [];
      for (const [k, v] of Object.entries(params)) {
        const kind = parseParamKind(v);
        paramsDrafts.push({ key: String(k), kind, value: stringifyParamValue(kind, v) });
      }
      paramsDrafts.sort((a, b) => a.key.localeCompare(b.key));

      next.push({
        sourceId,
        loaderDraft,
        keyDraft,
        cacheModePresent,
        cacheModeDraft,
        lookupCastPresent,
        lookupCastName,
        lookupCastSepPresent,
        lookupCastSepDraft,
        lookupChunkPresent,
        lookupChunkDraft,
        bindPresent,
        bindKind,
        bindParamDraft,
        bindAsDraft,
        bindCacheModeDraft,
        paramsPresent,
        paramsDrafts
      });
    }

    next.sort((a, b) => a.sourceId.localeCompare(b.sourceId));
    drafts = next;
    for (const s of next) ensureAddParamDraft(s.sourceId);
  };

  $effect(() => {
    appState.yamlText;
    lastError = "";
    syncDrafts();
  });

  const applyPatch = (out: any, title: string) => {
    const res = applyPatchResult(out, { title });
    lastError = res.ok ? "" : res.error;
  };

  const requestJump = () => {
    const loc = lookupYamlLocation("sources", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const jumpToSource = (sourceId: string) => {
    const loc = lookupYamlLocation("sources." + sourceId, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const removeSource = (sourceId: string) => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId], { pruneEmptyParents: true }), "Remove sources." + sourceId);
  };

  const applyKey = (sourceId: string, rawDraft: string) => {
    const inline = itemsToInline(csvToItems(rawDraft));
    if (!inline) {
      lastError = "sources." + sourceId + ".key is required";
      return;
    }
    applyPatch(setInlineValueAtPath(appState.yamlText, ["sources", sourceId, "key"], inline, { createMissing: true }), "Update sources." + sourceId + ".key");
  };

  const applyCacheMode = (sourceId: string, value: string) => {
    const v: "none" | "preload_forever" = value === "preload_forever" ? "preload_forever" : "none";
    if (v === "none") {
      applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId, "cache_mode"], { pruneEmptyParents: true }), "Remove cache_mode");
      return;
    }
    applyPatch(setScalarAtPathDeep(appState.yamlText, ["sources", sourceId, "cache_mode"], v, { createMissing: true }), "Update cache_mode");
  };

  const applyLookupCast = (sourceId: string, name: string, sepDraft: string) => {
    const cleaned = String(name || "").trim();
    if (!cleaned) {
      applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId, "lookup_cast"], { pruneEmptyParents: true }), "Remove lookup_cast");
      return;
    }
    const lcName: LookupCastName | "" =
      cleaned === "auto" || cleaned === "int" || cleaned === "str" || cleaned === "sep_first" ? (cleaned as LookupCastName) : "";
    if (!lcName) return;
    const needsSep = lcName === "sep_first";
    const out = composePatchResults(appState.yamlText, [
      (t) => ensureEmptyMapAtPathDeep(t, ["sources", sourceId, "lookup_cast"], { createMissing: true }),
      (t) => setScalarAtPathDeep(t, ["sources", sourceId, "lookup_cast", "name"], lcName, { createMissing: true }),
      (t) => {
        if (!needsSep) return removeKeyAtPath(t, ["sources", sourceId, "lookup_cast", "sep"], { pruneEmptyParents: true });
        const sep = String(sepDraft || "").trim() || ",";
        return setScalarAtPathDeep(t, ["sources", sourceId, "lookup_cast", "sep"], sep, { createMissing: true });
      }
    ]);
    applyPatch(out, "Update lookup_cast");
  };

  const applyLookupChunkSize = (sourceId: string, rawDraft: string) => {
    const raw = String(rawDraft || "").trim();
    if (!raw) {
      applyPatch(
        removeKeyAtPath(appState.yamlText, ["sources", sourceId, "lookup_chunk_size"], { pruneEmptyParents: true }),
        "Remove lookup_chunk_size"
      );
      return;
    }
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) {
      lastError = "lookup_chunk_size must be a non-negative integer (or blank to remove)";
      return;
    }
    applyPatch(
      setScalarAtPathDeep(appState.yamlText, ["sources", sourceId, "lookup_chunk_size"], Math.floor(n), { createMissing: true }),
      "Update lookup_chunk_size"
    );
  };

  const applyBind = (sourceId: string, kind: BindKind, paramDraft: string, asDraft: string, cacheModeDraft: string) => {
    const cleanedKind: BindKind = kind === "use_keys" || kind === "use_rows" ? kind : "none";

    if (cleanedKind === "none") {
      applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId, "bind"], { pruneEmptyParents: true }), "Remove bind");
      return;
    }

    const cleanedParam = String(paramDraft || "").trim();
    if (!cleanedParam) {
      lastError = "bind.param is required";
      return;
    }

    const basePath = ["sources", sourceId, "bind"];
    const out = composePatchResults(appState.yamlText, [
      (t) => removeKeyAtPath(t, basePath, { pruneEmptyParents: true }),
      (t) =>
        ensureEmptyMapAtPathDeep(t, cleanedKind === "use_keys" ? basePath.concat(["use_keys"]) : basePath.concat(["use_rows"]), {
          createMissing: true
        }),
      (t) =>
        setScalarAtPathDeep(
          t,
          cleanedKind === "use_keys" ? basePath.concat(["use_keys", "param"]) : basePath.concat(["use_rows", "param"]),
          cleanedParam,
          { createMissing: true }
        ),
      (t) => {
        if (cleanedKind === "use_keys") {
          const asValue = asDraft === "list" ? "list" : "set";
          if (asValue === "set") return removeKeyAtPath(t, basePath.concat(["use_keys", "as"]), { pruneEmptyParents: true });
          return setScalarAtPathDeep(t, basePath.concat(["use_keys", "as"]), asValue, { createMissing: true });
        }
        const cmValue = cacheModeDraft === "none" ? "none" : "batch";
        if (cmValue === "batch") return removeKeyAtPath(t, basePath.concat(["use_rows", "cache_mode"]), { pruneEmptyParents: true });
        return setScalarAtPathDeep(t, basePath.concat(["use_rows", "cache_mode"]), cmValue, { createMissing: true });
      }
    ]);
    applyPatch(out, "Update bind");
  };

  const applyParamScalar = (sourceId: string, key: string, kind: Exclude<ParamKind, "complex">, draftValue: string) => {
    const cleanedKey = String(key || "").trim();
    if (!cleanedKey) {
      lastError = "params key is required";
      return;
    }

    const path = ["sources", sourceId, "params", cleanedKey];

    if (kind === "null") {
      applyPatch(setScalarAtPathDeep(appState.yamlText, path, null, { createMissing: true }), "Set param");
      return;
    }
    if (kind === "boolean") {
      const raw = String(draftValue || "").trim().toLowerCase();
      const v = raw === "false" ? false : true;
      applyPatch(setScalarAtPathDeep(appState.yamlText, path, v, { createMissing: true }), "Set param");
      return;
    }
    if (kind === "number") {
      const raw = String(draftValue || "").trim();
      const n = Number(raw);
      if (!raw || !Number.isFinite(n)) {
        lastError = "params." + cleanedKey + " must be a number";
        return;
      }
      applyPatch(setScalarAtPathDeep(appState.yamlText, path, n, { createMissing: true }), "Set param");
      return;
    }
    applyPatch(setScalarAtPathDeep(appState.yamlText, path, String(draftValue || ""), { createMissing: true }), "Set param");
  };

  const removeParam = (sourceId: string, key: string) => {
    const cleanedKey = String(key || "").trim();
    if (!cleanedKey) return;
    applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId, "params", cleanedKey], { pruneEmptyParents: true }), "Remove param");
  };

  const onAddParam = (sourceId: string) => {
    const draft = ensureAddParamDraft(sourceId);
    const key = String(draft.key || "").trim();
    if (!key) return;
    applyParamScalar(sourceId, key, draft.kind, draft.value);
    addParamDrafts[sourceId] = { key: "", kind: "string", value: "" };
  };

  const onAddSource = () => {
    const sid = addSourceId.trim();
    if (!sid) return;
    const loader = addSourceLoader.trim();
    const keyInline = itemsToInline(csvToItems(addSourceKey));
    if (!loader || !keyInline) {
      lastError = "Add source requires source_id / loader / key";
      return;
    }

    const out = composePatchResults(appState.yamlText, [
      (t) => ensureEmptyMapAtPathDeep(t, ["sources"], { createMissing: true }),
      (t) => ensureEmptyMapAtPathDeep(t, ["sources", sid], { createMissing: true }),
      (t) => setScalarAtPathDeep(t, ["sources", sid, "loader"], loader, { createMissing: true }),
      (t) => setInlineValueAtPath(t, ["sources", sid, "key"], keyInline, { createMissing: true })
    ]);
    applyPatch(out, "Add sources." + sid);

    addSourceId = "";
    addSourceLoader = "";
    addSourceKey = "";
  };

  onMount(async () => {
    try {
      demandSchema = await loadDemandSchema();
    } catch {
      demandSchema = null;
    }
  });
</script>

<section class="rounded-xl border bg-white p-3">
  <div class="mb-2 flex items-center">
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="cursor-pointer text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
        title="点击定位到 YAML"
        onclick={requestJump}
      >
        Sources
      </button>
      <SchemaHint text={helpText(["sources"])} label="sources" />
      <Badge variant="outline">{drafts.length}</Badge>
    </div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  {#if drafts.length === 0}
    <div class="mb-3 rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 sources(可在下方添加)</div>
  {:else}
    <div class="flex flex-col gap-3">
      {#each drafts as s, idx (s.sourceId)}
        {@const addParam = ensureAddParamDraft(s.sourceId)}
        <details class="rounded-xl border bg-white" open>
          <summary class="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2">
            <div class="min-w-0 flex items-center gap-2">
              <button
                type="button"
                class="truncate font-mono text-[11px] font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                title="点击定位到 YAML"
                onclick={(e) => {
                  e.preventDefault();
                  jumpToSource(s.sourceId);
                }}
              >
                {s.sourceId}
              </button>
              {#if (appState.yamlLocations as any)["sources." + s.sourceId]}
                <span class="text-[11px] text-slate-500">L{(appState.yamlLocations as any)["sources." + s.sourceId].line}</span>
              {/if}
              {#if s.cacheModeDraft === "preload_forever"}
                <Badge variant="secondary">cache: preload_forever</Badge>
              {/if}
            </div>
            <button
              type="button"
              class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              title={"移除 sources." + s.sourceId + "(从 YAML 删除)"}
              aria-label={"remove source " + s.sourceId}
              onclick={(e) => {
                e.preventDefault();
                removeSource(s.sourceId);
              }}
            >
              删除
            </button>
          </summary>

          <div class="border-t bg-slate-50/40 p-3">
            <div class="grid grid-cols-12 gap-2">
              <div class="col-span-6">
                <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                  <label class="font-medium" for={"src-loader-" + idx}>loader</label>
                  <SchemaHint text={helpText(["sources", s.sourceId, "loader"])} label="loader" />
                </div>
                <input
                  id={"src-loader-" + idx}
                  class="sx-input-sm w-full"
                  value={s.loaderDraft}
                  oninput={(e) => {
                    const v = (e.target as HTMLInputElement).value;
                    drafts[idx] = { ...s, loaderDraft: v };
                  }}
                  onblur={() =>
                    applyPatch(
                      setScalarAtPathDeep(appState.yamlText, ["sources", s.sourceId, "loader"], s.loaderDraft, { createMissing: true }),
                      "Update loader"
                    )}
                />
              </div>

              <div class="col-span-6">
                <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                  <label class="font-medium" for={"src-key-" + idx}>key</label>
                  <SchemaHint text={helpText(["sources", s.sourceId, "key"])} label="key" />
                </div>
                <input
                  id={"src-key-" + idx}
                  class="sx-input-sm w-full font-mono"
                  placeholder="customer_id 或 region_id, institution_id"
                  value={s.keyDraft}
                  oninput={(e) => {
                    const v = (e.target as HTMLInputElement).value;
                    drafts[idx] = { ...s, keyDraft: v };
                  }}
                  onblur={() => applyKey(s.sourceId, s.keyDraft)}
                />
              </div>
            </div>

            <div class="mt-3 grid grid-cols-12 gap-2">
              <div class="col-span-4">
                <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">cache_mode</span>
                    <SchemaHint text={helpText(["sources", s.sourceId, "cache_mode"])} label="cache_mode" />
                  </div>
                  {#if s.cacheModePresent}
                    <button
                      type="button"
                      class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 cache_mode(恢复默认 none)"
                      onclick={() => applyCacheMode(s.sourceId, "none")}
                    >
                      ×
                    </button>
                  {/if}
                </div>
                <select
                  class="sx-select h-8 w-full"
                  value={s.cacheModeDraft}
                  onchange={(e) => {
                    const v = (e.target as HTMLSelectElement).value;
                    drafts[idx] = { ...s, cacheModePresent: v !== "none", cacheModeDraft: v as any };
                    applyCacheMode(s.sourceId, v);
                  }}
                  aria-label="cache_mode"
                >
                  <option value="none">none</option>
                  <option value="preload_forever">preload_forever</option>
                </select>
              </div>

              <div class="col-span-4">
                <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">lookup_cast</span>
                    <SchemaHint text={helpText(["sources", s.sourceId, "lookup_cast"])} label="lookup_cast" />
                  </div>
                  {#if s.lookupCastPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 lookup_cast(从 YAML 删除)"
                      onclick={() => applyLookupCast(s.sourceId, "", "")}
                    >
                      ×
                    </button>
                  {/if}
                </div>
                <div class="flex items-center gap-2">
                  <select
                    class="sx-select h-8 flex-1"
                    value={s.lookupCastName || ""}
                    onchange={(e) => {
                      const v = (e.target as HTMLSelectElement).value;
                      drafts[idx] = { ...s, lookupCastPresent: Boolean(v), lookupCastName: v as any };
                      applyLookupCast(s.sourceId, v, s.lookupCastSepDraft);
                    }}
                    aria-label="lookup_cast name"
                  >
                    <option value="">(none)</option>
                    <option value="auto">auto</option>
                    <option value="int">int</option>
                    <option value="str">str</option>
                    <option value="sep_first">sep_first</option>
                  </select>
                  {#if s.lookupCastName === "sep_first"}
                    <input
                      class="sx-input-sm w-[110px] font-mono"
                      placeholder="sep"
                      value={s.lookupCastSepDraft}
                      oninput={(e) => {
                        const v = (e.target as HTMLInputElement).value;
                        drafts[idx] = { ...s, lookupCastSepDraft: v };
                      }}
                      onblur={() => applyLookupCast(s.sourceId, s.lookupCastName, s.lookupCastSepDraft)}
                    />
                  {/if}
                </div>
              </div>

              <div class="col-span-4">
                <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">lookup_chunk_size</span>
                    <SchemaHint text={helpText(["sources", s.sourceId, "lookup_chunk_size"])} label="lookup_chunk_size" />
                  </div>
                  {#if s.lookupChunkPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 lookup_chunk_size(从 YAML 删除)"
                      onclick={() => applyLookupChunkSize(s.sourceId, "")}
                    >
                      ×
                    </button>
                  {/if}
                </div>
                <input
                  class="sx-input-sm w-full"
                  inputmode="numeric"
                  placeholder="0 / null / 空 表示不分片"
                  value={s.lookupChunkDraft}
                  oninput={(e) => {
                    const v = (e.target as HTMLInputElement).value;
                    drafts[idx] = { ...s, lookupChunkPresent: Boolean(v.trim()), lookupChunkDraft: v };
                  }}
                  onblur={() => applyLookupChunkSize(s.sourceId, s.lookupChunkDraft)}
                />
              </div>
            </div>

            <div class="mt-3 rounded-lg border bg-white p-3 text-xs">
              <div class="mb-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <div class="flex items-center gap-2">
                  <span class="font-medium">bind</span>
                  <SchemaHint text={helpText(["sources", s.sourceId, "bind"])} label="bind" />
                </div>
                {#if s.bindPresent}
                  <button
                    type="button"
                    class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                    title="移除 bind(从 YAML 删除)"
                    onclick={() => applyBind(s.sourceId, "none", "", "set", "batch")}
                  >
                    ×
                  </button>
                {/if}
              </div>

              <div class="flex items-center gap-2">
                <select
                  class="sx-select h-8 w-[120px]"
                  value={s.bindKind}
                  onchange={(e) => {
                    const v = (e.target as HTMLSelectElement).value as any;
                    const kind: BindKind = v === "use_keys" || v === "use_rows" ? v : "none";
                    drafts[idx] = { ...s, bindPresent: kind !== "none", bindKind: kind };
                    applyBind(s.sourceId, kind, s.bindParamDraft, s.bindAsDraft, s.bindCacheModeDraft);
                  }}
                  aria-label="bind kind"
                >
                  <option value="none">(none)</option>
                  <option value="use_keys">use_keys</option>
                  <option value="use_rows">use_rows</option>
                </select>
                <input
                  class="sx-input-sm flex-1 font-mono"
                  placeholder="param(必填)"
                  value={s.bindParamDraft}
                  oninput={(e) => {
                    const v = (e.target as HTMLInputElement).value;
                    drafts[idx] = { ...s, bindParamDraft: v };
                  }}
                  onblur={() => applyBind(s.sourceId, s.bindKind, s.bindParamDraft, s.bindAsDraft, s.bindCacheModeDraft)}
                />
                {#if s.bindKind === "use_keys"}
                  <select
                    class="sx-select h-8 w-[92px]"
                    value={s.bindAsDraft}
                    onchange={(e) => {
                      const v = (e.target as HTMLSelectElement).value as any;
                      drafts[idx] = { ...s, bindAsDraft: v === "list" ? "list" : "set" };
                      applyBind(s.sourceId, s.bindKind, s.bindParamDraft, drafts[idx].bindAsDraft, s.bindCacheModeDraft);
                    }}
                    aria-label="bind as"
                  >
                    <option value="set">set</option>
                    <option value="list">list</option>
                  </select>
                {:else if s.bindKind === "use_rows"}
                  <select
                    class="sx-select h-8 w-[110px]"
                    value={s.bindCacheModeDraft}
                    onchange={(e) => {
                      const v = (e.target as HTMLSelectElement).value as any;
                      drafts[idx] = { ...s, bindCacheModeDraft: v === "none" ? "none" : "batch" };
                      applyBind(s.sourceId, s.bindKind, s.bindParamDraft, s.bindAsDraft, drafts[idx].bindCacheModeDraft);
                    }}
                    aria-label="bind cache_mode"
                  >
                    <option value="batch">cache: batch</option>
                    <option value="none">cache: none</option>
                  </select>
                {/if}
              </div>
            </div>

            <div class="mt-3 rounded-xl border bg-white p-3 text-xs">
              <div class="mb-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <div class="flex items-center gap-2">
                  <span class="font-medium">params</span>
                  <SchemaHint text={helpText(["sources", s.sourceId, "params"])} label="params" />
                </div>
                {#if s.paramsPresent}
                  <button
                    type="button"
                    class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                    title="移除 params(从 YAML 删除)"
                    onclick={() => applyPatch(removeKeyAtPath(appState.yamlText, ["sources", s.sourceId, "params"], { pruneEmptyParents: true }), "Remove params")}
                  >
                    ×
                  </button>
                {/if}
              </div>

              {#if s.paramsDrafts.length === 0}
                <div class="mb-2 rounded-md border bg-slate-50 px-2 py-2 text-[11px] text-slate-600">暂无 params(可在下方添加)</div>
              {:else}
                <div class="mb-2 flex flex-col gap-1">
                  {#each s.paramsDrafts as p (p.key)}
                    <div class="group flex items-start gap-2 rounded-md border bg-white px-2 py-2 text-xs">
                      <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-2">
                          <span class="truncate font-mono text-[11px] text-slate-700">{p.key}</span>
                          <span class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">{p.kind}</span>
                        </div>

                        {#if p.kind === "complex"}
                          <div class="mt-1 rounded-md border bg-slate-50 px-2 py-1 font-mono text-[11px] text-slate-600">
                            复杂值暂不支持可视化编辑,请在 YAML 中修改
                          </div>
                          <div class="mt-1 truncate font-mono text-[11px] text-slate-500">{p.value}</div>
                        {:else if p.kind === "boolean"}
                          <select
                            class="sx-select mt-1 h-8 w-full"
                            aria-label={"params." + p.key}
                            value={p.value.trim().toLowerCase() === "false" ? "false" : "true"}
                            onchange={(e) => {
                              const v = (e.target as HTMLSelectElement).value;
                              applyParamScalar(s.sourceId, p.key, "boolean", v);
                            }}
                          >
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        {:else}
                          <input
                            class="sx-input-sm mt-1 w-full font-mono"
                            placeholder={p.kind === "number" ? "number" : p.kind === "null" ? "(null)" : "string"}
                            value={p.value}
                            disabled={p.kind === "null"}
                            onblur={(e) => {
                              const v = (e.target as HTMLInputElement).value;
                              applyParamScalar(s.sourceId, p.key, p.kind as any, v);
                            }}
                          />
                        {/if}
                      </div>

                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title={"移除 params." + p.key + "(从 YAML 删除)"}
                        aria-label={"remove param " + p.key}
                        onclick={() => removeParam(s.sourceId, p.key)}
                      >
                        ×
                      </button>
                    </div>
                  {/each}
                </div>
              {/if}

              <div class="grid grid-cols-12 gap-2">
                <input class="sx-input-sm col-span-4 font-mono" placeholder="key(例:since_days)" bind:value={addParam.key} />
                <select class="sx-select col-span-3" bind:value={addParam.kind} aria-label="add param kind">
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="boolean">boolean</option>
                  <option value="null">null</option>
                </select>
                <input class="sx-input-sm col-span-3 font-mono" placeholder="value" bind:value={addParam.value} />
                <Button
                  variant="add"
                  size="icon"
                  className="col-span-2 justify-self-end"
                  aria-label={"add param for " + s.sourceId}
                  title="添加参数"
                  on:click={() => onAddParam(s.sourceId)}
                />
              </div>
            </div>

            <div class="mt-3">
              <SourceFieldsEditor sourceId={s.sourceId} relationOptions={relationOptions} />
            </div>
          </div>
        </details>
      {/each}
    </div>
  {/if}

  <div class="mt-4 rounded-xl border bg-slate-50/50 p-3">
    <div class="mb-2 text-xs font-semibold text-slate-800">添加 source</div>
    <div class="grid grid-cols-12 gap-2">
      <input
        class="sx-input-sm col-span-3 font-mono"
        name="add_source_id"
        placeholder="source_id(例:customers)"
        bind:value={addSourceId}
        onkeydown={(e) => {
          if ((e as KeyboardEvent).key === "Enter") onAddSource();
        }}
      />
      <input class="sx-input-sm col-span-6" placeholder="loader(例:myapp.loaders:load_customers)" bind:value={addSourceLoader} />
      <input class="sx-input-sm col-span-3 font-mono" placeholder="key(例:customer_id)" bind:value={addSourceKey} />
    </div>
    <div class="mt-2 flex items-center justify-between gap-2">
      <div class="text-[11px] text-slate-500">支持复合键:`region_id, institution_id` → `[region_id, institution_id]`</div>
      <Button variant="add" size="icon" aria-label="add source" title="添加 source" on:click={onAddSource} />
    </div>
  </div>
</section>

<style>
  summary {
    list-style: none;
  }
  summary::-webkit-details-marker {
    display: none;
  }
</style>
