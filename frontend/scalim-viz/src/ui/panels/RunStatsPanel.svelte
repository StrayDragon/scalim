<script lang="ts">
  import { onMount, tick } from "svelte";
  import Badge from "$ui/badge.svelte";
  import Button from "$ui/button.svelte";
  import {
    isHighImpactRunStatsProfile,
    runStatsProfileLabel,
    type RunStatsStages
  } from "$domain/runStats";
  import { startPanelDrag, state } from "$domain/state.svelte";

  let root: HTMLDivElement | null = null;

  const hasStats = () => state.runStatsStatus === "loaded" && Boolean(state.runStats);
  const hasInvalid = () => state.runStatsStatus === "invalid";
  const isAvailable = () => hasStats() || hasInvalid();

  const profile = () => runStatsProfileLabel(state.runStats);
  const highImpact = () => isHighImpactRunStatsProfile(profile());

  const fmt = (value: number | null | undefined, digits = 3) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return Number(value).toFixed(digits);
  };

  const stageEntries = (stages: RunStatsStages | null | undefined) => {
    const keys = ["loader", "compute", "write", "stream"] as const;
    return keys
      .map((key) => ({ key, value: Number(stages?.[key] ?? 0) }))
      .filter((row) => Number.isFinite(row.value));
  };

  const stageSum = (stages: RunStatsStages | null | undefined) => {
    return stageEntries(stages).reduce((acc, row) => acc + row.value, 0);
  };

  const topLoaders = () => {
    const rows = [...(state.runStats?.loaders ?? [])];
    rows.sort((a, b) => Number(b.total_s ?? 0) - Number(a.total_s ?? 0));
    return rows.slice(0, 8);
  };

  const nodes = () => state.runStats?.nodes ?? [];

  const attribution = () => {
    const notes = state.runStats?.notes ?? {};
    const write = notes.write_stage_attribution;
    return typeof write === "string" ? write : "";
  };

  const clampIntoView = async () => {
    await tick();
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 12;
    const safeTop = Math.max(margin, state.panelDockTop);
    let dx = 0;
    let dy = 0;
    if (rect.left < margin) dx = margin - rect.left;
    if (rect.right > vw - margin) dx = vw - margin - rect.right;
    if (rect.top < safeTop) dy = safeTop - rect.top;
    if (rect.bottom > vh - margin) dy = vh - margin - rect.bottom;
    if (!dx && !dy) return;
    state.runStatsOffset = { x: state.runStatsOffset.x + dx, y: state.runStatsOffset.y + dy };
  };

  const openPanel = async () => {
    state.runStatsOpen = true;
    await clampIntoView();
  };

  onMount(() => {
    void clampIntoView();
    const onResize = () => {
      if (!state.runStatsOpen) return;
      void clampIntoView();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  });
</script>

{#if isAvailable() && !state.runStatsOpen}
  <div
    class="absolute left-4 z-20"
    style={`top: ${state.panelDockTop}px; transform: translate(${state.runStatsOffset.x}px, ${state.runStatsOffset.y}px);`}
  >
    <Button variant="outline" size="sm" title="打开 run_stats 摘要" on:click={openPanel}>
      Run Stats
      {#if hasInvalid()}
        <span class="ml-1 text-amber-600">!</span>
      {/if}
    </Button>
  </div>
{/if}

{#if isAvailable() && state.runStatsOpen}
  <div
    bind:this={root}
    class="absolute left-4 z-20 flex max-h-[min(70vh,640px)] w-[min(420px,calc(100vw-2rem))] flex-col gap-3 overflow-hidden rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm backdrop-blur"
    style={`top: ${state.panelDockTop}px; transform: translate(${state.runStatsOffset.x}px, ${state.runStatsOffset.y}px);`}
    on:pointerdown={(event) => startPanelDrag("runStats", event, root)}
  >
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <div class="text-sm font-semibold text-slate-800">Run Stats</div>
          {#if hasStats() && profile()}
            <Badge variant={highImpact() ? "warning" : "secondary"}>{profile()}</Badge>
          {/if}
          {#if hasInvalid()}
            <Badge variant="destructive">schema?</Badge>
          {/if}
        </div>
        <div class="mt-1 text-[11px] text-slate-500">
          sibling <span class="font-mono">run_stats.json</span>（不嵌入 snapshot）
        </div>
      </div>
      <Button variant="ghost" size="sm" on:click={() => (state.runStatsOpen = false)}>关闭</Button>
    </div>

    {#if hasInvalid()}
      <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        找到文件但不是 <span class="font-mono">scalim_run_stats/v1</span>，已忽略。
      </div>
    {:else if hasStats() && state.runStats}
      {#if highImpact()}
        <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          高影响 profile（debug/probe）：墙钟含观测税；日常请用 bench。阶段和 ≠ 墙钟。
        </div>
      {/if}

      <div class="grid grid-cols-2 gap-2 text-xs text-slate-700">
        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
          <div class="text-[10px] uppercase tracking-wide text-slate-400">pipeline</div>
          <div class="font-mono">{fmt(state.runStats.pipeline?.total_duration_s)}s</div>
          <div class="text-[11px] text-slate-500">
            nodes {state.runStats.pipeline?.node_count ?? nodes().length} · rows
            {state.runStats.pipeline?.total_rows_in ?? "—"}
          </div>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
          <div class="text-[10px] uppercase tracking-wide text-slate-400">stages Σ</div>
          <div class="font-mono">{fmt(stageSum(state.runStats.stages_total))}s</div>
          <div class="text-[11px] text-slate-500">归因窗；非墙钟</div>
        </div>
      </div>

      <div>
        <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">stages_total</div>
        <div class="flex flex-col gap-1">
          {#each stageEntries(state.runStats.stages_total) as row}
            <div class="flex items-center justify-between gap-2 text-xs">
              <span class="font-mono text-slate-600">{row.key}</span>
              <span class="font-mono text-slate-800">{fmt(row.value)}s</span>
            </div>
          {/each}
        </div>
        {#if attribution()}
          <div class="mt-1 text-[11px] text-slate-500">
            write attribution: <span class="font-mono">{attribution()}</span>
          </div>
        {/if}
      </div>

      {#if nodes().length}
        <div class="min-h-0 overflow-auto">
          <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">nodes[]</div>
          <table class="w-full border-collapse text-[11px]">
            <thead>
              <tr class="text-left text-slate-400">
                <th class="py-0.5 font-normal">#</th>
                <th class="py-0.5 font-normal">dur</th>
                <th class="py-0.5 font-normal">L</th>
                <th class="py-0.5 font-normal">C</th>
                <th class="py-0.5 font-normal">W</th>
              </tr>
            </thead>
            <tbody>
              {#each nodes() as node, idx}
                <tr class="border-t border-slate-100 font-mono text-slate-700">
                  <td class="py-0.5">{idx}</td>
                  <td class="py-0.5">{fmt(node.pipeline?.total_duration_s, 2)}</td>
                  <td class="py-0.5">{fmt(node.stages_total?.loader, 2)}</td>
                  <td class="py-0.5">{fmt(node.stages_total?.compute, 2)}</td>
                  <td class="py-0.5">{fmt(node.stages_total?.write, 2)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      {#if topLoaders().length}
        <div class="min-h-0 overflow-auto">
          <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">loaders (top)</div>
          <table class="w-full border-collapse text-[11px]">
            <thead>
              <tr class="text-left text-slate-400">
                <th class="py-0.5 font-normal">name</th>
                <th class="py-0.5 font-normal">s</th>
                <th class="py-0.5 font-normal">calls</th>
              </tr>
            </thead>
            <tbody>
              {#each topLoaders() as loader}
                <tr class="border-t border-slate-100 font-mono text-slate-700">
                  <td class="max-w-[180px] truncate py-0.5" title={loader.name}>{loader.name || "—"}</td>
                  <td class="py-0.5">{fmt(loader.total_s, 3)}</td>
                  <td class="py-0.5">{loader.calls ?? "—"}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      {#if state.runStats.memory?.peak_mb != null}
        <div class="text-[11px] text-slate-500">
          memory peak: <span class="font-mono">{fmt(state.runStats.memory.peak_mb, 1)} MB</span>
        </div>
      {/if}
    {/if}
  </div>
{/if}
