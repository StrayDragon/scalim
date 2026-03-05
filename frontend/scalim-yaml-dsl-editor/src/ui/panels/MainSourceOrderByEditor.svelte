<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import Button from "$components/ui/button.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import { insertStringItemAtPath, moveSeqItemAtPath, removeKeyAtPath, removeSeqItemAtPath, setScalarAtSeqIndex } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
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

  let demandSchema = $state<any | null>(null);
  const helpText = $derived(() => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, ["main_source", "order_by"]);
  });

  let lastError = $state<string>("");
  let orderByDrafts = $state<string[]>([]);
  let orderByPresent = $state<boolean>(false);
  let addDraft = $state<string>("");

  const syncDrafts = () => {
    const p = parsed();
    if (!p.ok) return;
    const data = p.data || {};
    const mainSource = data.main_source && typeof data.main_source === "object" ? data.main_source : {};
    orderByPresent = Object.prototype.hasOwnProperty.call(mainSource, "order_by");
    const ob = Array.isArray(mainSource.order_by) ? mainSource.order_by : [];
    orderByDrafts = ob.map((x: any) => String(x ?? ""));
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
    const loc = lookupYamlLocation("main_source.order_by", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const removeOrderBy = () => {
    applyPatch(removeKeyAtPath(appState.yamlText, ["main_source", "order_by"], { pruneEmptyParents: true }), "Remove main_source.order_by");
  };

  const onAdd = () => {
    const v = addDraft.trim();
    if (!v) return;
    applyPatch(
      insertStringItemAtPath(appState.yamlText, ["main_source", "order_by"], orderByDrafts.length, v),
      "Insert main_source.order_by[" + String(orderByDrafts.length) + "]"
    );
    addDraft = "";
  };

  const onRemove = (idx: number) => {
    applyPatch(removeSeqItemAtPath(appState.yamlText, ["main_source", "order_by"], idx), "Remove main_source.order_by[" + String(idx) + "]");
  };

  const onMove = (from: number, to: number) => {
    applyPatch(
      moveSeqItemAtPath(appState.yamlText, ["main_source", "order_by"], from, to),
      "Move main_source.order_by[" + String(from) + "]"
    );
  };

  const onApplyItem = (idx: number) => {
    const raw = (orderByDrafts[idx] || "").trim();
    if (!raw) {
      onRemove(idx);
      return;
    }
    applyPatch(setScalarAtSeqIndex(appState.yamlText, ["main_source", "order_by"], idx, raw), "Update main_source.order_by[" + String(idx) + "]");
  };

  onMount(async () => {
    try {
      demandSchema = await loadDemandSchema();
    } catch {
      demandSchema = null;
    }
  });
</script>

<div class="rounded-lg border bg-slate-50/60 p-2">
  <div class="mb-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="cursor-pointer text-[11px] font-medium text-slate-700 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
        title="点击定位到 YAML"
        onclick={requestJump}
      >
        main_source.order_by
      </button>
      {#if orderByPresent}
        <button
          type="button"
          class="rounded-md border bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title="移除 main_source.order_by(从 YAML 删除)"
          aria-label="remove main_source.order_by"
          onclick={removeOrderBy}
        >
          ×
        </button>
      {/if}
      <SchemaHint text={helpText()} label="main_source.order_by" />
      <Badge variant="outline">{orderByDrafts.length}</Badge>
    </div>
    <div class="text-[10px] text-slate-400">支持前缀 - 表示 desc</div>
  </div>

  {#if lastError}
    <div class="mb-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-700">{lastError}</div>
  {/if}

  {#if orderByDrafts.length === 0}
    <div class="mb-2 rounded-md border bg-white px-2 py-2 text-[11px] text-slate-600">暂无 order_by(可在下方添加)</div>
  {:else}
    <div class="mb-2 flex flex-col gap-1">
      {#each orderByDrafts as item, idx (idx)}
        <div class="group sx-interactive flex items-center gap-2 rounded-md border bg-white px-2 py-2 text-xs">
          <input
            class="sx-input h-8 flex-1"
            name={"order_by." + idx}
            value={item}
            placeholder="field_id 或 -field_id"
            oninput={(e) => {
              orderByDrafts[idx] = (e.target as HTMLInputElement).value;
            }}
            onkeydown={(e) => {
              if ((e as KeyboardEvent).key === "Enter") onApplyItem(idx);
            }}
            onblur={() => onApplyItem(idx)}
          />
          <button
            type="button"
            class="rounded-md border bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background disabled:opacity-40"
            aria-label={"move order_by." + idx + " up"}
            title="上移"
            disabled={idx === 0}
            onclick={() => onMove(idx, idx - 1)}
          >
            ↑
          </button>
          <button
            type="button"
            class="rounded-md border bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background disabled:opacity-40"
            aria-label={"move order_by." + idx + " down"}
            title="下移"
            disabled={idx === orderByDrafts.length - 1}
            onclick={() => onMove(idx, idx + 1)}
          >
            ↓
          </button>
          <button
            type="button"
            class="rounded-md border bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-600 shadow-sm hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
            aria-label={"remove order_by." + idx}
            title="移除"
            onclick={() => onRemove(idx)}
          >
            ×
          </button>
        </div>
      {/each}
    </div>
  {/if}

  <div class="grid grid-cols-12 gap-2">
    <input
      class="sx-input col-span-10"
      name="add_order_by"
      placeholder="新增排序字段,例如 created_at 或 -created_at"
      bind:value={addDraft}
      onkeydown={(e) => {
        if ((e as KeyboardEvent).key === "Enter") onAdd();
      }}
    />
    <Button
      variant="add"
      size="icon"
      className="col-span-2 justify-self-end"
      aria-label="add order_by"
      title="添加排序项"
      on:click={onAdd}
    />
  </div>
</div>
