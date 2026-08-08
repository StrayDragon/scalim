<script lang="ts">
  import { LayerCake, Svg, flatten, stack } from "layercake";
  import { scaleBand, scaleOrdinal } from "d3-scale";
  import { runStatsNodeLabel, type RunStatsNode, type RunStatsStages } from "$domain/runStats";
  import AxisBandY from "./AxisBandY.svelte";
  import BarStacked from "./BarStacked.svelte";

  type Props = {
    stagesTotal?: RunStatsStages | null;
    nodes?: RunStatsNode[];
    includeTotal?: boolean;
    onRowClick?: (payload: { kind: "total" | "node"; nodeIndex: number | null; label: string }) => void;
  };

  let { stagesTotal = null, nodes = [], includeTotal = true, onRowClick }: Props = $props();

  const STAGE_KEYS = ["loader", "compute", "write", "stream"] as const;
  const STAGE_COLORS = ["#0f766e", "#1d4ed8", "#b45309", "#64748b"];

  const rows = $derived.by(() => {
    const out: Array<Record<string, string | number>> = [];
    const pushRow = (label: string, stages: RunStatsStages | null | undefined) => {
      const row: Record<string, string | number> = { row: label };
      for (const key of STAGE_KEYS) {
        row[key] = Number(stages?.[key] ?? 0);
      }
      out.push(row);
    };
    if (includeTotal) {
      pushRow("Σ", stagesTotal);
    }
    (nodes ?? []).forEach((node, idx) => {
      pushRow(runStatsNodeLabel(node, idx), node?.stages_total);
    });
    return out;
  });

  const stacked = $derived(stack(rows, [...STAGE_KEYS]));
  const flat = $derived(flatten(stacked));

  let tip = $state<{
    seriesKey: string;
    rowLabel: string;
    value: number;
    x: number;
    y: number;
  } | null>(null);

  const fmt = (value: number) => Number(value).toFixed(3);

  const handleRowClick = (rowLabel: string) => {
    if (!onRowClick) return;
    if (rowLabel === "Σ") {
      onRowClick({ kind: "total", nodeIndex: null, label: rowLabel });
      return;
    }
    const idx = (nodes ?? []).findIndex((node, i) => runStatsNodeLabel(node, i) === rowLabel);
    onRowClick({ kind: "node", nodeIndex: idx >= 0 ? idx : null, label: rowLabel });
  };
  const chartHeight = $derived(Math.max(48, rows.length * 28 + 12));
</script>

<div class="flex flex-col gap-1">
  <div class="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
    {#each STAGE_KEYS as key, i}
      <span class="inline-flex items-center gap-1">
        <span class="inline-block h-2 w-2 rounded-sm" style={`background:${STAGE_COLORS[i]}`}></span>
        <span class="font-mono">{key}</span>
      </span>
    {/each}
  </div>

  <div class="relative w-full" style={`height:${chartHeight}px`}>
    {#key JSON.stringify(rows)}
      <LayerCake
        padding={{ top: 4, right: 8, bottom: 4, left: 56 }}
        x={[0, 1]}
        y={(d: { data: { row: string } }) => d.data.row}
        z="key"
        yScale={scaleBand().paddingInner(0.18)}
        zScale={scaleOrdinal()}
        yDomainSort={false}
        zDomain={[...STAGE_KEYS]}
        zRange={STAGE_COLORS}
        flatData={flat}
        data={stacked}
      >
        <Svg>
          <AxisBandY />
          <BarStacked bind:hovered={tip} onRowClick={handleRowClick} />
        </Svg>
      </LayerCake>
    {/key}

    {#if tip}
      <div
        class="pointer-events-none absolute z-10 rounded-md border border-slate-200 bg-white/95 px-2 py-1 text-[10px] text-slate-700 shadow-sm"
        style={`left:${Math.min(tip.x + 8, 240)}px; top:${Math.max(4, tip.y - 8)}px;`}
      >
        <span class="font-mono">{tip.rowLabel}</span>
        ·
        <span class="font-mono">{tip.seriesKey}</span>
        =
        <span class="font-mono">{fmt(tip.value)}s</span>
        <span class="text-slate-400"> · click</span>
      </div>
    {/if}
  </div>
</div>
