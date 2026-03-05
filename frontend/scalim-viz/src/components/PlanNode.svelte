<script lang="ts">
  import { Handle, Position } from "@xyflow/svelte";

  export let data: {
    label?: string;
    kind?: string;
    highlighted?: boolean;
    dimmed?: boolean;
    is_focus?: boolean;
    active?: boolean;
    sequence_hidden?: boolean;
  };
  export let selected: boolean = false;

  $: label = data?.label ?? "plan";
  $: dimClass = data?.dimmed ? "opacity-30" : "";
  $: highlightClass = data?.highlighted ? "ring-1 ring-emerald-200" : "";
  $: focusClass = data?.is_focus ? "ring-2 ring-blue-400" : "";
  $: activeClass = data?.active ? "border-emerald-400" : "";
  $: sequenceClass = data?.sequence_hidden ? "opacity-0 scale-95 pointer-events-none" : "opacity-100";
  $: wrapperClass = `min-w-[140px] max-w-[220px] rounded-xl border border-dashed bg-emerald-50/70 px-2.5 py-2 shadow-sm flex flex-col gap-1 transition-all duration-200 cursor-default ${sequenceClass} ${dimClass} ${highlightClass} ${focusClass} ${activeClass} ${
    selected ? "border-emerald-400 ring-2 ring-emerald-200" : "border-emerald-200"
  }`;
  $: chipClass = "text-[9px] font-mono tracking-[0.14em] uppercase px-1.5 py-0.5 rounded-full border border-emerald-300 bg-white/70 text-emerald-700";
</script>

<div class={wrapperClass}>
  <Handle type="target" position={Position.Left} class="h-2 w-2 rounded-full border border-slate-200 bg-white" />
  <Handle type="source" position={Position.Right} class="h-2 w-2 rounded-full border border-slate-200 bg-white" />
  <div class="flex items-center justify-between gap-2">
    <span class="text-sm font-semibold text-slate-900 truncate" title={label}>{label}</span>
    <span class={chipClass}>PLAN</span>
  </div>
  {#if data?.kind}
    <div class="text-[11px] font-mono text-slate-500 truncate" title={String(data.kind)}>{String(data.kind)}</div>
  {/if}
</div>

