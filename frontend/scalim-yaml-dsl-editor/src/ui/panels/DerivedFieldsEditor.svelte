<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { composePatchResults } from "$services/patch_compose";
  import { buildDerivedDepsGraph } from "$services/graph_model";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import { ensureEmptyMapAtPathDeep, removeKeyAtPath, setScalarAtPathDeep } from "$services/yaml_patch";
  import DirectedGraph from "$ui/components/DirectedGraph.svelte";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import { parse as parseYaml } from "yaml";

  type FieldMode = "compute" | "call_by";

  type FieldDraft = {
    fieldId: string;
    namePresent: boolean;
    nameDraft: string;
    computePresent: boolean;
    computeDraft: string;
    callByPresent: boolean;
    callByDraft: string;
    mode: FieldMode;
    deps: string[];
    unknownDeps: string[];
  };

  type Parsed = { ok: true; data: any } | { ok: false; error: string };

  const parsed = $derived((): Parsed => {
    try {
      return { ok: true as const, data: parseYaml(appState.yamlText) };
    } catch (err: any) {
      return { ok: false as const, error: String(err?.message || err || "YAML parse failed") };
    }
  });

  const depsGraph = $derived(() => {
    const p = parsed();
    if (!p.ok) return { nodes: [], edges: [] };
    return buildDerivedDepsGraph(p.data);
  });

  let demandSchema = $state<any | null>(null);
  const helpText = (path: string[]) => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, path);
  };

  let lastError = $state<string>("");
  let drafts = $state<FieldDraft[]>([]);
  let fieldsPresent = $state<boolean>(false);

  let addFieldId = $state<string>("");
  let addCompute = $state<string>("");

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
      "None"
    ]);
    const out: string[] = [];
    for (const t of tokens) {
      if (stop.has(t)) continue;
      if (out.indexOf(t) >= 0) continue;
      out.push(t);
    }
    return out;
  };

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    fieldsPresent = Object.prototype.hasOwnProperty.call(data, "fields");
    const fields = data.fields && typeof data.fields === "object" && !Array.isArray(data.fields) ? data.fields : {};

    const knownFieldIds = new Set<string>();
    const mainSource = data.main_source && typeof data.main_source === "object" ? data.main_source : {};
    const mainFields =
      mainSource.fields && typeof mainSource.fields === "object" && !Array.isArray(mainSource.fields) ? (mainSource.fields as any) : {};
    for (const k of Object.keys(mainFields)) knownFieldIds.add(String(k));

    const sources = data.sources && typeof data.sources === "object" && !Array.isArray(data.sources) ? (data.sources as any) : {};
    for (const [sid, srcCfgRaw] of Object.entries(sources)) {
      const srcCfg = srcCfgRaw && typeof srcCfgRaw === "object" && !Array.isArray(srcCfgRaw) ? (srcCfgRaw as any) : {};
      const srcFields = srcCfg.fields && typeof srcCfg.fields === "object" && !Array.isArray(srcCfg.fields) ? (srcCfg.fields as any) : {};
      void sid;
      for (const k of Object.keys(srcFields)) knownFieldIds.add(String(k));
    }

    for (const k of Object.keys(fields)) knownFieldIds.add(String(k));

    const next: FieldDraft[] = [];
    for (const [fieldIdRaw, cfgRaw] of Object.entries(fields)) {
      const fieldId = String(fieldIdRaw);
      const cfg = cfgRaw && typeof cfgRaw === "object" && !Array.isArray(cfgRaw) ? (cfgRaw as any) : {};

      const namePresent = Object.prototype.hasOwnProperty.call(cfg, "name");
      const nameDraft = typeof cfg.name === "string" ? cfg.name : "";

      const computePresent = Object.prototype.hasOwnProperty.call(cfg, "compute");
      const computeDraft = typeof cfg.compute === "string" ? cfg.compute : "";
      const callByPresent = Object.prototype.hasOwnProperty.call(cfg, "call_by");
      const callByDraft = typeof cfg.call_by === "string" ? cfg.call_by : "";

      const mode: FieldMode = callByPresent && !computePresent ? "call_by" : "compute";

      const deps = mode === "compute" ? extractDeps(computeDraft) : [];
      const unknownDeps = deps.filter((d) => !knownFieldIds.has(d));

      next.push({
        fieldId,
        namePresent,
        nameDraft,
        computePresent,
        computeDraft,
        callByPresent,
        callByDraft,
        mode,
        deps,
        unknownDeps
      });
    }

    next.sort((a, b) => a.fieldId.localeCompare(b.fieldId));
    drafts = next;
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
    const loc = lookupYamlLocation("fields", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const jumpToField = (fieldId: string) => {
    appState.activePath = "fields." + fieldId;
    const loc = lookupYamlLocation("fields." + fieldId, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const onGraphSelect = (event: CustomEvent<{ kind: "node" | "edge"; id: string; path?: string }>) => {
    const path = String(event.detail?.path || "").trim();
    if (!path) return;
    appState.activePath = path;
    const loc = lookupYamlLocation(path, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const removeField = (fieldId: string) => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["fields", fieldId], { pruneEmptyParents: true }), "Remove fields." + fieldId);
  };

  const applyName = (fieldId: string, draft: string) => {
    const raw = String(draft || "").trim();
    if (!raw) {
      applyPatch(removeKeyAtPath(appState.yamlText, ["fields", fieldId, "name"], { pruneEmptyParents: true }), "Remove name");
      return;
    }
    applyPatch(setScalarAtPathDeep(appState.yamlText, ["fields", fieldId, "name"], draft, { createMissing: true }), "Update name");
  };

  const applyCompute = (fieldId: string, draft: string) => {
    const raw = String(draft || "").trim();
    if (!raw) {
      lastError = "fields." + fieldId + ".compute is required (or use call_by)";
      return;
    }
    const out = composePatchResults(appState.yamlText, [
      (t) => removeKeyAtPath(t, ["fields", fieldId, "call_by"], { pruneEmptyParents: true }),
      (t) => setScalarAtPathDeep(t, ["fields", fieldId, "compute"], draft, { createMissing: true })
    ]);
    applyPatch(out, "Update compute");
  };

  const applyCallBy = (fieldId: string, draft: string) => {
    const raw = String(draft || "").trim();
    if (!raw) {
      lastError = "fields." + fieldId + ".call_by is required (or use compute)";
      return;
    }
    const out = composePatchResults(appState.yamlText, [
      (t) => removeKeyAtPath(t, ["fields", fieldId, "compute"], { pruneEmptyParents: true }),
      (t) => setScalarAtPathDeep(t, ["fields", fieldId, "call_by"], draft, { createMissing: true })
    ]);
    applyPatch(out, "Update call_by");
  };

  const switchMode = (fieldId: string, mode: FieldMode) => {
    if (mode === "compute") {
      const out = composePatchResults(appState.yamlText, [
        (t) => removeKeyAtPath(t, ["fields", fieldId, "call_by"], { pruneEmptyParents: true }),
        (t) => ensureEmptyMapAtPathDeep(t, ["fields", fieldId], { createMissing: true })
      ]);
      applyPatch(out, "Switch to compute");
      return;
    }
    const out = composePatchResults(appState.yamlText, [
      (t) => removeKeyAtPath(t, ["fields", fieldId, "compute"], { pruneEmptyParents: true }),
      (t) => ensureEmptyMapAtPathDeep(t, ["fields", fieldId], { createMissing: true })
    ]);
    applyPatch(out, "Switch to call_by");
  };

  const onAddField = () => {
    const id = addFieldId.trim();
    const compute = addCompute.trim();
    if (!id) return;
    if (!compute) {
      lastError = "新增 derived field 需要 compute(可后续切换到 call_by)";
      return;
    }
    const out = composePatchResults(appState.yamlText, [
      (t) => ensureEmptyMapAtPathDeep(t, ["fields"], { createMissing: true }),
      (t) => ensureEmptyMapAtPathDeep(t, ["fields", id], { createMissing: true }),
      (t) => setScalarAtPathDeep(t, ["fields", id, "compute"], compute, { createMissing: true })
    ]);
    applyPatch(out, "Add fields." + id);
    addFieldId = "";
    addCompute = "";
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
        Derived Fields
      </button>
      {#if fieldsPresent}
        <button
          type="button"
          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title="移除 fields(从 YAML 删除)"
          aria-label="remove fields"
          onclick={() => applyPatch(removeKeyAtPath(appState.yamlText, ["fields"], { pruneEmptyParents: true }), "Remove fields")}
        >
          ×
        </button>
      {/if}
      <SchemaHint text={helpText(["fields"])} label="fields" />
      <Badge variant="outline">{drafts.length}</Badge>
    </div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  {#if !parsed().ok}
    <div class="mb-3 rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">YAML 解析失败,依赖图暂不可用</div>
  {:else}
    <div class="mb-3">
      <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
        <div class="font-medium text-slate-600">依赖图</div>
        <div class="text-slate-400">点击节点/边定位</div>
      </div>
      <DirectedGraph graph={depsGraph()} selectedPath={appState.activePath} title="" on:select={onGraphSelect} />
    </div>
  {/if}

  {#if drafts.length === 0}
    <div class="rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 derived fields(可在下方添加)</div>
  {:else}
    <div class="flex flex-col gap-2">
      {#each drafts as f, idx (f.fieldId)}
        {@const fieldPath = "fields." + f.fieldId}
        {@const fieldActive = Boolean(appState.activePath && (appState.activePath === fieldPath || appState.activePath.startsWith(fieldPath + ".")))}
        <div
          class="group rounded-xl border bg-white px-3 py-2 text-xs"
          class:border-sky-300={fieldActive}
          class:ring-2={fieldActive}
          class:ring-sky-100={fieldActive}
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  class="cursor-pointer truncate font-mono text-[11px] font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                  title="点击定位到 YAML"
                  onclick={() => jumpToField(f.fieldId)}
                >
                  {f.fieldId}
                </button>
                {#if (appState.yamlLocations as any)["fields." + f.fieldId]}
                  <span class="text-[11px] text-slate-500">L{(appState.yamlLocations as any)["fields." + f.fieldId].line}</span>
                {/if}
              </div>
            </div>
            <button
              type="button"
              class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              title={"移除 fields." + f.fieldId + "(从 YAML 删除)"}
              aria-label={"remove derived field " + f.fieldId}
              onclick={() => removeField(f.fieldId)}
            >
              删除
            </button>
          </div>

          <div class="mt-2 grid grid-cols-12 gap-2">
            <div class="col-span-6">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"df-name-" + idx}>name</label>
                <div class="flex items-center gap-1">
                  {#if f.namePresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 name(从 YAML 删除)"
                      onclick={() => applyPatch(removeKeyAtPath(appState.yamlText, ["fields", f.fieldId, "name"], { pruneEmptyParents: true }), "Remove name")}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["fields", f.fieldId, "name"])} label="name" />
                </div>
              </div>
              <input
                id={"df-name-" + idx}
                class="sx-input-sm h-8 w-full"
                placeholder="显示名(可选)"
                value={f.namePresent ? f.nameDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, namePresent: true, nameDraft: v };
                }}
                onblur={() => applyName(f.fieldId, f.namePresent ? f.nameDraft : "")}
              />
            </div>

            <div class="col-span-6">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"df-mode-" + idx}>mode</label>
                <SchemaHint text={helpText(["fields", f.fieldId])} label="field" />
              </div>
              <select
                id={"df-mode-" + idx}
                class="sx-select h-8 w-full"
                value={f.mode}
                onchange={(e) => {
                  const v = (e.target as HTMLSelectElement).value === "call_by" ? "call_by" : "compute";
                  drafts[idx] = { ...f, mode: v };
                  switchMode(f.fieldId, v);
                }}
                aria-label="derived field mode"
              >
                <option value="compute">compute</option>
                <option value="call_by">call_by</option>
              </select>
            </div>
          </div>

          {#if f.mode === "compute"}
            <div class="mt-3">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <div class="flex items-center gap-2">
                  <span class="font-medium">compute</span>
                  <SchemaHint text={helpText(["fields", f.fieldId, "compute"])} label="compute" />
                </div>
              </div>
              <textarea
                class="sx-input w-full font-mono text-[11px]"
                rows="2"
                placeholder="revenue - cost"
                oninput={(e) => {
                  const v = (e.target as HTMLTextAreaElement).value;
                  drafts[idx] = { ...f, computePresent: true, computeDraft: v };
                }}
                onblur={() => applyCompute(f.fieldId, f.computePresent ? f.computeDraft : "")}
              >{f.computePresent ? f.computeDraft : ""}</textarea>
              {#if f.deps.length > 0}
                <div class="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
                  <span class="mr-1">deps:</span>
                  {#each f.deps as dep (dep)}
                    <Badge variant={f.unknownDeps.indexOf(dep) >= 0 ? "destructive" : "secondary"}>{dep}</Badge>
                  {/each}
                </div>
              {/if}
            </div>
          {:else}
            <div class="mt-3">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <div class="flex items-center gap-2">
                  <span class="font-medium">call_by</span>
                  <SchemaHint text={helpText(["fields", f.fieldId, "call_by"])} label="call_by" />
                </div>
              </div>
              <input
                class="sx-input-sm h-8 w-full font-mono"
                placeholder="myapp.module:func(x, ctx=$ctx)"
                value={f.callByPresent ? f.callByDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, callByPresent: true, callByDraft: v };
                }}
                onblur={() => applyCallBy(f.fieldId, f.callByPresent ? f.callByDraft : "")}
              />
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <div class="mt-3 rounded-xl border bg-slate-50/50 p-3 text-xs">
    <div class="mb-2 text-xs font-semibold text-slate-800">添加 derived field(compute)</div>
    <div class="grid grid-cols-12 gap-2">
      <input
        class="sx-input-sm col-span-3 font-mono"
        name="add_derived_field_id"
        placeholder="field_id(例:profit)"
        bind:value={addFieldId}
        onkeydown={(e) => {
          if ((e as KeyboardEvent).key === "Enter") onAddField();
        }}
      />
      <input class="sx-input-sm col-span-9 font-mono" placeholder="compute(例:amount - cost)" bind:value={addCompute} />
    </div>
    <div class="mt-2 flex items-center justify-end gap-2">
      <Button variant="add" size="icon" aria-label="add derived field" title="添加字段" on:click={onAddField} />
    </div>
  </div>
</section>
