<script lang="ts">
  import { Handle, Position } from "@xyflow/svelte";

  export let data: {
    label?: string;
    source_id?: string;
    is_main?: boolean;
    status?: string;
    last_event_type?: string;
    highlighted?: boolean;
    dimmed?: boolean;
    is_focus?: boolean;
    active?: boolean;
    sequence_hidden?: boolean;
  };
  export let selected: boolean = false;

  const statusClassMap: Record<string, string> = {
    success: "bg-emerald-300 border-emerald-500",
    warn: "bg-amber-300 border-amber-500",
    error: "bg-rose-300 border-rose-500",
    info: "bg-blue-300 border-blue-500"
  };

  $: label = data?.label ?? data?.source_id ?? "source";
  $: meta = data?.source_id ?? "";
  $: status = data?.status ?? "";
  $: lastEvent = data?.last_event_type ?? "";
  $: statusClass = statusClassMap[status] ?? "bg-slate-200 border-slate-300";
  $: dimClass = data?.dimmed ? "opacity-30" : "";
  $: highlightClass = data?.highlighted ? "ring-1 ring-blue-200" : "";
  $: focusClass = data?.is_focus ? "ring-2 ring-blue-400" : "";
  $: activeClass = data?.active ? "border-blue-500" : "";
  $: sequenceClass = data?.sequence_hidden ? "opacity-0 scale-95 pointer-events-none" : "opacity-100";
  $: wrapperClass = `min-w-[160px] max-w-[220px] rounded-xl border bg-indigo-50/80 px-2.5 py-2 shadow-sm flex flex-col gap-1 transition-all duration-200 cursor-pointer border-indigo-200 hover:border-blue-300 ${sequenceClass} ${dimClass} ${highlightClass} ${focusClass} ${activeClass} ${
    selected ? "border-blue-400 ring-2 ring-blue-200" : ""
  }`;
  $: chipClass = "text-[9px] font-mono tracking-[0.14em] uppercase px-1.5 py-0.5 rounded-full border border-indigo-300 bg-white/70 text-indigo-700";
</script>

<div class={wrapperClass}>
  <Handle type="target" position={Position.Left} class="h-2 w-2 rounded-full border border-slate-200 bg-white" />
  <Handle type="source" position={Position.Right} class="h-2 w-2 rounded-full border border-slate-200 bg-white" />
  <div class="flex items-center justify-between gap-2">
    <div class="inline-flex items-center gap-1.5">
      <span class={`h-2.5 w-2.5 rounded-full border ${statusClass}`}></span>
      <span class="text-sm font-semibold text-slate-900">{label}</span>
    </div>
    <span class={chipClass}>SOURCE</span>
  </div>
  <div class="flex items-center flex-wrap gap-1.5 text-[11px] text-slate-500">
    <span class="font-mono">{meta}</span>
    {#if data?.is_main}
      <span class="text-[10px] px-1.5 py-0.5 rounded-full border border-slate-200 bg-white">main</span>
    {/if}
    {#if lastEvent}
      <span class="text-[10px] px-1.5 py-0.5 rounded-full border border-slate-200 bg-white">{lastEvent}</span>
    {/if}
  </div>
</div>
