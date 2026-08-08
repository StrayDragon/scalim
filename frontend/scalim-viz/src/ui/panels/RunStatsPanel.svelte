<script lang="ts">
  import { onMount, tick } from "svelte";
  import Badge from "$ui/badge.svelte";
  import Button from "$ui/button.svelte";
  import {
    isHighImpactRunStatsProfile,
    resolveGraphNodeIdsForLoader,
    resolveGraphNodeIdsForRunStatsNode,
    runStatsNodeLabel,
    runStatsProfileLabel,
    type RunStatsNode,
    type RunStatsOutput,
    type RunStatsStages
  } from "$domain/runStats";
  import { revealNodesByIds, startPanelDrag, state as viz } from "$domain/state.svelte";
  import StagesStackedChart from "../charts/StagesStackedChart.svelte";
  import LoadersBarChart from "../charts/LoadersBarChart.svelte";

  let root = $state<HTMLDivElement | null>(null);
  /** null = overall run_stats; number = nodes[index] drill-down */
  let focusNodeIndex = $state<number | null>(null);

  const hasStats = () => viz.runStatsStatus === "loaded" && Boolean(viz.runStats);
  const hasInvalid = () => viz.runStatsStatus === "invalid";
  const isAvailable = () => hasStats() || hasInvalid();

  const profile = () => runStatsProfileLabel(viz.runStats);
  const highImpact = () => isHighImpactRunStatsProfile(profile());

  const fmt = (value: number | null | undefined, digits = 3) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return Number(value).toFixed(digits);
  };

  const stageSum = (stages: RunStatsStages | null | undefined) => {
    const keys = ["loader", "compute", "write", "stream"] as const;
    return keys.reduce((acc, key) => acc + Number(stages?.[key] ?? 0), 0);
  };

  const nodes = () => viz.runStats?.nodes ?? [];

  const focusedNode = (): RunStatsNode | null => {
    if (focusNodeIndex == null) return null;
    return nodes()[focusNodeIndex] ?? null;
  };

  const focusLabel = () => {
    const node = focusedNode();
    if (!node || focusNodeIndex == null) return "";
    return runStatsNodeLabel(node, focusNodeIndex);
  };

  const sortLoaders = (list: NonNullable<RunStatsNode["loaders"]>) => {
    const rows = [...(list ?? [])];
    rows.sort((a, b) => Number(b.total_s ?? 0) - Number(a.total_s ?? 0));
    return rows.slice(0, 8);
  };

  const topLoaders = () => {
    const node = focusedNode();
    if (node) return sortLoaders(node.loaders ?? []);
    return sortLoaders(viz.runStats?.loaders ?? []);
  };

  const focusOutputs = (): RunStatsOutput[] => {
    const node = focusedNode();
    if (!node) return [];
    const rows = [...(node.outputs ?? [])];
    rows.sort((a, b) => Number(b.duration_s ?? 0) - Number(a.duration_s ?? 0));
    return rows;
  };

  const attribution = () => {
    const notes = viz.runStats?.notes ?? {};
    const write = notes.write_stage_attribution;
    return typeof write === "string" ? write : "";
  };

  const graphNodeIds = () => viz.nodes.map((node) => String(node.id));

  const clearFocus = () => {
    focusNodeIndex = null;
  };

  const enterFocus = (nodeIndex: number) => {
    if (nodeIndex < 0 || nodeIndex >= nodes().length) return;
    focusNodeIndex = nodeIndex;
    const node = nodes()[nodeIndex];
    const ids = resolveGraphNodeIdsForRunStatsNode(node, graphNodeIds(), nodeIndex);
    revealNodesByIds(ids);
  };

  const onStageRowClick = (payload: {
    kind: "total" | "node";
    nodeIndex: number | null;
    label: string;
  }) => {
    if (payload.kind === "total") {
      clearFocus();
      return;
    }
    if (payload.nodeIndex == null) return;
    enterFocus(payload.nodeIndex);
  };

  const onLoaderClick = (name: string) => {
    const scope = focusedNode() ? [focusedNode()!] : nodes();
    const ids = resolveGraphNodeIdsForLoader(name, graphNodeIds(), scope);
    revealNodesByIds(ids);
  };

  const clampIntoView = async () => {
    await tick();
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 12;
    const safeTop = Math.max(margin, viz.panelDockTop);
    let dx = 0;
    let dy = 0;
    if (rect.left < margin) dx = margin - rect.left;
    if (rect.right > vw - margin) dx = vw - margin - rect.right;
    if (rect.top < safeTop) dy = safeTop - rect.top;
    if (rect.bottom > vh - margin) dy = vh - margin - rect.bottom;
    if (!dx && !dy) return;
    viz.runStatsOffset = { x: viz.runStatsOffset.x + dx, y: viz.runStatsOffset.y + dy };
  };

  const openPanel = async () => {
    viz.runStatsOpen = true;
    await clampIntoView();
  };

  const closePanel = () => {
    viz.runStatsOpen = false;
    clearFocus();
  };

  let lastStatsRef: typeof viz.runStats = null;
  $effect(() => {
    const next = viz.runStats;
    if (next !== lastStatsRef) {
      lastStatsRef = next;
      clearFocus();
    }
  });

  onMount(() => {
    void clampIntoView();
    const onResize = () => {
      if (!viz.runStatsOpen) return;
      void clampIntoView();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  });
</script>

{#if isAvailable() && !viz.runStatsOpen}
  <div
    class="fixed left-4 z-20"
    style={`top: ${viz.panelDockTop}px; transform: translate(${viz.runStatsOffset.x}px, ${viz.runStatsOffset.y}px);`}
  >
    <Button variant="outline" size="sm" title="打开 run_stats 摘要" on:click={openPanel}>
      Run Stats
      {#if hasInvalid()}
        <span class="ml-1 text-amber-600">!</span>
      {/if}
    </Button>
  </div>
{/if}

{#if isAvailable() && viz.runStatsOpen}
  <div
    bind:this={root}
    class="fixed left-4 z-20 flex max-h-[min(78vh,720px)] w-[min(440px,calc(100vw-2rem))] flex-col gap-3 overflow-hidden rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm backdrop-blur"
    style={`top: ${viz.panelDockTop}px; transform: translate(${viz.runStatsOffset.x}px, ${viz.runStatsOffset.y}px);`}
    onpointerdown={(event) => startPanelDrag("runStats", event, root)}
    role="region"
    aria-label="Run Stats"
  >
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <div class="text-sm font-semibold text-slate-800">Run Stats</div>
          {#if hasStats() && profile()}
            <Badge variant={highImpact() ? "warning" : "secondary"}>{profile()}</Badge>
          {/if}
          {#if focusedNode()}
            <Badge variant="outline">{focusLabel()}</Badge>
          {/if}
          {#if hasInvalid()}
            <Badge variant="destructive">schema?</Badge>
          {/if}
        </div>
        <div class="mt-1 text-[11px] text-slate-500">
          {#if focusedNode()}
            demand 下钻 · sibling <span class="font-mono">run_stats.json</span>
          {:else}
            sibling <span class="font-mono">run_stats.json</span>（点 stages 行下钻）
          {/if}
        </div>
      </div>
      <Button variant="ghost" size="sm" on:click={closePanel}>关闭</Button>
    </div>

    {#if hasInvalid()}
      <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        找到文件但不是 <span class="font-mono">scalim_run_stats/v1</span>，已忽略。
      </div>
    {:else if hasStats() && viz.runStats}
      <div class="min-h-0 flex-1 space-y-3 overflow-auto pr-0.5">
        {#if highImpact()}
          <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            高影响 profile（debug/probe）：墙钟含观测税；日常请用 bench。阶段和 ≠ 墙钟。
          </div>
        {/if}

        {#if focusedNode()}
          {@const node = focusedNode()!}
          <div class="flex items-center justify-between gap-2" data-no-drag>
            <div class="text-[11px] text-slate-600">
              范围: <span class="font-mono font-medium text-slate-800">{focusLabel()}</span>
            </div>
            <Button variant="outline" size="sm" on:click={clearFocus}>返回整体</Button>
          </div>

          <div class="grid grid-cols-2 gap-2 text-xs text-slate-700">
            <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
              <div class="text-[10px] uppercase tracking-wide text-slate-400">wall (node)</div>
              <div class="font-mono">{fmt(node.pipeline?.total_duration_s)}s</div>
              <div class="text-[11px] text-slate-500">
                batches {node.pipeline?.total_batches ?? "—"} · rows {node.pipeline?.total_rows_in ?? "—"}
              </div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
              <div class="text-[10px] uppercase tracking-wide text-slate-400">stages Σ</div>
              <div class="font-mono">{fmt(stageSum(node.stages_total))}s</div>
              <div class="text-[11px] text-slate-500">归因窗；非墙钟</div>
            </div>
          </div>

          <div data-no-drag>
            <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">stages</div>
            <StagesStackedChart includeTotal={false} nodes={[node]} />
            {#if attribution()}
              <div class="mt-1 text-[11px] text-slate-500">
                write attribution: <span class="font-mono">{attribution()}</span>
              </div>
            {/if}
          </div>

          {#if topLoaders().length}
            <div data-no-drag>
              <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">loaders (this demand)</div>
              <LoadersBarChart loaders={topLoaders()} onBarClick={onLoaderClick} />
            </div>
          {/if}

          {#if focusOutputs().length}
            <div data-no-drag>
              <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">outputs (this demand)</div>
              <div class="overflow-hidden rounded-lg border border-slate-200">
                <table class="w-full text-left text-[11px] text-slate-700">
                  <thead class="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-400">
                    <tr>
                      <th class="px-2 py-1 font-medium">target</th>
                      <th class="px-2 py-1 font-medium">s</th>
                      <th class="px-2 py-1 font-medium">rows</th>
                      <th class="px-2 py-1 font-medium">err</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each focusOutputs() as output}
                      <tr class="border-t border-slate-100">
                        <td class="max-w-[9rem] truncate px-2 py-1 font-mono" title={String(output.target_id ?? "")}>
                          {output.target_id ?? "—"}
                        </td>
                        <td class="px-2 py-1 font-mono">{fmt(output.duration_s)}</td>
                        <td class="px-2 py-1 font-mono">{output.rows ?? "—"}</td>
                        <td class="px-2 py-1 font-mono">{output.error_count ?? 0}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}

          {#if node.memory?.peak_mb != null}
            <div class="text-[11px] text-slate-500">
              memory peak: <span class="font-mono">{fmt(node.memory.peak_mb, 1)} MB</span>
            </div>
          {/if}
        {:else}
          <div class="grid grid-cols-2 gap-2 text-xs text-slate-700">
            <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
              <div class="text-[10px] uppercase tracking-wide text-slate-400">pipeline</div>
              <div class="font-mono">{fmt(viz.runStats.pipeline?.total_duration_s)}s</div>
              <div class="text-[11px] text-slate-500">
                nodes {viz.runStats.pipeline?.node_count ?? nodes().length} · rows
                {viz.runStats.pipeline?.total_rows_in ?? "—"}
              </div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-1.5">
              <div class="text-[10px] uppercase tracking-wide text-slate-400">stages Σ</div>
              <div class="font-mono">{fmt(stageSum(viz.runStats.stages_total))}s</div>
              <div class="text-[11px] text-slate-500">归因窗；非墙钟</div>
            </div>
          </div>

          <div data-no-drag>
            <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">stages (click demand 下钻)</div>
            <StagesStackedChart
              stagesTotal={viz.runStats.stages_total}
              nodes={nodes()}
              onRowClick={onStageRowClick}
            />
            {#if attribution()}
              <div class="mt-1 text-[11px] text-slate-500">
                write attribution: <span class="font-mono">{attribution()}</span>
              </div>
            {/if}
          </div>

          {#if topLoaders().length}
            <div data-no-drag>
              <div class="mb-1 text-[10px] uppercase tracking-wide text-slate-400">loaders (hover / click)</div>
              <LoadersBarChart loaders={topLoaders()} onBarClick={onLoaderClick} />
            </div>
          {/if}

          {#if viz.runStats.memory?.peak_mb != null}
            <div class="text-[11px] text-slate-500">
              memory peak: <span class="font-mono">{fmt(viz.runStats.memory.peak_mb, 1)} MB</span>
            </div>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
{/if}
