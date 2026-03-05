<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import { ensureEmptyMapAtPathDeep, removeKeyAtPath, removeKeyAtPathKeepEmptyMap, setScalarAtPathDeep } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import { parse as parseYaml } from "yaml";

  type ValueCast = "auto" | "int" | "str";

  type FieldDraft = {
    fieldId: string;
    fieldPresent: boolean;
    fieldDraft: string;
    namePresent: boolean;
    nameDraft: string;
    valueCastPresent: boolean;
    valueCastDraft: ValueCast;
  };

  type Parsed =
    | { ok: true; data: any }
    | { ok: false; error: string };

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

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    const mainSource = data.main_source && typeof data.main_source === "object" ? data.main_source : {};
    fieldsPresent = Object.prototype.hasOwnProperty.call(mainSource, "fields");
    const fields = mainSource.fields && typeof mainSource.fields === "object" && !Array.isArray(mainSource.fields) ? mainSource.fields : {};

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

      next.push({ fieldId, fieldPresent, fieldDraft, namePresent, nameDraft, valueCastPresent, valueCastDraft });
    }
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
    const loc = lookupYamlLocation("main_source.fields", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const jumpToField = (fieldId: string) => {
    const loc = lookupYamlLocation("main_source.fields." + fieldId, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const ensureField = (fieldId: string) => {
    const cleaned = String(fieldId || "").trim();
    if (!cleaned) return;
    applyPatch(
      ensureEmptyMapAtPathDeep(appState.yamlText, ["main_source", "fields", cleaned], { createMissing: true }),
      "Ensure main_source.fields." + cleaned
    );
  };

  const removeFieldsBlock = () => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["main_source", "fields"], { pruneEmptyParents: true }), "Remove main_source.fields");
  };

  const removeField = (fieldId: string) => {
    applyPatch(
      removeKeyAtPath(appState.yamlText, ["main_source", "fields", fieldId], { pruneEmptyParents: true }),
      "Remove main_source.fields." + fieldId
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
      removeOptional(["main_source", "fields", fieldId, "field"]);
      return;
    }
    applyOptionalString(["main_source", "fields", fieldId, "field"], raw);
  };

  const applyName = (fieldId: string, draft: string) => {
    applyOptionalString(["main_source", "fields", fieldId, "name"], draft);
  };

  const applyValueCast = (fieldId: string, value: ValueCast) => {
    if (!value || value === "auto") {
      removeOptional(["main_source", "fields", fieldId, "value_cast"]);
      return;
    }
    applyOptionalString(["main_source", "fields", fieldId, "value_cast"], value);
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
        Main Source Fields
      </button>
      {#if fieldsPresent}
        <button
          type="button"
          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title="移除 main_source.fields(从 YAML 删除)"
          aria-label="remove main_source.fields"
          onclick={removeFieldsBlock}
        >
          ×
        </button>
      {/if}
      <SchemaHint text={helpText(["main_source", "fields"])} label="main_source.fields" />
      <Badge variant="outline">{drafts.length}</Badge>
    </div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  {#if drafts.length === 0}
    <div class="rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 main_source.fields(可在下方添加)</div>
  {:else}
    <div class="flex flex-col gap-1">
      {#each drafts as f, idx (f.fieldId)}
        <div class="group rounded-lg border bg-white px-3 py-2 text-xs">
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
                {#if (appState.yamlLocations as any)["main_source.fields." + f.fieldId]}
                  <span class="text-[11px] text-slate-500">L{(appState.yamlLocations as any)["main_source.fields." + f.fieldId].line}</span>
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
            <div class="col-span-5">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"msf-field-" + idx}>field(data_key)</label>
                <div class="flex items-center gap-1">
                  {#if f.fieldPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 field(恢复默认=field_id)"
                      aria-label={"remove field of " + f.fieldId}
                      onclick={() => removeOptional(["main_source", "fields", f.fieldId, "field"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["main_source", "fields", f.fieldId, "field"])} label={"fields." + f.fieldId + ".field"} />
                </div>
              </div>
              <input
                id={"msf-field-" + idx}
                class="sx-input h-8 w-full"
                name={"main_source.fields." + f.fieldId + ".field"}
                placeholder={"默认: " + f.fieldId}
                value={f.fieldPresent ? f.fieldDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, fieldPresent: true, fieldDraft: v };
                }}
                onkeydown={(e) => {
                  if ((e as KeyboardEvent).key === "Enter") applyDataKey(f.fieldId, drafts[idx].fieldDraft);
                }}
                onblur={() => applyDataKey(f.fieldId, drafts[idx].fieldDraft)}
              />
            </div>

            <div class="col-span-5">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"msf-name-" + idx}>name</label>
                <div class="flex items-center gap-1">
                  {#if f.namePresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 name(从 YAML 删除)"
                      aria-label={"remove name of " + f.fieldId}
                      onclick={() => removeOptional(["main_source", "fields", f.fieldId, "name"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["main_source", "fields", f.fieldId, "name"])} label={"fields." + f.fieldId + ".name"} />
                </div>
              </div>
              <input
                id={"msf-name-" + idx}
                class="sx-input h-8 w-full"
                name={"main_source.fields." + f.fieldId + ".name"}
                placeholder="可选:表头显示名"
                value={f.namePresent ? f.nameDraft : ""}
                oninput={(e) => {
                  const v = (e.target as HTMLInputElement).value;
                  drafts[idx] = { ...f, namePresent: true, nameDraft: v };
                }}
                onkeydown={(e) => {
                  if ((e as KeyboardEvent).key === "Enter") applyName(f.fieldId, drafts[idx].nameDraft);
                }}
                onblur={() => applyName(f.fieldId, drafts[idx].nameDraft)}
              />
            </div>

            <div class="col-span-2">
              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <label class="font-medium" for={"msf-cast-" + idx}>value_cast</label>
                <div class="flex items-center gap-1">
                  {#if f.valueCastPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 value_cast(恢复默认=auto)"
                      aria-label={"remove value_cast of " + f.fieldId}
                      onclick={() => removeOptional(["main_source", "fields", f.fieldId, "value_cast"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint
                    text={helpText(["main_source", "fields", f.fieldId, "value_cast"])}
                    label={"fields." + f.fieldId + ".value_cast"}
                  />
                </div>
              </div>
              <select
                id={"msf-cast-" + idx}
                class="sx-select h-8 w-full"
                name={"main_source.fields." + f.fieldId + ".value_cast"}
                value={f.valueCastPresent ? f.valueCastDraft : "auto"}
                onchange={(e) => {
                  const v = ((e.target as HTMLSelectElement).value as ValueCast) || "auto";
                  drafts[idx] = { ...f, valueCastPresent: true, valueCastDraft: v };
                  applyValueCast(f.fieldId, v);
                }}
              >
                <option value="auto">auto</option>
                <option value="int">int</option>
                <option value="str">str</option>
              </select>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <div class="mt-3 rounded-lg border bg-slate-50 p-3">
    <div class="mb-2 text-xs font-semibold text-slate-800">添加字段</div>
    <div class="flex items-center gap-2">
      <input
        class="sx-input flex-1"
        name="add_main_source_field_id"
        id="add-main-source-field"
        placeholder="field_id(例:customer_id)"
        bind:value={addFieldIdDraft}
        onkeydown={(e) => {
          if ((e as KeyboardEvent).key === "Enter") onAddField();
        }}
      />
      <Button variant="add" size="icon" aria-label="add main source field" title="添加字段" on:click={onAddField} />
    </div>
    <div class="mt-2 text-[11px] text-slate-500">
      提示:`field`/`name`/`value_cast` 均可选;留空表示采用默认行为(可用 × 移除显式配置).
    </div>
  </div>
</section>
