<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "$components/ui/badge.svelte";
  import Button from "$components/ui/button.svelte";
  import { state as appState } from "$domain/state.svelte";
  import { applyPatchResult } from "$services/patch_apply";
  import { composePatchResults } from "$services/patch_compose";
  import { loadDemandSchema } from "$services/schema";
  import { schemaDescriptionForPath } from "$services/schema_help";
  import { ensureEmptyMapAtPathDeep, removeKeyAtPath, setInlineValueAtPath, setScalarAtPathDeep } from "$services/yaml_patch";
  import SchemaHint from "$ui/components/SchemaHint.svelte";
  import { parse as parseYaml } from "yaml";

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

  const applyPatch = (out: any, title: string) => {
    const res = applyPatchResult(out, { title });
    lastError = res.ok ? "" : res.error;
  };

  const removeBlock = (path: string[]) => {
    applyPatch(removeKeyAtPath(appState.yamlText, path, { pruneEmptyParents: true }), "Remove " + path.join("."));
  };

  const ensureMap = (path: string[]) => {
    return (t: string) => ensureEmptyMapAtPathDeep(t, path, { createMissing: true });
  };

  const setScalar = (path: string[], value: string | number | boolean | null) => {
    return (t: string) => setScalarAtPathDeep(t, path, value, { createMissing: true });
  };

  const setInline = (path: string[], value: string) => {
    return (t: string) => setInlineValueAtPath(t, path, value, { createMissing: true });
  };

  const applyDebugPreset = () => {
    const out = composePatchResults(appState.yamlText, [
      ensureMap(["observability"]),
      ensureMap(["observability", "logging"]),
      setScalar(["observability", "logging", "enabled"], true),
      setScalar(["observability", "logging", "renderer"], "pretty"),
      ensureMap(["observability", "trace"]),
      setScalar(["observability", "trace", "enabled"], true),
      ensureMap(["observability", "relations"]),
      setScalar(["observability", "relations", "enabled"], true),
      setScalar(["observability", "relations", "sampling_rate"], 0.1),
      setScalar(["observability", "relations", "max_samples"], 200),
      ensureMap(["guardrails"]),
      setScalar(["guardrails", "enabled"], true),
      setScalar(["guardrails", "mode"], "quiet"),
      ensureMap(["guardrails", "loader"]),
      setScalar(["guardrails", "loader", "validate_result"], true)
    ]);
    applyPatch(out, "Preset: debug");
  };

  const applyPerfPreset = () => {
    const out = composePatchResults(appState.yamlText, [
      ensureMap(["observability"]),
      ensureMap(["observability", "performance"]),
      setScalar(["observability", "performance", "enabled"], true),
      setInline(["observability", "performance", "metrics"], "[duration, memory]"),
      setScalar(["observability", "performance", "sampling_interval"], 1),
      ensureMap(["observability", "performance", "report"]),
      setScalar(["observability", "performance", "report", "format"], "console"),
      ensureMap(["observability", "memory_opt"]),
      setScalar(["observability", "memory_opt", "enabled"], true),
      setScalar(["observability", "memory_opt", "auto_report"], true),
      ensureMap(["observability", "row_gap"]),
      setScalar(["observability", "row_gap", "enabled"], true)
    ]);
    applyPatch(out, "Preset: perf");
  };

  const applyVizPreset = () => {
    const out = composePatchResults(appState.yamlText, [
      ensureMap(["observability"]),
      ensureMap(["observability", "viz"]),
      setScalar(["observability", "viz", "enabled"], true),
      setScalar(["observability", "viz", "output_dir"], "./output"),
      setScalar(["observability", "viz", "payload_policy"], "summary"),
      setScalar(["observability", "viz", "trace_enabled"], false)
    ]);
    applyPatch(out, "Preset: viz");
  };

  const summary = $derived(() => {
    const p = parsed();
    if (!p.ok) return null;
    const data = p.data || {};
    const obs = data.observability && typeof data.observability === "object" ? data.observability : null;
    const gr = data.guardrails && typeof data.guardrails === "object" ? data.guardrails : null;

    const subEnabled = (key: string) => {
      if (!obs || typeof (obs as any)[key] !== "object") return null;
      const v = (obs as any)[key];
      if (!v || typeof v !== "object") return null;
      const raw = (v as any).enabled;
      if (typeof raw === "boolean") return raw;
      return null;
    };

    const guardEnabled = gr && typeof (gr as any).enabled === "boolean" ? Boolean((gr as any).enabled) : null;
    const guardMode = gr && typeof (gr as any).mode === "string" ? String((gr as any).mode) : "";

    return {
      observabilityPresent: Object.prototype.hasOwnProperty.call(data, "observability"),
      guardrailsPresent: Object.prototype.hasOwnProperty.call(data, "guardrails"),
      guardEnabled,
      guardMode,
      obs: {
        logging: subEnabled("logging"),
        performance: subEnabled("performance"),
        relations: subEnabled("relations"),
        viz: subEnabled("viz"),
        trace: subEnabled("trace"),
        row_gap: subEnabled("row_gap"),
        memory_opt: subEnabled("memory_opt")
      }
    };
  });

  onMount(async () => {
    try {
      demandSchema = await loadDemandSchema();
    } catch {
      demandSchema = null;
    }
  });
</script>

<section class="rounded-xl border bg-white p-3">
  <div class="mb-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-2">
      <div class="text-xs font-semibold text-slate-800">Observability / Guardrails</div>
      <SchemaHint text={helpText(["observability"])} label="observability" />
      <SchemaHint text={helpText(["guardrails"])} label="guardrails" />
      {#if summary()}
        {#if summary()!.observabilityPresent}
          <Badge variant="secondary">observability</Badge>
        {/if}
        {#if summary()!.guardrailsPresent}
          <Badge variant={summary()!.guardEnabled ? "warning" : "outline"}>guardrails{summary()!.guardEnabled ? ": on" : ""}</Badge>
        {/if}
      {/if}
    </div>
    <div class="text-[11px] text-slate-500">一键 presets · 可随时移除</div>
  </div>

  {#if lastError}
    <div class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{lastError}</div>
  {/if}

  <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
    <button
      type="button"
      class="sx-interactive group rounded-xl border bg-slate-50/40 px-3 py-2 text-left"
      onclick={applyDebugPreset}
      title="插入/更新:logging+trace+relations 采样 + guardrails(quiet)"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="text-xs font-semibold text-slate-800">Debug</div>
        <Badge variant="outline">preset</Badge>
      </div>
      <div class="mt-1 text-[11px] text-slate-600">更强日志/追踪,适合调试 relation 与字段问题.</div>
    </button>

    <button
      type="button"
      class="sx-interactive group rounded-xl border bg-slate-50/40 px-3 py-2 text-left"
      onclick={applyPerfPreset}
      title="插入/更新:performance(duration+memory)+memory_opt+row_gap"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="text-xs font-semibold text-slate-800">Perf</div>
        <Badge variant="outline">preset</Badge>
      </div>
      <div class="mt-1 text-[11px] text-slate-600">开启耗时/内存观测与摘要,适合压测与回归.</div>
    </button>

    <button
      type="button"
      class="sx-interactive group rounded-xl border bg-slate-50/40 px-3 py-2 text-left"
      onclick={applyVizPreset}
      title="插入/更新:viz 输出(output_dir=./output, payload_policy=summary)"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="text-xs font-semibold text-slate-800">Viz</div>
        <Badge variant="outline">preset</Badge>
      </div>
      <div class="mt-1 text-[11px] text-slate-600">输出 scalim-viz 事件/快照,便于可视化回放.</div>
    </button>
  </div>

  <div class="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-white px-3 py-2 text-xs">
    <div class="flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
      <span class="font-medium text-slate-700">当前</span>
      {#if summary()}
        {@const obs = summary()!.obs}
        <span class="rounded-md border bg-slate-50 px-1.5 py-0.5">logging: {obs.logging == null ? "—" : obs.logging ? "on" : "off"}</span>
        <span class="rounded-md border bg-slate-50 px-1.5 py-0.5">perf: {obs.performance == null ? "—" : obs.performance ? "on" : "off"}</span>
        <span class="rounded-md border bg-slate-50 px-1.5 py-0.5">relations: {obs.relations == null ? "—" : obs.relations ? "on" : "off"}</span>
        <span class="rounded-md border bg-slate-50 px-1.5 py-0.5">viz: {obs.viz == null ? "—" : obs.viz ? "on" : "off"}</span>
        <span class="rounded-md border bg-slate-50 px-1.5 py-0.5">trace: {obs.trace == null ? "—" : obs.trace ? "on" : "off"}</span>
      {:else}
        <span class="text-slate-500">YAML 解析失败</span>
      {/if}
    </div>

    <div class="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!summary() || !summary()!.observabilityPresent}
        on:click={() => removeBlock(["observability"])}
        title="移除 observability(从 YAML 删除)"
      >
        清除 observability
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!summary() || !summary()!.guardrailsPresent}
        on:click={() => removeBlock(["guardrails"])}
        title="移除 guardrails(从 YAML 删除)"
      >
        清除 guardrails
      </Button>
    </div>
  </div>
</section>
