<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import Button from "$components/ui/button.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { applyPatchResult } from "$services/patch_apply";
  import { collectFieldCandidates, computeHeaderPreview, readOutputFields, type FieldCandidate, type OutputHeaderBy } from "$services/output_fields";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import {
    insertOutputFieldAliasAt,
    insertOutputFieldIdAt,
    moveOutputField,
    removeKeyAtPath,
    removeOutputFieldAt,
    setScalarAtPathDeep
  } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";

  let search = $state<string>("");
  let customFieldId = $state<string>("");
  let demandSchema = $state<any | null>(null);
  let lastError = $state<string>("");

  const fieldsHelp = $derived(() => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, ["output", "fields"]);
  });

  const headerByHelp = $derived(() => {
    if (!demandSchema) return "";
    return schemaDescriptionForPath(demandSchema, ["output", "header_fields_output_by"]);
  });

  const current = $derived(() => readOutputFields(appState.yamlText, appState.yamlLocations));
  const currentOk = $derived(() => current().ok);
  const currentHeaderBy = $derived(() => {
    const cur = current();
    return cur.ok ? cur.headerBy : "field_id";
  });
  const currentItems = $derived(() => {
    const cur = current();
    return cur.ok ? cur.items : [];
  });
  const currentError = $derived(() => {
    const cur = current();
    return cur.ok ? "" : cur.error;
  });
  const fieldsPresent = $derived(() => Boolean(appState.yamlLocations && (appState.yamlLocations as any)["output.fields"]));
  const headerByPresent = $derived(() => Boolean(appState.yamlLocations && (appState.yamlLocations as any)["output.header_fields_output_by"]));
  const candidates = $derived(() => collectFieldCandidates(appState.yamlText));

  const visibleCandidates = $derived(() => {
    const q = search.trim().toLowerCase();
    if (!q) return candidates().slice(0, 30);
    const out: FieldCandidate[] = [];
    for (const item of candidates()) {
      const hay = (item.fieldId + " " + (item.anchor || "") + " " + (item.name || "") + " " + item.origin).toLowerCase();
      if (hay.includes(q)) out.push(item);
      if (out.length >= 30) break;
    }
    return out;
  });

  const headerPreview = $derived(() => {
    const cur = current();
    if (!cur.ok) return { headers: [] as string[], duplicates: [] as Array<{ value: string; count: number }> };
    return computeHeaderPreview(cur.headerBy, cur.items);
  });

  let dragging = $state<number | null>(null);
  let dragOver = $state<number | null>(null);

  const applyPatch = (out: any, title: string) => {
    const res = applyPatchResult(out, { title });
    lastError = res.ok ? "" : res.error;
  };

  const removePath = (path: string[]) => {
    applyPatch(removeKeyAtPath(appState.yamlText, path, { pruneEmptyParents: true }), "Remove " + path.join("."));
  };

  const jumpToFields = () => {
    const loc = lookupYamlLocation("output.fields", appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const onAddCandidate = (cand: FieldCandidate) => {
    const cur = current();
    const items = cur.ok ? cur.items : [];
    const idx = items.length;
    if (cand.anchor) {
      applyPatch(insertOutputFieldAliasAt(appState.yamlText, idx, cand.anchor), "Insert output.fields[" + String(idx) + "]");
      return;
    }
    applyPatch(insertOutputFieldIdAt(appState.yamlText, idx, cand.fieldId), "Insert output.fields[" + String(idx) + "]");
  };

  const onAddCustom = () => {
    const id = customFieldId.trim();
    if (!id) return;
    const cur = current();
    const items = cur.ok ? cur.items : [];
    applyPatch(insertOutputFieldIdAt(appState.yamlText, items.length, id), "Insert output.fields[" + String(items.length) + "]");
    customFieldId = "";
  };

  const onRemove = (idx: number) => {
    applyPatch(removeOutputFieldAt(appState.yamlText, idx), "Remove output.fields[" + String(idx) + "]");
  };

  const onMove = (from: number, to: number) => {
    applyPatch(moveOutputField(appState.yamlText, from, to), "Move output.fields[" + String(from) + "]");
  };

  const onHeaderBy = (value: string) => {
    const v: OutputHeaderBy = value === "name" ? "name" : "field_id";
    applyPatch(
      setScalarAtPathDeep(appState.yamlText, ["output", "header_fields_output_by"], v, { createMissing: true }),
      "Update output.header_fields_output_by"
    );
  };

  const onDragStart = (idx: number) => {
    dragging = idx;
    dragOver = idx;
  };

  const onDragOver = (idx: number, event: DragEvent) => {
    event.preventDefault();
    dragOver = idx;
  };

  const onDrop = (idx: number) => {
    if (dragging == null) return;
    if (dragging !== idx) onMove(dragging, idx);
    dragging = null;
    dragOver = null;
  };

  const onDragEnd = () => {
    dragging = null;
    dragOver = null;
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
  <div class="mb-2 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="cursor-pointer text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
        title="点击定位到 YAML"
        onclick={jumpToFields}
      >
        Output Fields
      </button>
      {#if fieldsPresent()}
        <button
          type="button"
          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title="移除 output.fields(从 YAML 删除)"
          aria-label="remove output.fields"
          onclick={() => removePath(["output", "fields"])}
        >
          ×
        </button>
      {/if}
      <SchemaHint text={fieldsHelp()} label="output.fields" />
      {#if currentOk()}
        <Badge variant="outline">{currentItems().length}</Badge>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      {#if currentOk()}
        <select
          class="sx-select"
          name="header_fields_output_by"
          value={currentHeaderBy()}
          onchange={(e) => onHeaderBy((e.target as HTMLSelectElement).value)}
          aria-label="header_fields_output_by"
        >
          <option value="field_id">header: field_id</option>
          <option value="name">header: name</option>
        </select>
        {#if headerByPresent()}
          <button
            type="button"
            class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
            title="移除 output.header_fields_output_by(恢复默认)"
            aria-label="remove output.header_fields_output_by"
            onclick={() => removePath(["output", "header_fields_output_by"])}
          >
            ×
          </button>
        {/if}
        <SchemaHint text={headerByHelp()} label="output.header_fields_output_by" />
      {/if}
    </div>
  </div>

  {#if lastError}
    <div class="mb-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-700">{lastError}</div>
  {/if}

  {#if !currentOk()}
    <div class="text-xs text-red-700">{currentError()}</div>
  {:else}
    {#if headerPreview().duplicates.length > 0 && currentHeaderBy() === "name"}
      <div class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <div class="flex items-center justify-between">
          <div>检测到表头重复(header_fields_output_by=name)</div>
          <Button variant="outline" size="sm" on:click={() => onHeaderBy("field_id")}>切换到 field_id</Button>
        </div>
        <div class="mt-1 text-[11px] text-amber-700">
          {#each headerPreview().duplicates.slice(0, 4) as d (d.value)}
            <span class="mr-2">{d.value} ×{d.count}</span>
          {/each}
        </div>
      </div>
    {/if}

    <div class="flex flex-col gap-1">
      {#if currentItems().length === 0}
        <div class="rounded-lg border bg-slate-50 px-3 py-2 text-xs text-slate-600">暂无 output.fields(可从下方添加)</div>
      {:else}
        {#each currentItems() as item, idx (item.id)}
          <div
            class="sx-interactive flex cursor-grab items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-xs active:cursor-grabbing"
            draggable="true"
            role="listitem"
            ondragstart={() => onDragStart(idx)}
            ondragover={(e) => onDragOver(idx, e)}
            ondrop={() => onDrop(idx)}
            ondragend={onDragEnd}
            class:border-sky-300={dragOver === idx}
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <Badge variant={item.kind === "alias" ? "outline" : item.kind === "map" ? "warning" : "secondary"}>{item.kind}</Badge>
                <span class="truncate text-slate-800">{item.label}</span>
                {#if item.line}
                  <span class="text-[11px] text-slate-500">L{item.line}</span>
                {/if}
              </div>
              {#if item.raw}
                <div class="mt-1 truncate font-mono text-[11px] text-slate-500">{item.raw.trim()}</div>
              {/if}
            </div>

            <div class="flex items-center gap-1">
              <Button variant="ghost" size="icon" disabled={idx === 0} on:click={() => onMove(idx, idx - 1)}>↑</Button>
              <Button
                variant="ghost"
                size="icon"
                disabled={idx === currentItems().length - 1}
                on:click={() => onMove(idx, idx + 1)}
              >
                ↓
              </Button>
              <Button variant="outline" size="sm" on:click={() => onRemove(idx)}>移除</Button>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="mt-3 grid grid-cols-1 gap-3">
      <div class="rounded-lg border bg-slate-50 p-3">
        <div class="mb-2 text-xs font-semibold text-slate-800">添加字段</div>

        <div class="flex items-center gap-2">
          <input
            class="sx-input flex-1"
            name="output_fields_search"
            placeholder="搜索 field_id / anchor / name / origin"
            bind:value={search}
          />
        </div>

        <div class="mt-2 max-h-[220px] overflow-auto rounded-md border bg-white">
          {#if visibleCandidates().length === 0}
            <div class="px-3 py-2 text-xs text-slate-500">无匹配</div>
          {:else}
            <div class="flex flex-col">
              {#each visibleCandidates() as cand (cand.id)}
                <div class="sx-interactive flex items-center justify-between gap-2 border-b px-3 py-2 text-xs last:border-b-0">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-slate-800">
                      {cand.fieldId}
                      {#if cand.name}
                        <span class="text-slate-500"> — {cand.name}</span>
                      {/if}
                    </div>
                    <div class="truncate font-mono text-[11px] text-slate-500">
                      {cand.origin}{cand.anchor ? "  &" + cand.anchor : ""}
                    </div>
                  </div>
                  <Button
                    variant="add"
                    size="icon"
                    aria-label={"add output field " + cand.fieldId}
                    title={cand.anchor ? "添加 *" + cand.anchor : "添加 field_id"}
                    on:click={() => onAddCandidate(cand)}
                  />
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <div class="mt-3 flex items-center gap-2">
          <input
            class="sx-input flex-1"
            name="custom_field_id"
            placeholder={"自定义 field_id (添加为 {field_id: ...})"}
            bind:value={customFieldId}
          />
          <Button variant="add" size="icon" aria-label="add custom output field" title="添加自定义字段" on:click={onAddCustom} />
        </div>
      </div>

      <div class="rounded-lg border bg-white p-3">
        <div class="mb-2 text-xs font-semibold text-slate-800">表头预览</div>
        <div class="grid grid-cols-2 gap-2 text-[11px]">
          {#each headerPreview().headers.slice(0, 12) as h, i (i)}
            <div class="truncate rounded-md border bg-slate-50 px-2 py-1 font-mono text-slate-700">
              {i + 1}. {h}
            </div>
          {/each}
        </div>
        {#if headerPreview().headers.length > 12}
          <div class="mt-2 text-[11px] text-slate-500">... 共 {headerPreview().headers.length} 个</div>
        {/if}
      </div>
    </div>
  {/if}
</section>
