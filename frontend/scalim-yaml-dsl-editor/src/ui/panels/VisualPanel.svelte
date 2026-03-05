<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { onMount } from "svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { removeKeyAtPath, setScalarAtPathDeep } from "$services/yaml_patch";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath, schemaIsRequiredForPath } from "$services/schema_help";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import MainSourceFieldsEditor from "$ui/panels/MainSourceFieldsEditor.svelte";
  import MainSourceOrderByEditor from "$ui/panels/MainSourceOrderByEditor.svelte";
  import OutputFieldsEditor from "$ui/panels/OutputFieldsEditor.svelte";
  import RelationsEditor from "$ui/panels/RelationsEditor.svelte";
  import SourcesEditor from "$ui/panels/SourcesEditor.svelte";
  import DerivedFieldsEditor from "$ui/panels/DerivedFieldsEditor.svelte";
  import ObservabilityGuardrailsEditor from "$ui/panels/ObservabilityGuardrailsEditor.svelte";
  import { parse as parseYaml } from "yaml";

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

  const parseOk = $derived(() => parsed().ok);
  const parseError = $derived(() => {
    const p = parsed();
    return p.ok ? "" : p.error;
  });

  let lastApplyError = $state<string>("");

  let nameDraft = $state<string>("");
  let descDraft = $state<string>("");
  let batchSizeDraft = $state<string>("");
  let descPresent = $state<boolean>(false);
  let batchSizePresent = $state<boolean>(false);

  let mainSourceIdDraft = $state<string>("");
  let mainLoaderDraft = $state<string>("");
  type ParamKind = "string" | "number" | "boolean" | "null" | "complex";
  type ParamDraft = { key: string; kind: ParamKind; value: string };
  let paramsDrafts = $state<ParamDraft[]>([]);
  let paramsPresent = $state<boolean>(false);
  let addParamKeyDraft = $state<string>("");
  let addParamKindDraft = $state<Exclude<ParamKind, "complex">>("string");
  let addParamValueDraft = $state<string>("");

  let outputFormatDraft = $state<string>("");
  let outputPathDraft = $state<string>("");
  let outputEncodingDraft = $state<string>("");
  let outputFormatPresent = $state<boolean>(false);
  let outputPathPresent = $state<boolean>(false);
  let outputEncodingPresent = $state<boolean>(false);

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

    nameDraft = typeof data.name === "string" ? data.name : "";
    descPresent = Object.prototype.hasOwnProperty.call(data, "description");
    descDraft = typeof data.description === "string" ? data.description : "";
    batchSizePresent = Object.prototype.hasOwnProperty.call(data, "batch_size");
    batchSizeDraft = data.batch_size == null ? "" : String(data.batch_size);

    const mainSource = (data.main_source && typeof data.main_source === "object") ? data.main_source : {};
    mainSourceIdDraft = typeof mainSource.source_id === "string" ? mainSource.source_id : "";
    mainLoaderDraft = typeof mainSource.loader === "string" ? mainSource.loader : "";

    paramsPresent = Object.prototype.hasOwnProperty.call(mainSource, "params");
    const params = (mainSource.params && typeof mainSource.params === "object" && !Array.isArray(mainSource.params)) ? mainSource.params : {};
    const nextParams: ParamDraft[] = [];
    for (const [k, v] of Object.entries(params)) {
      const kind = parseParamKind(v);
      nextParams.push({ key: String(k), kind, value: stringifyParamValue(kind, v) });
    }
    paramsDrafts = nextParams;

    const output = (data.output && typeof data.output === "object") ? data.output : {};
    outputFormatPresent = Object.prototype.hasOwnProperty.call(output, "format");
    outputFormatDraft = typeof output.format === "string" ? output.format : "";
    outputPathPresent = Object.prototype.hasOwnProperty.call(output, "path");
    outputPathDraft = typeof output.path === "string" ? output.path : "";
    outputEncodingPresent = Object.prototype.hasOwnProperty.call(output, "encoding");
    outputEncodingDraft = typeof output.encoding === "string" ? output.encoding : "";
  };

  $effect(() => {
    appState.yamlText;
    lastApplyError = "";
    syncDrafts();
  });

  const requestJump = (path: string) => {
    const loc = lookupYamlLocation(path, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  let demandSchema = $state<any | null>(null);
  const helpText = (path: string[]) => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, path);
  };

  onMount(async () => {
    try {
      demandSchema = await loadDemandSchema();
    } catch {
      demandSchema = null;
    }
  });

  const applyScalar = (path: string[], value: string | number | boolean | null, createMissing = true) => {
    const out = setScalarAtPathDeep(appState.yamlText, path, value, { createMissing });
    const res = applyPatchResult(out, { title: "Update " + path.join(".") });
    lastApplyError = res.ok ? "" : res.error;
  };

  const removePath = (path: string[]) => {
    const out = removeKeyAtPath(appState.yamlText, path, { pruneEmptyParents: true });
    const res = applyPatchResult(out, { title: "Remove " + path.join(".") });
    lastApplyError = res.ok ? "" : res.error;
  };

  const isRequired = (path: string[]) => {
    if (!demandSchema) return false;
    const out = schemaIsRequiredForPath(demandSchema, path);
    return Boolean(out);
  };

  const applyBatchSize = () => {
    const raw = batchSizeDraft.trim();
    if (!raw) {
      if (!isRequired(["batch_size"])) removePath(["batch_size"]);
      return;
    }
    const n = Number(raw);
    if (!Number.isFinite(n)) {
      lastApplyError = "batch_size must be a number";
      return;
    }
    applyScalar(["batch_size"], n);
  };

  const applyOptionalString = (path: string[], draft: string) => {
    const raw = draft.trim();
    if (!raw) {
      if (!isRequired(path)) removePath(path);
      return;
    }
    applyScalar(path, draft);
  };

  const applyParamScalar = (key: string, kind: Exclude<ParamKind, "complex">, draftValue: string) => {
    const cleanedKey = String(key || "").trim();
    if (!cleanedKey) {
      lastApplyError = "params key is required";
      return;
    }

    if (kind === "null") {
      applyScalar(["main_source", "params", cleanedKey], null);
      return;
    }
    if (kind === "boolean") {
      const raw = String(draftValue || "").trim().toLowerCase();
      const v = raw === "false" ? false : true;
      applyScalar(["main_source", "params", cleanedKey], v);
      return;
    }
    if (kind === "number") {
      const raw = String(draftValue || "").trim();
      const n = Number(raw);
      if (!raw || !Number.isFinite(n)) {
        lastApplyError = "params." + cleanedKey + " must be a number";
        return;
      }
      applyScalar(["main_source", "params", cleanedKey], n);
      return;
    }

    applyScalar(["main_source", "params", cleanedKey], String(draftValue || ""));
  };

  const removeParam = (key: string) => {
    const cleanedKey = String(key || "").trim();
    if (!cleanedKey) return;
    removePath(["main_source", "params", cleanedKey]);
  };

  const onAddParam = () => {
    const key = addParamKeyDraft.trim();
    if (!key) return;
    applyParamScalar(key, addParamKindDraft, addParamValueDraft);
    addParamKeyDraft = "";
    addParamKindDraft = "string";
    addParamValueDraft = "";
  };
</script>

<div class="flex h-full flex-col">
  <div class="flex items-center justify-between border-b bg-slate-50 px-3 py-2 text-xs">
    <div class="font-semibold text-slate-800">Visual</div>
    <div class="text-[11px] text-slate-500">双向:表单 ⇄ YAML · 提示:点击 ?</div>
  </div>

  {#if !parseOk()}
    <div class="p-3 text-xs text-red-700">
      <div class="font-semibold">YAML parse error</div>
      <div class="mt-1 whitespace-pre-wrap font-mono text-[11px] text-red-600">{parseError()}</div>
      <div class="mt-2 text-slate-600">修复 YAML 后可继续使用可视化编辑.</div>
    </div>
  {:else}
    <div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3">
      {#if lastApplyError}
        <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {lastApplyError}
        </div>
      {/if}

      <div class="space-y-4">
        <section class="rounded-xl border bg-white p-3">
	          <div class="mb-2 flex items-center">
	            <button
	              type="button"
	              class="cursor-pointer text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
	              title="点击定位到 YAML"
	              onclick={() => requestJump("name")}
	            >
	              基本信息
	            </button>
	          </div>

	          <div class="grid grid-cols-1 gap-2">
	            <div class="text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-name" class="font-medium">name</label>
                  <div class="flex items-center gap-1">
	                  <SchemaHint text={helpText(["name"])} label="name" />
                  </div>
	              </div>
	              <input
	                id="v-name"
	                name="name"
	                class="sx-input w-full"
	                bind:value={nameDraft}
	                onblur={() => applyScalar(["name"], nameDraft)}
	              />
	            </div>

	            <div class="group text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-description" class="font-medium">description</label>
                  <div class="flex items-center gap-1">
                    {#if !isRequired(["description"]) && descPresent}
                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title="移除 description(从 YAML 删除)"
                        aria-label="remove description"
                        onclick={() => removePath(["description"])}
                      >
                        ×
                      </button>
                    {/if}
	                  <SchemaHint text={helpText(["description"])} label="description" />
                  </div>
	              </div>
	              <input
	                id="v-description"
	                name="description"
	                class="sx-input w-full"
	                bind:value={descDraft}
	                onblur={() => applyOptionalString(["description"], descDraft)}
	              />
	            </div>

	            <div class="group text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-batch_size" class="font-medium">batch_size</label>
                  <div class="flex items-center gap-1">
                    {#if !isRequired(["batch_size"]) && batchSizePresent}
                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title="移除 batch_size(从 YAML 删除)"
                        aria-label="remove batch_size"
                        onclick={() => removePath(["batch_size"])}
                      >
                        ×
                      </button>
                    {/if}
	                  <SchemaHint text={helpText(["batch_size"])} label="batch_size" />
                  </div>
	              </div>
	              <input
	                id="v-batch_size"
	                name="batch_size"
	                class="sx-input w-full"
	                inputmode="numeric"
	                bind:value={batchSizeDraft}
                onblur={applyBatchSize}
              />
            </div>
          </div>
        </section>

        <section class="rounded-xl border bg-white p-3">
	          <div class="mb-2 flex items-center">
	            <button
	              type="button"
	              class="cursor-pointer text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
	              title="点击定位到 YAML"
	              onclick={() => requestJump("main_source")}
	            >
	              Main Source
	            </button>
	          </div>

	          <div class="grid grid-cols-1 gap-2">
	            <div class="text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-main_source_source_id" class="font-medium">main_source.source_id</label>
	                <SchemaHint text={helpText(["main_source", "source_id"])} label="main_source.source_id" />
	              </div>
	              <input
	                id="v-main_source_source_id"
	                name="main_source.source_id"
	                class="sx-input w-full"
	                bind:value={mainSourceIdDraft}
	                onblur={() => applyScalar(["main_source", "source_id"], mainSourceIdDraft)}
              />
            </div>

	            <div class="text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-main_source_loader" class="font-medium">main_source.loader</label>
	                <SchemaHint text={helpText(["main_source", "loader"])} label="main_source.loader" />
	              </div>
	              <input
	                id="v-main_source_loader"
	                name="main_source.loader"
	                class="sx-input w-full"
	                bind:value={mainLoaderDraft}
	                onblur={() => applyScalar(["main_source", "loader"], mainLoaderDraft)}
              />
            </div>

            <div class="rounded-lg border bg-slate-50/60 p-2">
              <div class="mb-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                <div class="flex items-center gap-2">
                  <div class="font-medium text-slate-700">main_source.params</div>
                  {#if paramsPresent}
                    <button
                      type="button"
                      class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                      title="移除 main_source.params(从 YAML 删除)"
                      aria-label="remove main_source.params"
                      onclick={() => removePath(["main_source", "params"])}
                    >
                      ×
                    </button>
                  {/if}
                  <SchemaHint text={helpText(["main_source", "params"])} label="main_source.params" />
                </div>
                <div class="text-[10px] text-slate-400">键名与含义由 loader 决定</div>
              </div>

              {#if paramsDrafts.length === 0}
                <div class="mb-2 rounded-md border bg-white px-2 py-2 text-[11px] text-slate-600">暂无 params(可在下方添加)</div>
              {:else}
                <div class="mb-2 flex flex-col gap-1">
                  {#each paramsDrafts as p, idx (p.key)}
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
                              paramsDrafts[idx] = { ...p, kind: "boolean", value: v };
                              applyParamScalar(p.key, "boolean", v);
                            }}
                          >
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        {:else if p.kind === "null"}
                          <div class="mt-1 rounded-md border bg-slate-50 px-2 py-1 text-[11px] text-slate-600">null</div>
                        {:else}
                          <input
                            class="sx-input mt-1 w-full"
                            name={"params." + p.key}
                            inputmode={p.kind === "number" ? "decimal" : "text"}
                            value={p.value}
                            oninput={(e) => {
                              const v = (e.target as HTMLInputElement).value;
                              paramsDrafts[idx] = { ...p, value: v };
                            }}
                            onkeydown={(e) => {
                              if ((e as KeyboardEvent).key !== "Enter") return;
                              const cur = paramsDrafts[idx];
                              if (!cur || cur.kind === "complex") return;
                              applyParamScalar(cur.key, cur.kind === "number" ? "number" : "string", cur.value);
                            }}
                            onblur={() => {
                              const cur = paramsDrafts[idx];
                              if (!cur || cur.kind === "complex") return;
                              applyParamScalar(cur.key, cur.kind === "number" ? "number" : "string", cur.value);
                            }}
                          />
                        {/if}
                      </div>

                      <div class="flex flex-col items-end gap-1">
                        {#if p.kind !== "complex"}
                          <select
                            class="sx-select h-8 w-[110px]"
                            aria-label={"params." + p.key + " type"}
                            value={p.kind === "number" ? "number" : p.kind === "boolean" ? "boolean" : p.kind === "null" ? "null" : "string"}
                            onchange={(e) => {
                              const raw = (e.target as HTMLSelectElement).value;
                              const nextKind = (raw === "number" || raw === "boolean" || raw === "null") ? raw : "string";
                              let nextValue = p.value;
                              if (nextKind === "boolean") nextValue = p.value.trim().toLowerCase() === "false" ? "false" : "true";
                              if (nextKind === "null") nextValue = "";
                              paramsDrafts[idx] = { ...p, kind: nextKind as ParamKind, value: nextValue };
                              applyParamScalar(p.key, nextKind as any, nextValue);
                            }}
                          >
                            <option value="string">string</option>
                            <option value="number">number</option>
                            <option value="boolean">boolean</option>
                            <option value="null">null</option>
                          </select>
                        {/if}

                        <button
                          type="button"
                          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                          title={"移除 params." + p.key + "(从 YAML 删除)"}
                          aria-label={"remove params." + p.key}
                          onclick={() => removeParam(p.key)}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}

              <div class="grid grid-cols-12 gap-2">
                <input
                  class="sx-input-sm col-span-12"
                  name="add_param_key"
                  placeholder="key(例:since_days)"
                  bind:value={addParamKeyDraft}
                  onkeydown={(e) => {
                    if ((e as KeyboardEvent).key === "Enter") onAddParam();
                  }}
                />
                <select
                  class="sx-select h-8 col-span-4"
                  name="add_param_kind"
                  bind:value={addParamKindDraft}
                  aria-label="add param type"
                  onchange={() => {
                    if (addParamKindDraft === "boolean" && addParamValueDraft.trim().toLowerCase() !== "false") addParamValueDraft = "true";
                    if (addParamKindDraft === "null") addParamValueDraft = "";
                  }}
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="boolean">boolean</option>
                  <option value="null">null</option>
                </select>

                {#if addParamKindDraft === "null"}
                  <div class="col-span-6 flex h-8 items-center rounded-md border bg-white px-2 text-[11px] text-slate-600">null</div>
                {:else if addParamKindDraft === "boolean"}
                  <select
                    class="sx-select h-8 col-span-6"
                    name="add_param_value_bool"
                    value={addParamValueDraft.trim().toLowerCase() === "false" ? "false" : "true"}
                    aria-label="add param value"
                    onchange={(e) => {
                      addParamValueDraft = (e.target as HTMLSelectElement).value;
                    }}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                {:else}
                  <input
                    class="sx-input-sm col-span-6"
                    name="add_param_value"
                    placeholder="value"
                    inputmode={addParamKindDraft === "number" ? "decimal" : "text"}
                    bind:value={addParamValueDraft}
                    onkeydown={(e) => {
                      if ((e as KeyboardEvent).key === "Enter") onAddParam();
                    }}
                  />
                {/if}

                <Button
                  variant="add"
                  size="icon"
                  className="col-span-2 justify-self-end"
                  aria-label="add main source param"
                  title="添加参数"
                  on:click={onAddParam}
                />
              </div>
            </div>

            <MainSourceOrderByEditor />
          </div>
        </section>

        <MainSourceFieldsEditor />

        <RelationsEditor />

        <SourcesEditor />

        <DerivedFieldsEditor />

        <ObservabilityGuardrailsEditor />

        <section class="rounded-xl border bg-white p-3">
	          <div class="mb-2 flex items-center">
	            <button
	              type="button"
	              class="cursor-pointer text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
	              title="点击定位到 YAML"
	              onclick={() => requestJump("output")}
	            >
	              Output
	            </button>
	          </div>

	          <div class="grid grid-cols-1 gap-2">
	            <div class="group text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-output_format" class="font-medium">output.format</label>
                  <div class="flex items-center gap-1">
                    {#if !isRequired(["output", "format"]) && outputFormatPresent}
                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title="移除 output.format(从 YAML 删除)"
                        aria-label="remove output.format"
                        onclick={() => removePath(["output", "format"])}
                      >
                        ×
                      </button>
                    {/if}
	                  <SchemaHint text={helpText(["output", "format"])} label="output.format" />
                  </div>
	              </div>
	              <input
	                id="v-output_format"
	                name="output.format"
	                class="sx-input w-full"
	                bind:value={outputFormatDraft}
	                onblur={() => applyOptionalString(["output", "format"], outputFormatDraft)}
              />
            </div>

	            <div class="group text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-output_path" class="font-medium">output.path</label>
                  <div class="flex items-center gap-1">
                    {#if !isRequired(["output", "path"]) && outputPathPresent}
                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title="移除 output.path(从 YAML 删除)"
                        aria-label="remove output.path"
                        onclick={() => removePath(["output", "path"])}
                      >
                        ×
                      </button>
                    {/if}
	                  <SchemaHint text={helpText(["output", "path"])} label="output.path" />
                  </div>
	              </div>
	              <input
	                id="v-output_path"
	                name="output.path"
	                class="sx-input w-full"
	                bind:value={outputPathDraft}
	                onblur={() => applyOptionalString(["output", "path"], outputPathDraft)}
              />
            </div>

	            <div class="group text-xs text-slate-700">
	              <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-slate-500">
	                <label for="v-output_encoding" class="font-medium">output.encoding</label>
                  <div class="flex items-center gap-1">
                    {#if !isRequired(["output", "encoding"]) && outputEncodingPresent}
                      <button
                        type="button"
                        class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
                        title="移除 output.encoding(从 YAML 删除)"
                        aria-label="remove output.encoding"
                        onclick={() => removePath(["output", "encoding"])}
                      >
                        ×
                      </button>
                    {/if}
	                  <SchemaHint text={helpText(["output", "encoding"])} label="output.encoding" />
                  </div>
	              </div>
	              <input
	                id="v-output_encoding"
	                name="output.encoding"
	                class="sx-input w-full"
	                bind:value={outputEncodingDraft}
	                onblur={() => applyOptionalString(["output", "encoding"], outputEncodingDraft)}
              />
            </div>
          </div>
        </section>

        <OutputFieldsEditor />
      </div>
    </div>
  {/if}
</div>
