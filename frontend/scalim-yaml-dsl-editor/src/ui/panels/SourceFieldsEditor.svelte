<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import {
    ensureEmptyMapAtPathDeep,
    removeKeyAtPath,
    removeKeyAtPathKeepEmptyMap,
    setInlineValueAtPath,
    setScalarAtPathDeep
  } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import { isAlias, isMap, isScalar, parse as parseYaml, parseDocument, type Node, type Pair, type ParsedNode, type YAMLMap } from "yaml";

  type ValueCast = "auto" | "int" | "str";
  type RelationKind = "none" | "alias" | "inline";

  type FieldDraft = {
    fieldId: string;
    fieldPresent: boolean;
    fieldDraft: string;
    namePresent: boolean;
    nameDraft: string;
    valueCastPresent: boolean;
    valueCastDraft: ValueCast;
    relationPresent: boolean;
    relationKind: RelationKind;
    relationAliasDraft: string;
  };

  type Props = {
    sourceId: string;
    relationOptions?: string[];
  };

  let { sourceId, relationOptions = [] }: Props = $props();

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
  let drafts = $state<FieldDraft[]>([]);
  let fieldsPresent = $state<boolean>(false);
  let addFieldIdDraft = $state<string>("");

  const scalarKeyToString = (keyNode: any): string => {
    if (isScalar(keyNode)) return String((keyNode as any).value ?? "");
    return String((keyNode as any)?.value ?? "");
  };

  const findPairInMap = (mapNode: YAMLMap, key: string): Pair<ParsedNode, ParsedNode | null> | null => {
    for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
      if (scalarKeyToString(pair.key) === key) return pair;
    }
    return null;
  };

  const getIn = (root: Node | null, path: string[]): Node | null => {
    let current: Node | null = root;
    for (const seg of path) {
      if (!current) return null;
      if (isMap(current)) {
        const mapNode = current as YAMLMap;
        const pair = findPairInMap(mapNode, seg);
        current = (pair?.value as Node | null) || null;
        continue;
      }
      return null;
    }
    return current;
  };

  const readRelationKinds = (yamlText: string, sid: string): Record<string, { kind: RelationKind; alias: string }> => {
    let doc: any;
    try {
      doc = parseDocument(yamlText, { keepSourceTokens: true });
    } catch {
      return {};
    }
    const root = (doc?.contents as Node | null) || null;
    if (!root || !isMap(root)) return {};

    const fieldsNode = getIn(root, ["sources", sid, "fields"]);
    if (!fieldsNode || !isMap(fieldsNode)) return {};

    const out: Record<string, { kind: RelationKind; alias: string }> = {};
    const fieldsMap = fieldsNode as YAMLMap;
    for (const pair of fieldsMap.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
      const fieldId = scalarKeyToString(pair.key);
      const valueNode = (pair.value as Node | null) || null;
      if (!valueNode || !isMap(valueNode)) continue;
      const fieldMap = valueNode as YAMLMap;
      const relPair = findPairInMap(fieldMap, "relation");
      const relNode = (relPair?.value as Node | null) || null;
      if (!relNode) continue;
      if (isAlias(relNode)) {
        const alias = String((relNode as any).source || "").trim();
        out[fieldId] = { kind: "alias", alias };
      } else {
        out[fieldId] = { kind: "inline", alias: "" };
      }
    }
    return out;
  };

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    const sources = data.sources && typeof data.sources === "object" && !Array.isArray(data.sources) ? data.sources : {};
    const source = sources[sourceId] && typeof sources[sourceId] === "object" && !Array.isArray(sources[sourceId]) ? sources[sourceId] : {};

    fieldsPresent = Object.prototype.hasOwnProperty.call(source, "fields");
    const fields = source.fields && typeof source.fields === "object" && !Array.isArray(source.fields) ? source.fields : {};

    const relationKinds = readRelationKinds(appState.yamlText, sourceId);

    const next: FieldDraft[] = [];
    for (const [fieldIdRaw, cfgRaw] of Object.entries(fields)) {
      const fieldId = String(fieldIdRaw);
      const cfg = cfgRaw && typeof cfgRaw === "object" && !Array.isArray(cfgRaw) ? (cfgRaw as any) : {};

      const fieldPresent = Object.prototype.hasOwnProperty.call(cfg, "field");
      const fieldDraft = typeof cfg.field === "string" ? cfg.field : "";
      const namePresent = Object.prototype.hasOwnProperty.call(cfg, "name");
      const nameDraft = typeof cfg.name === "string" ? cfg.name : "";
      const valueCastPresent = Object.prototype.hasOwnProperty.call(cfg, "value_cast");
      const valueCastDraft: ValueCast = cfg.value_cast === "int" ? "int" : cfg.value_cast === "str" ? "str" : "auto";

      const rel = relationKinds[fieldId];
      const relationPresent = Boolean(rel);
      const relationKind: RelationKind = rel ? rel.kind : "none";
      const relationAliasDraft = rel && rel.kind === "alias" ? rel.alias : "";

      next.push({
        fieldId,
        fieldPresent,
        fieldDraft,
        namePresent,
        nameDraft,
        valueCastPresent,
        valueCastDraft,
        relationPresent,
        relationKind,
        relationAliasDraft
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
    const loc = lookupYamlLocation("sources." + sourceId + ".fields", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const jumpToField = (fieldId: string) => {
    const loc = lookupYamlLocation("sources." + sourceId + ".fields." + fieldId, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const ensureField = (fieldId: string) => {
    const cleaned = String(fieldId || "").trim();
    if (!cleaned) return;
    applyPatch(ensureEmptyMapAtPathDeep(appState.yamlText, ["sources", sourceId, "fields", cleaned], { createMissing: true }), "Ensure field");
  };

  const removeFieldsBlock = () => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["sources", sourceId, "fields"], { pruneEmptyParents: true }), "Remove sources." + sourceId + ".fields");
  };

  const removeField = (fieldId: string) => {
    applyPatch(
      removeKeyAtPath(appState.yamlText, ["sources", sourceId, "fields", fieldId], { pruneEmptyParents: true }),
      "Remove sources." + sourceId + ".fields." + fieldId
    );
  };

  const removeOptional = (path: string[]) => {
    applyPatch(removeKeyAtPathKeepEmptyMap(appState.yamlText, path), "Remove " + path.join("."));
  };

  const applyOptionalString = (path: string[], rawDraft: string) => {
    const raw = String(rawDraft || "").trim();
    if (!raw) {
      removeOptional(path);
      return;
    }
    applyPatch(setScalarAtPathDeep(appState.yamlText, path, raw, { createMissing: true }), "Update " + path.join("."));
  };

  const applyDataKey = (fieldId: string, draft: string) => {
    const raw = String(draft || "").trim();
    if (!raw || raw === fieldId) {
      removeOptional(["sources", sourceId, "fields", fieldId, "field"]);
      return;
    }
    applyOptionalString(["sources", sourceId, "fields", fieldId, "field"], raw);
  };

  const applyName = (fieldId: string, draft: string) => {
    applyOptionalString(["sources", sourceId, "fields", fieldId, "name"], draft);
  };

  const applyValueCast = (fieldId: string, value: ValueCast) => {
    if (!value || value === "auto") {
      removeOptional(["sources", sourceId, "fields", fieldId, "value_cast"]);
      return;
    }
    applyOptionalString(["sources", sourceId, "fields", fieldId, "value_cast"], value);
  };

  const applyRelationAlias = (fieldId: string, relationId: string) => {
    const cleaned = String(relationId || "").trim();
    if (!cleaned) {
      removeOptional(["sources", sourceId, "fields", fieldId, "relation"]);
      return;
    }
    applyPatch(
      setInlineValueAtPath(appState.yamlText, ["sources", sourceId, "fields", fieldId, "relation"], "*" + cleaned, { createMissing: true }),
      "Update relation"
    );
  };

  const onAddField = () => {
    const id = addFieldIdDraft.trim();
    if (!id) return;
    ensureField(id);
    addFieldIdDraft = "";
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
        Fields · {sourceId}
      </button>
      {#if fieldsPresent}
        <button
          type="button"
          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title={"移除 sources." + sourceId + ".fields(从 YAML 删除)"}
          aria-label="remove fields block"
          onclick={removeFieldsBlock}
        >
          ×
        </button>
      {/if}
      <SchemaHint text={helpText(["sources", sourceId, "fields"])} label={"sources." + sourceId + ".fields"} />
      <Badge variant="outline">{drafts.length}</Badge>
    </div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  {#if drafts.length === 0}
    <div class="rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 fields(可在下方添加)</div>
  {:else}
    <div class="flex flex-col gap-2">
      {#each drafts as f, idx (f.fieldId)}
        <div class="group rounded-xl border bg-white px-3 py-2 text-xs">
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
                {#if (appState.yamlLocations as any)["sources." + sourceId + ".fields." + f.fieldId]}
                  <span class="text-[11px] text-slate-500">L{(appState.yamlLocations as any)["sources." + sourceId + ".fields." + f.fieldId].line}</span>
                {/if}
                {#if f.relationKind === "inline"}
                  <Badge variant="warning">relation: inline</Badge>
                {:else if f.relationKind === "alias"}
                  <Badge variant="secondary">relation: *alias</Badge>
                {/if}
              </div>
            </div>

            <button
              type="button"
              class="rounded-md border bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              title={"移除字段 " + f.fieldId + "(从 YAML 删除)"}
              aria-label={"remove field " + f.fieldId}
              onclick={() => removeField(f.fieldId)}
            >
              删除
            </button>
          </div>

          <div class="mt-2 grid grid-cols-12 gap-2">
            <div class="col-span-4">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"sf-field-" + idx}>field(data_key)</label>
                <div class="flex items-center gap-1">
                  {#if f.fieldPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 field(恢复默认=field_id)"
                      onclick={() => removeOptional(["sources", sourceId, "fields", f.fieldId, "field"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["sources", sourceId, "fields", f.fieldId, "field"])} label="field" />
                </div>
              </div>
              <input
                id={"sf-field-" + idx}
                class="sx-input-sm h-8 w-full"
                name={"sources." + sourceId + ".fields." + f.fieldId + ".field"}
                placeholder={"默认: " + f.fieldId}
                value={f.fieldPresent ? f.fieldDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, fieldPresent: true, fieldDraft: v };
                }}
                onblur={() => applyDataKey(f.fieldId, f.fieldPresent ? f.fieldDraft : "")}
              />
            </div>

            <div class="col-span-4">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"sf-name-" + idx}>name</label>
                <div class="flex items-center gap-1">
                  {#if f.namePresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 name(从 YAML 删除)"
                      onclick={() => removeOptional(["sources", sourceId, "fields", f.fieldId, "name"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["sources", sourceId, "fields", f.fieldId, "name"])} label="name" />
                </div>
              </div>
              <input
                id={"sf-name-" + idx}
                class="sx-input-sm h-8 w-full"
                name={"sources." + sourceId + ".fields." + f.fieldId + ".name"}
                placeholder="显示名(可选)"
                value={f.namePresent ? f.nameDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, namePresent: true, nameDraft: v };
                }}
                onblur={() => applyName(f.fieldId, f.namePresent ? f.nameDraft : "")}
              />
            </div>

            <div class="col-span-4">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"sf-cast-" + idx}>value_cast</label>
                <div class="flex items-center gap-1">
                  {#if f.valueCastPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 value_cast(恢复默认=auto)"
                      onclick={() => removeOptional(["sources", sourceId, "fields", f.fieldId, "value_cast"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["sources", sourceId, "fields", f.fieldId, "value_cast"])} label="value_cast" />
                </div>
              </div>
              <select
                id={"sf-cast-" + idx}
                class="sx-select h-8 w-full"
                value={f.valueCastDraft}
                onchange={(e) => {
                  const v = (e.target as HTMLSelectElement).value as ValueCast;
                  drafts[idx] = { ...f, valueCastPresent: v !== "auto", valueCastDraft: v };
                  applyValueCast(f.fieldId, v);
                }}
                aria-label="value_cast"
              >
                <option value="auto">auto</option>
                <option value="int">int</option>
                <option value="str">str</option>
              </select>
            </div>
          </div>

          <div class="mt-3">
            <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
              <div class="flex items-center gap-2">
                <span class="font-medium">relation</span>
                <SchemaHint text={helpText(["sources", sourceId, "fields", f.fieldId, "relation"])} label="relation" />
              </div>
              {#if f.relationPresent}
                <button
                  type="button"
                  class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                  title="移除 relation(从 YAML 删除)"
                  onclick={() => removeOptional(["sources", sourceId, "fields", f.fieldId, "relation"])}
                >
                  ×
                </button>
              {/if}
            </div>

            <div class="flex items-center gap-2">
              <select
                class="sx-select h-8 flex-1"
                value={f.relationKind === "alias" ? f.relationAliasDraft : ""}
                onchange={(e) => {
                  const v = (e.target as HTMLSelectElement).value;
                  drafts[idx] = { ...f, relationPresent: Boolean(v), relationKind: v ? "alias" : "none", relationAliasDraft: v };
                  applyRelationAlias(f.fieldId, v);
                }}
                aria-label="relation alias"
              >
                <option value="">(none)</option>
                {#each relationOptions as relOpt (relOpt)}
                  <option value={relOpt}>{relOpt}</option>
                {/each}
              </select>
              {#if f.relationKind === "inline"}
                <span class="text-[11px] text-slate-500">当前为内联 steps(建议在 YAML / Relations 中编辑)</span>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <div class="mt-3 rounded-lg border bg-slate-50/60 p-3 text-xs">
    <div class="mb-2 text-[11px] font-medium text-slate-600">添加字段</div>
    <div class="flex items-center gap-2">
      <input
        class="sx-input-sm flex-1 font-mono"
        name="add_source_field_id"
        placeholder="field_id(例:customer_name)"
        bind:value={addFieldIdDraft}
        onkeydown={(e) => {
          if ((e as KeyboardEvent).key === "Enter") onAddField();
        }}
      />
      <Button variant="add" size="icon" aria-label={"add field for " + sourceId} title="添加字段" on:click={onAddField} />
    </div>
  </div>
</section>
