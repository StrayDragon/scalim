<script lang="ts">
  export let data: {
    width?: number;
    height?: number;
    level?: number;
    label?: string;
    variant?: "stage" | "ingest";
    focus?: boolean;
    highlighted?: boolean;
    dimmed?: boolean;
    sequence_hidden?: boolean;
  };

  $: dimClass = data?.dimmed ? "opacity-25" : "";
  $: variant = data?.variant ?? "stage";
  $: baseClass = variant === "ingest" ? "border-indigo-300 bg-indigo-50/70" : "border-slate-300 bg-slate-100/70";
  $: focusClass = data?.focus ? "border-blue-400 bg-blue-50/80 ring-2 ring-blue-200 shadow-sm" : baseClass;
  $: highlightClass = !data?.focus && data?.highlighted ? "border-blue-200 bg-blue-50/50" : "";
  $: sequenceClass = data?.sequence_hidden ? "opacity-0 scale-95 pointer-events-none" : "opacity-100";
  $: cursorClass = variant === "ingest" ? "cursor-default" : "cursor-pointer";
</script>

<div
  class={`relative rounded-2xl border border-dashed transition-all duration-200 ${sequenceClass} ${focusClass} ${highlightClass} ${dimClass} ${cursorClass}`}
  style={`width:${data?.width ?? 200}px;height:${data?.height ?? 120}px;`}
>
  <span class="absolute top-2 left-2 text-[11px] font-mono uppercase tracking-wider text-slate-500 bg-white/80 border border-slate-200 rounded-md px-2 py-0.5">
    {data?.label ?? `stage ${data?.level ?? ""}`}
  </span>
</div>
