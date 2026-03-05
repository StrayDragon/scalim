<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { composePatchResults } from "$services/patch_compose";
  import { buildRelationsGraph } from "$services/graph_model";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import {
    appendAnchoredBlockEntryAtPath,
    ensureEmptyMapAtPathDeep,
    insertInlineItemAtPath,
    removeKeyAtPath,
    removeSeqItemAtPath,
    setInlineValueAtPath,
    setScalarAtPathDeep
  } from "$services/yaml_patch";
  import DirectedGraph from "$ui/components/DirectedGraph.svelte";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import { parse as parseYaml } from "yaml";

  type LookupCastName = "auto" | "int" | "str" | "sep_first";
  type BindKind = "none" | "use_keys" | "use_rows";

  type StepDraft = {
    idx: number;
    fromDraft: string;
    toDraft: string;

    lookupCastPresent: boolean;
    lookupCastName: LookupCastName | "";
    lookupCastSepPresent: boolean;
    lookupCastSepDraft: string;

    toBindPresent: boolean;
    toBindKind: BindKind;
    toBindParamDraft: string;
    toBindAsDraft: "set" | "list";
    toBindCacheModeDraft: "batch" | "none";
  };

  type RelationDraft = {
    relationId: string;
    steps: StepDraft[];
  };

  type Parsed = { ok: true; data: any } | { ok: false; error: string };

  const parsed = $derived((): Parsed => {
    try {
      return { ok: true as const, data: parseYaml(appState.yamlText) };
    } catch (err: any) {
      return { ok: false as const, error: String(err?.message || err || "YAML parse failed") };
    }
  });

  const relationsGraph = $derived(() => {
    const p = parsed();
    if (!p.ok) return { nodes: [], edges: [] };
    return buildRelationsGraph(p.data);
  });

  const relationsGraphRoots = $derived(() => {
    const p = parsed();
    if (!p.ok) return [] as string[];
    const mainSource = p.data && typeof p.data.main_source === "object" ? p.data.main_source : null;
    const id = mainSource && typeof (mainSource as any).source_id === "string" ? String((mainSource as any).source_id).trim() : "";
    return id ? [id] : [];
  });

  let demandSchema = $state<any | null>(null);
  const helpText = (path: string[]) => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, path);
  };

  let lastError = $state<string>("");
  let drafts = $state<RelationDraft[]>([]);

  let addRelationId = $state<string>("");
  let addRelationFrom = $state<string>("");
  let addRelationTo = $state<string>("");

  let addStepDrafts = $state<Record<string, { from: string; to: string }>>({});

  const ensureAddStepDraft = (relationId: string) => {
    if (!relationId) return { from: "", to: "" };
    if (!addStepDrafts[relationId]) addStepDrafts[relationId] = { from: "", to: "" };
    return addStepDrafts[relationId];
  };

  const csvToItems = (raw: string): string[] => {
    const parts = String(raw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return parts;
  };

  const itemsToInline = (items: string[]): string => {
    if (!items.length) return "";
    if (items.length === 1) return items[0] as string;
    return "[" + items.join(", ") + "]";
  };

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    const relations = data.relations && typeof data.relations === "object" && !Array.isArray(data.relations) ? data.relations : {};

    const next: RelationDraft[] = [];
    for (const [relIdRaw, relCfgRaw] of Object.entries(relations)) {
      const relationId = String(relIdRaw);
      const cfg = relCfgRaw && typeof relCfgRaw === "object" && !Array.isArray(relCfgRaw) ? (relCfgRaw as any) : {};
      const steps = Array.isArray(cfg.steps) ? cfg.steps : [];

      const stepDrafts: StepDraft[] = [];
      for (let i = 0; i < steps.length; i += 1) {
        const st = steps[i] && typeof steps[i] === "object" && !Array.isArray(steps[i]) ? (steps[i] as any) : {};

        const fromItems = Array.isArray(st.from) ? st.from.map((x: any) => String(x)) : typeof st.from === "string" ? [st.from] : [];
        const toItems = Array.isArray(st.to) ? st.to.map((x: any) => String(x)) : typeof st.to === "string" ? [st.to] : [];

        const lookupCastPresent = Object.prototype.hasOwnProperty.call(st, "lookup_cast");
        const lc = st.lookup_cast && typeof st.lookup_cast === "object" ? (st.lookup_cast as any) : {};
        const lookupCastName: LookupCastName | "" =
          lc.name === "auto" || lc.name === "int" || lc.name === "str" || lc.name === "sep_first" ? lc.name : "";
        const lookupCastSepPresent = Object.prototype.hasOwnProperty.call(lc, "sep");
        const lookupCastSepDraft = typeof lc.sep === "string" ? lc.sep : "";

        const toBindPresent = Object.prototype.hasOwnProperty.call(st, "to_bind");
        const tb = st.to_bind && typeof st.to_bind === "object" ? (st.to_bind as any) : {};
        let toBindKind: BindKind = "none";
        let toBindParamDraft = "";
        let toBindAsDraft: "set" | "list" = "set";
        let toBindCacheModeDraft: "batch" | "none" = "batch";
        if (tb.use_keys && typeof tb.use_keys === "object") {
          toBindKind = "use_keys";
          toBindParamDraft = typeof tb.use_keys.param === "string" ? tb.use_keys.param : "";
          toBindAsDraft = tb.use_keys.as === "list" ? "list" : "set";
        } else if (tb.use_rows && typeof tb.use_rows === "object") {
          toBindKind = "use_rows";
          toBindParamDraft = typeof tb.use_rows.param === "string" ? tb.use_rows.param : "";
          toBindCacheModeDraft = tb.use_rows.cache_mode === "none" ? "none" : "batch";
        }

        stepDrafts.push({
          idx: i,
          fromDraft: fromItems.join(", "),
          toDraft: toItems.join(", "),
          lookupCastPresent,
          lookupCastName,
          lookupCastSepPresent,
          lookupCastSepDraft,
          toBindPresent,
          toBindKind,
          toBindParamDraft,
          toBindAsDraft,
          toBindCacheModeDraft
        });
      }

      next.push({ relationId, steps: stepDrafts });
    }

    next.sort((a, b) => a.relationId.localeCompare(b.relationId));
    drafts = next;

    for (const rel of next) ensureAddStepDraft(rel.relationId);
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
    appState.activePath = "relations";
    const loc = lookupYamlLocation("relations", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const jumpToRelation = (relationId: string) => {
    appState.activePath = "relations." + relationId;
    const loc = lookupYamlLocation("relations." + relationId, appState.yamlLocations);
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

  const removeRelation = (relationId: string) => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["relations", relationId], { pruneEmptyParents: true }), "Remove relations." + relationId);
  };

  const applyFromTo = (relationId: string, stepIdx: number, which: "from" | "to", rawDraft: string) => {
    const items = csvToItems(rawDraft);
    const inline = itemsToInline(items);
    if (!inline) {
      lastError = "relations." + relationId + ".steps[" + String(stepIdx) + "]." + which + " is required";
      return;
    }
    applyPatch(
      setInlineValueAtPath(appState.yamlText, ["relations", relationId, "steps", String(stepIdx), which], inline, { createMissing: true }),
      "Update relations." + relationId + ".steps[" + String(stepIdx) + "]." + which
    );
  };

  const addStep = (relationId: string, rawFrom: string, rawTo: string) => {
    const fromInline = itemsToInline(csvToItems(rawFrom));
    const toInline = itemsToInline(csvToItems(rawTo));
    if (!fromInline || !toInline) {
      lastError = "Step requires from/to";
      return;
    }
    const rel = drafts.find((r) => r.relationId === relationId);
    const idx = rel ? rel.steps.length : 0;
    const inlineMap = "{from: " + fromInline + ", to: " + toInline + "}";
    applyPatch(insertInlineItemAtPath(appState.yamlText, ["relations", relationId, "steps"], idx, inlineMap), "Insert relations." + relationId + ".steps");
  };

  const removeStep = (relationId: string, stepIdx: number) => {
    applyPatch(removeSeqItemAtPath(appState.yamlText, ["relations", relationId, "steps"], stepIdx), "Remove relations." + relationId + ".steps[" + String(stepIdx) + "]");
  };

  const applyLookupCast = (relationId: string, stepIdx: number, name: string, sepDraft: string) => {
    const cleaned = String(name || "").trim();
    if (!cleaned) {
      applyPatch(
        removeKeyAtPath(appState.yamlText, ["relations", relationId, "steps", String(stepIdx), "lookup_cast"], { pruneEmptyParents: true }),
        "Remove lookup_cast"
      );
      return;
    }

    const lcName: LookupCastName | "" =
      cleaned === "auto" || cleaned === "int" || cleaned === "str" || cleaned === "sep_first" ? (cleaned as LookupCastName) : "";
    if (!lcName) return;

    const needsSep = lcName === "sep_first";
    const out = composePatchResults(appState.yamlText, [
      (t) => ensureEmptyMapAtPathDeep(t, ["relations", relationId, "steps", String(stepIdx), "lookup_cast"], { createMissing: true }),
      (t) => setScalarAtPathDeep(t, ["relations", relationId, "steps", String(stepIdx), "lookup_cast", "name"], lcName, { createMissing: true }),
      (t) => {
        if (!needsSep) {
          return removeKeyAtPath(t, ["relations", relationId, "steps", String(stepIdx), "lookup_cast", "sep"], { pruneEmptyParents: true });
        }
        const sep = String(sepDraft || "").trim() || ",";
        return setScalarAtPathDeep(t, ["relations", relationId, "steps", String(stepIdx), "lookup_cast", "sep"], sep, { createMissing: true });
      }
    ]);
    applyPatch(out, "Update lookup_cast");
  };

  const applyToBind = (relationId: string, stepIdx: number, kind: BindKind, paramDraft: string, asDraft: string, cacheModeDraft: string) => {
    const cleanedKind: BindKind = kind === "use_keys" || kind === "use_rows" ? kind : "none";

    if (cleanedKind === "none") {
      applyPatch(
        removeKeyAtPath(appState.yamlText, ["relations", relationId, "steps", String(stepIdx), "to_bind"], { pruneEmptyParents: true }),
        "Remove to_bind"
      );
      return;
    }

    const cleanedParam = String(paramDraft || "").trim();
    if (!cleanedParam) {
      lastError = "to_bind.param is required";
      return;
    }

    const basePath = ["relations", relationId, "steps", String(stepIdx), "to_bind"];
    const out = composePatchResults(appState.yamlText, [
      (t) => removeKeyAtPath(t, basePath, { pruneEmptyParents: true }),
      (t) => ensureEmptyMapAtPathDeep(t, cleanedKind === "use_keys" ? basePath.concat(["use_keys"]) : basePath.concat(["use_rows"]), { createMissing: true }),
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
          if (asValue === "set") {
            return removeKeyAtPath(t, basePath.concat(["use_keys", "as"]), { pruneEmptyParents: true });
          }
          return setScalarAtPathDeep(t, basePath.concat(["use_keys", "as"]), asValue, { createMissing: true });
        }
        const cmValue = cacheModeDraft === "none" ? "none" : "batch";
        if (cmValue === "batch") {
          return removeKeyAtPath(t, basePath.concat(["use_rows", "cache_mode"]), { pruneEmptyParents: true });
        }
        return setScalarAtPathDeep(t, basePath.concat(["use_rows", "cache_mode"]), cmValue, { createMissing: true });
      }
    ]);
    applyPatch(out, "Update to_bind");
  };

  const onAddRelation = () => {
    const relId = addRelationId.trim();
    if (!relId) return;
    const fromInline = itemsToInline(csvToItems(addRelationFrom));
    const toInline = itemsToInline(csvToItems(addRelationTo));
    if (!fromInline || !toInline) {
      lastError = "Relation requires initial step from/to";
      return;
    }

    const blockLines = ["steps:", "  - {from: " + fromInline + ", to: " + toInline + "}"];
    const out = composePatchResults(appState.yamlText, [
      (t) => ensureEmptyMapAtPathDeep(t, ["relations"], { createMissing: true }),
      (t) => appendAnchoredBlockEntryAtPath(t, ["relations"], relId, relId, blockLines)
    ]);
    applyPatch(out, "Add relations." + relId);

    addRelationId = "";
    addRelationFrom = "";
    addRelationTo = "";
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
        Relations
      </button>
      <SchemaHint text={helpText(["relations"])} label="relations" />
      <Badge variant="outline">{drafts.length}</Badge>
    </div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  {#if !parsed().ok}
    <div class="rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">YAML 解析失败,relations 可视化暂不可用</div>
  {:else}
    <div class="mb-3">
      <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
        <div class="font-medium text-slate-600">关系图</div>
        <div class="text-slate-400">点击节点/边定位</div>
      </div>
      <DirectedGraph
        graph={relationsGraph()}
        rootIds={relationsGraphRoots()}
        selectedPath={appState.activePath}
        title=""
        on:select={onGraphSelect}
      />
    </div>

    {#if drafts.length === 0}
      <div class="mb-3 rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 relations(可在下方添加)</div>
    {:else}
      <div class="flex flex-col gap-2">
        {#each drafts as rel (rel.relationId)}
          {@const stepDraft = ensureAddStepDraft(rel.relationId)}
          {@const relPath = "relations." + rel.relationId}
          {@const relActive = Boolean(appState.activePath && (appState.activePath === relPath || appState.activePath.startsWith(relPath + ".")))}
          <details
            class="rounded-xl border bg-white"
            class:border-sky-300={relActive}
            class:ring-2={relActive}
            class:ring-sky-100={relActive}
            open
          >
            <summary class="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2">
              <div class="min-w-0 flex items-center gap-2">
                <button
                  type="button"
                  class="truncate font-mono text-[11px] font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                  title="点击定位到 YAML"
                  onclick={(e) => {
                    e.preventDefault();
                    jumpToRelation(rel.relationId);
                  }}
                >
                  {rel.relationId}
                </button>
                {#if (appState.yamlLocations as any)["relations." + rel.relationId]}
                  <span class="text-[11px] text-slate-500">L{(appState.yamlLocations as any)["relations." + rel.relationId].line}</span>
                {/if}
                <Badge variant="secondary">{rel.steps.length} steps</Badge>
              </div>
              <button
                type="button"
                class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                title={"移除 relations." + rel.relationId + "(从 YAML 删除)"}
                aria-label={"remove relation " + rel.relationId}
                onclick={(e) => {
                  e.preventDefault();
                  removeRelation(rel.relationId);
                }}
              >
                删除
              </button>
            </summary>

            <div class="border-t bg-slate-50/40 p-3">
              <div class="mb-2 flex items-center gap-2 text-[11px] text-slate-600">
                <div class="font-medium">steps</div>
                <SchemaHint text={helpText(["relations", rel.relationId, "steps"])} label={"relations." + rel.relationId + ".steps"} />
              </div>

              {#if rel.steps.length === 0}
                <div class="rounded-lg border bg-white px-3 py-2 text-xs text-slate-600">暂无 steps(schema 要求至少 1 条)</div>
              {:else}
                <div class="flex flex-col gap-2">
                  {#each rel.steps as st, sidx (st.idx)}
                    {@const stepPath = relPath + ".steps." + String(st.idx)}
                    {@const stepActive = Boolean(appState.activePath && (appState.activePath === stepPath || appState.activePath.startsWith(stepPath + ".")))}
                    <div
                      class="rounded-lg border bg-white p-3 text-xs"
                      class:border-sky-300={stepActive}
                      class:ring-2={stepActive}
                      class:ring-sky-100={stepActive}
                    >
                      <div class="mb-2 flex items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                          <Badge variant="outline">#{st.idx}</Badge>
                          <span class="text-[11px] text-slate-500">from → to</span>
                        </div>
                        <button
                          type="button"
                          class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                          title="移除该 step(从 YAML 删除)"
                          onclick={() => removeStep(rel.relationId, st.idx)}
                        >
                          删除 step
                        </button>
                      </div>

                      <div class="grid grid-cols-12 gap-2">
                        <div class="col-span-6">
                          <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                            <label class="font-medium" for={"rel-" + rel.relationId + "-from-" + st.idx}>from</label>
                            <SchemaHint text={helpText(["relations", rel.relationId, "steps", String(st.idx), "from"])} label="from" />
                          </div>
                          <input
                            id={"rel-" + rel.relationId + "-from-" + st.idx}
                            class="sx-input-sm w-full font-mono"
                            placeholder="orders.customer_id 或 orders.a, orders.b"
                            value={st.fromDraft}
                            oninput={(e) => {
                              const v = (e.target as HTMLInputElement).value;
                              st.fromDraft = v;
                              rel.steps[sidx] = st;
                              drafts = drafts;
                            }}
                            onblur={() => applyFromTo(rel.relationId, st.idx, "from", st.fromDraft)}
                          />
                        </div>
                        <div class="col-span-6">
                          <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                            <label class="font-medium" for={"rel-" + rel.relationId + "-to-" + st.idx}>to</label>
                            <SchemaHint text={helpText(["relations", rel.relationId, "steps", String(st.idx), "to"])} label="to" />
                          </div>
                          <input
                            id={"rel-" + rel.relationId + "-to-" + st.idx}
                            class="sx-input-sm w-full font-mono"
                            placeholder="customers.customer_id 或 customers.a, customers.b"
                            value={st.toDraft}
                            oninput={(e) => {
                              const v = (e.target as HTMLInputElement).value;
                              st.toDraft = v;
                              rel.steps[sidx] = st;
                              drafts = drafts;
                            }}
                            onblur={() => applyFromTo(rel.relationId, st.idx, "to", st.toDraft)}
                          />
                        </div>
                      </div>

                      <div class="mt-3 grid grid-cols-12 gap-2">
                        <div class="col-span-6">
                          <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                            <div class="flex items-center gap-2">
                              <span class="font-medium">lookup_cast</span>
                              <SchemaHint
                                text={helpText(["relations", rel.relationId, "steps", String(st.idx), "lookup_cast"])}
                                label="lookup_cast"
                              />
                            </div>
                            {#if st.lookupCastPresent}
                              <button
                                type="button"
                                class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                                title="移除 lookup_cast(从 YAML 删除)"
                                onclick={() => applyLookupCast(rel.relationId, st.idx, "", "")}
                              >
                                ×
                              </button>
                            {/if}
                          </div>
                          <div class="flex items-center gap-2">
                            <select
                              class="sx-select h-8 flex-1"
                              value={st.lookupCastName || ""}
                              onchange={(e) => {
                                const v = (e.target as HTMLSelectElement).value;
                                st.lookupCastPresent = Boolean(v);
                                st.lookupCastName = v as any;
                                rel.steps[sidx] = st;
                                drafts = drafts;
                                applyLookupCast(rel.relationId, st.idx, v, st.lookupCastSepDraft);
                              }}
                              aria-label="lookup_cast name"
                            >
                              <option value="">(none)</option>
                              <option value="auto">auto</option>
                              <option value="int">int</option>
                              <option value="str">str</option>
                              <option value="sep_first">sep_first</option>
                            </select>
                            {#if st.lookupCastName === "sep_first"}
                              <input
                                class="sx-input-sm w-[120px] font-mono"
                                placeholder="sep (默认 ,)"
                                value={st.lookupCastSepDraft}
                                oninput={(e) => {
                                  const v = (e.target as HTMLInputElement).value;
                                  st.lookupCastSepDraft = v;
                                  rel.steps[sidx] = st;
                                  drafts = drafts;
                                }}
                                onblur={() => applyLookupCast(rel.relationId, st.idx, st.lookupCastName, st.lookupCastSepDraft)}
                              />
                            {/if}
                          </div>
                        </div>

                        <div class="col-span-6">
                          <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                            <div class="flex items-center gap-2">
                              <span class="font-medium">to_bind</span>
                              <SchemaHint text={helpText(["relations", rel.relationId, "steps", String(st.idx), "to_bind"])} label="to_bind" />
                            </div>
                            {#if st.toBindPresent}
                              <button
                                type="button"
                                class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                                title="移除 to_bind(从 YAML 删除)"
                                onclick={() => applyToBind(rel.relationId, st.idx, "none", "", "set", "batch")}
                              >
                                ×
                              </button>
                            {/if}
                          </div>
                          <div class="flex items-center gap-2">
                            <select
                              class="sx-select h-8 w-[120px]"
                              value={st.toBindKind}
                              onchange={(e) => {
                                const v = (e.target as HTMLSelectElement).value as BindKind;
                                st.toBindPresent = v !== "none";
                                st.toBindKind = v;
                                rel.steps[sidx] = st;
                                drafts = drafts;
                                applyToBind(rel.relationId, st.idx, v, st.toBindParamDraft, st.toBindAsDraft, st.toBindCacheModeDraft);
                              }}
                              aria-label="to_bind kind"
                            >
                              <option value="none">(none)</option>
                              <option value="use_keys">use_keys</option>
                              <option value="use_rows">use_rows</option>
                            </select>
                            <input
                              class="sx-input-sm flex-1 font-mono"
                              placeholder="param(必填)"
                              value={st.toBindParamDraft}
                              oninput={(e) => {
                                const v = (e.target as HTMLInputElement).value;
                                st.toBindParamDraft = v;
                                rel.steps[sidx] = st;
                                drafts = drafts;
                              }}
                              onblur={() => applyToBind(rel.relationId, st.idx, st.toBindKind, st.toBindParamDraft, st.toBindAsDraft, st.toBindCacheModeDraft)}
                            />
                            {#if st.toBindKind === "use_keys"}
                              <select
                                class="sx-select h-8 w-[92px]"
                                value={st.toBindAsDraft}
                                onchange={(e) => {
                                  const v = (e.target as HTMLSelectElement).value as any;
                                  st.toBindAsDraft = v === "list" ? "list" : "set";
                                  rel.steps[sidx] = st;
                                  drafts = drafts;
                                  applyToBind(rel.relationId, st.idx, st.toBindKind, st.toBindParamDraft, st.toBindAsDraft, st.toBindCacheModeDraft);
                                }}
                                aria-label="to_bind as"
                              >
                                <option value="set">set</option>
                                <option value="list">list</option>
                              </select>
                            {:else if st.toBindKind === "use_rows"}
                              <select
                                class="sx-select h-8 w-[110px]"
                                value={st.toBindCacheModeDraft}
                                onchange={(e) => {
                                  const v = (e.target as HTMLSelectElement).value as any;
                                  st.toBindCacheModeDraft = v === "none" ? "none" : "batch";
                                  rel.steps[sidx] = st;
                                  drafts = drafts;
                                  applyToBind(rel.relationId, st.idx, st.toBindKind, st.toBindParamDraft, st.toBindAsDraft, st.toBindCacheModeDraft);
                                }}
                                aria-label="to_bind cache_mode"
                              >
                                <option value="batch">cache: batch</option>
                                <option value="none">cache: none</option>
                              </select>
                            {/if}
                          </div>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}

              <div class="mt-3 rounded-lg border bg-white p-3 text-xs">
                <div class="mb-2 text-[11px] font-medium text-slate-600">添加 step</div>
                <div class="grid grid-cols-12 gap-2">
                  <input
                    class="sx-input-sm col-span-5 font-mono"
                    placeholder="from(例:orders.customer_id)"
                    bind:value={stepDraft.from}
                  />
                  <input class="sx-input-sm col-span-5 font-mono" placeholder="to(例:customers.customer_id)" bind:value={stepDraft.to} />
                  <Button
                    variant="add"
                    size="icon"
                    className="col-span-2 justify-self-end"
                    aria-label={"add step for " + rel.relationId}
                    title="添加 step"
                    on:click={() => addStep(rel.relationId, stepDraft.from, stepDraft.to)}
                  />
                </div>
                <div class="mt-2 text-[11px] text-slate-500">支持逗号分隔复合键:`orders.a, orders.b` → `[orders.a, orders.b]`</div>
              </div>
            </div>
          </details>
        {/each}
      </div>
    {/if}

    <div class="mt-4 rounded-xl border bg-slate-50/50 p-3">
      <div class="mb-2 text-xs font-semibold text-slate-800">添加 relation(会自动创建 `&amp;anchor`)</div>
      <div class="grid grid-cols-12 gap-2">
        <input
          class="sx-input-sm col-span-4 font-mono"
          name="add_relation_id"
          placeholder="relation_id(例:orders_to_customers)"
          bind:value={addRelationId}
          onkeydown={(e) => {
            if ((e as KeyboardEvent).key === "Enter") onAddRelation();
          }}
        />
        <input class="sx-input-sm col-span-4 font-mono" placeholder="from(例:orders.customer_id)" bind:value={addRelationFrom} />
        <input class="sx-input-sm col-span-4 font-mono" placeholder="to(例:customers.customer_id)" bind:value={addRelationTo} />
      </div>
      <div class="mt-2 flex items-center justify-between gap-2">
        <div class="text-[11px] text-slate-500">会插入 `relation_id: &amp;relation_id` + `steps`,避免后续无法用 `*alias`.</div>
        <Button variant="add" size="icon" aria-label="add relation" title="添加 relation" on:click={onAddRelation} />
      </div>
    </div>
  {/if}
</section>

<style>
  summary {
    list-style: none;
  }
  summary::-webkit-details-marker {
    display: none;
  }
</style>
