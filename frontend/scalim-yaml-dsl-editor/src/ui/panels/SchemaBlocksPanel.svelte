<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$components/ui/button.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { applyPatchResult } from "$services/patch_apply";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import { loadDemandSchema, loadWorkflowSchema } from "$services/schema";
  import { buildBlocks, OverrideRegistry, applyBlockAction, type BlockAction, type EditableBlock, type JsonSchemaNode } from "$schema_blocks/index";
  import { parse as parseYaml } from "yaml";

  import BlockView from "$ui/panels/schema_blocks/BlockView.svelte";
  import RelationsCustomBlock from "$ui/panels/schema_blocks/custom/RelationsCustomBlock.svelte";
  import DerivedFieldsCustomBlock from "$ui/panels/schema_blocks/custom/DerivedFieldsCustomBlock.svelte";
  import MainSourceFieldsCustomBlock from "$ui/panels/schema_blocks/custom/MainSourceFieldsCustomBlock.svelte";
  import OutputFieldsCustomBlock from "$ui/panels/schema_blocks/custom/OutputFieldsCustomBlock.svelte";

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

  let schema = $state<JsonSchemaNode | null>(null);
  let schemaError = $state<string>("");
  let lastApplyError = $state<string>("");

  const overrides = new OverrideRegistry();
  overrides.registerExact(["relations"], {
    id: "custom-relations",
    priority: 100,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "Relations",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: [],
      custom: { component: RelationsCustomBlock, props: { yamlPath: ctx.yamlPath } }
    })
  });

  overrides.registerExact(["fields"], {
    id: "custom-fields",
    priority: 100,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "Fields",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: [],
      custom: { component: DerivedFieldsCustomBlock, props: { yamlPath: ctx.yamlPath } }
    })
  });

  overrides.registerExact(["main_source", "fields"], {
    id: "custom-main_source-fields",
    priority: 100,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "Main Source Fields",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: [],
      custom: { component: MainSourceFieldsCustomBlock, props: { yamlPath: ctx.yamlPath } }
    })
  });

  overrides.registerGlob("outputs.*.fields", {
    id: "custom-output-fields",
    priority: 100,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "Output Fields",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: [],
      custom: { component: OutputFieldsCustomBlock, props: { yamlPath: ctx.yamlPath } }
    })
  });

  const blocks = $derived((): EditableBlock[] => {
    const p = parsed();
    if (!p.ok) return [];
    if (!schema) return [];
    return buildBlocks({
      rootSchema: schema,
      schemaNode: schema,
      yamlPath: [],
      yamlData: p.data || {},
      yamlLocations: appState.yamlLocations,
      overrides
    });
  });

  const jumpToPath = (yamlPath: string[]) => {
    const key = yamlPath.join(".");
    const loc = lookupYamlLocation(key, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const onAction = (action: BlockAction, title: string) => {
    const out = applyBlockAction(appState.yamlText, action);
    const res = applyPatchResult(out, { title });
    lastApplyError = res.ok ? "" : res.error;
  };

  const loadSchema = async () => {
    schemaError = "";
    schema = null;
    const isWorkflow = String(appState.schemaHeaderPath || "").toLowerCase().includes("workflow.gen.json");
    try {
      schema = isWorkflow ? ((await loadWorkflowSchema()) as any) : ((await loadDemandSchema()) as any);
    } catch (err: any) {
      schemaError = String(err?.message || err || "Failed to load schema");
      schema = null;
    }
  };

  $effect(() => {
    appState.schemaHeaderPath;
    void loadSchema();
  });
</script>

<div class="flex h-full flex-col">
  <div class="flex items-center justify-between border-b bg-slate-50 px-3 py-2 text-xs">
    <div class="font-semibold text-slate-800">Schema Blocks</div>
    <div class="text-[11px] text-slate-500">Schema → Blocks → YAML patch</div>
  </div>

  {#if lastApplyError}
    <div class="border-b bg-red-50 px-3 py-2 text-xs text-red-700">{lastApplyError}</div>
  {/if}

  {#if !parseOk()}
    <div class="p-3 text-xs text-red-700">
      <div class="font-semibold">YAML parse error</div>
      <div class="mt-1 whitespace-pre-wrap font-mono text-[11px] text-red-600">{parseError()}</div>
      <div class="mt-2 text-slate-600">修复 YAML 后可继续使用 schema-driven 编辑.</div>
    </div>
  {:else if schemaError}
    <div class="p-3 text-xs text-red-700">
      <div class="font-semibold">Schema load error</div>
      <div class="mt-1 whitespace-pre-wrap font-mono text-[11px] text-red-600">{schemaError}</div>
      <div class="mt-2">
        <Button variant="outline" size="sm" on:click={loadSchema}>Retry</Button>
      </div>
    </div>
  {:else if !schema}
    <div class="p-3 text-xs text-slate-600">Loading schema…</div>
  {:else}
    <div class="min-h-0 flex-1 overflow-hidden">
      <div class="grid h-full grid-cols-[220px_1fr]">
        <div class="min-w-0 border-r bg-white">
          <div class="flex items-center justify-between border-b bg-slate-50 px-3 py-2 text-xs">
            <div class="font-semibold text-slate-800">Outline</div>
            <div class="text-[11px] text-slate-500">{blocks().length} sections</div>
          </div>
          <div class="min-h-0 overflow-auto p-2">
            {#if blocks().length === 0}
              <div class="px-2 py-3 text-xs text-slate-500">No blocks</div>
            {:else}
              <div class="flex flex-col gap-1">
                {#each blocks() as b (b.id)}
                  <Button variant="ghost" className="justify-between" on:click={() => jumpToPath(b.yamlPath)}>
                    <span class="text-slate-800 truncate">{b.title}{b.required ? "*" : ""}</span>
                    {#if !b.present}
                      <span class="text-[10px] text-slate-400">missing</span>
                    {:else}
                      <span class="text-[10px] text-slate-400">ok</span>
                    {/if}
                  </Button>
                {/each}
              </div>
            {/if}
          </div>
        </div>

        <div class="min-w-0 overflow-auto bg-slate-50 p-3">
          <div class="flex flex-col gap-3">
            {#each blocks() as b (b.id)}
              <BlockView block={b} depth={0} {onAction} onJumpToYaml={jumpToPath} />
            {/each}
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
