<script lang="ts">
  import { getContext } from "svelte";

  const { yScale } = getContext("LayerCake") as any;

  const labels = $derived((() => {
    const scale = $yScale;
    if (!scale || typeof scale.domain !== "function") return [] as string[];
    return (scale.domain() as string[]).map(String);
  })());
</script>

<g class="axis-y" transform="translate(-4, 0)">
  {#each labels as label}
    <text
      x={0}
      y={($yScale(label) ?? 0) + ($yScale.bandwidth?.() ?? 0) / 2}
      dy="0.35em"
      text-anchor="end"
      class="fill-slate-500 text-[10px] font-mono"
    >
      {label}
    </text>
  {/each}
</g>
