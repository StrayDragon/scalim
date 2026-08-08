<script lang="ts">
  import { LayerCake, Svg } from "layercake";
  import { scaleBand } from "d3-scale";
  import type { RunStatsLoader } from "$domain/runStats";
  import AxisBandY from "./AxisBandY.svelte";
  import BarHorizontal from "./BarHorizontal.svelte";

  type Props = {
    loaders?: RunStatsLoader[];
    limit?: number;
    onBarClick?: (name: string) => void;
  };

  let { loaders = [], limit = 8, onBarClick }: Props = $props();

  const rows = $derived.by(() => {
    const sorted = [...(loaders ?? [])].sort((a, b) => Number(b.total_s ?? 0) - Number(a.total_s ?? 0));
    return sorted.slice(0, limit).map((loader) => ({
      name: String(loader.name || "—"),
      total_s: Number(loader.total_s ?? 0),
      calls: loader.calls == null ? null : Number(loader.calls)
    }));
  });

  const chartHeight = $derived(Math.max(72, rows.length * 22 + 8));

  let tip = $state<{
    name: string;
    value: number;
    calls: number | null;
    x: number;
    y: number;
  } | null>(null);

  const fmt = (value: number) => Number(value).toFixed(3);
</script>

<div class="relative w-full" style={`height:${chartHeight}px`}>
  {#key JSON.stringify(rows)}
    <LayerCake
      padding={{ top: 4, right: 8, bottom: 4, left: 72 }}
      x="total_s"
      y="name"
      yScale={scaleBand().paddingInner(0.2)}
      yDomainSort={false}
      data={rows}
    >
      <Svg>
        <AxisBandY />
        <BarHorizontal bind:hovered={tip} onBarClick={onBarClick} />
      </Svg>
    </LayerCake>
  {/key}

  {#if tip}
    <div
      class="pointer-events-none absolute z-10 rounded-md border border-slate-200 bg-white/95 px-2 py-1 text-[10px] text-slate-700 shadow-sm"
      style={`left:${Math.min(tip.x + 8, 220)}px; top:${Math.max(4, tip.y - 8)}px;`}
    >
      <span class="font-mono">{tip.name}</span>
      =
      <span class="font-mono">{fmt(tip.value)}s</span>
      {#if tip.calls != null}
        · calls <span class="font-mono">{tip.calls}</span>
      {/if}
      <span class="text-slate-400"> · click</span>
    </div>
  {/if}
</div>
