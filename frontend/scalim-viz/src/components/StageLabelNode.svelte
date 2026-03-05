<script lang="ts">
  export let data: {
    label?: string;
    level?: number;
    focus?: boolean;
    highlighted?: boolean;
    dimmed?: boolean;
    active?: boolean;
    sequence_hidden?: boolean;
  };
  export let selected: boolean = false;

  $: label = data?.label ?? `stage ${data?.level ?? ""}`;
  $: baseClass = "border-slate-200 bg-white/90 text-slate-500";
  $: focusClass = data?.focus ? "border-blue-400 bg-blue-50/90 text-blue-700" : baseClass;
  $: highlightClass = data?.highlighted ? "ring-1 ring-blue-200" : "";
  $: dimClass = data?.dimmed ? "opacity-40" : "";
  $: activeClass = data?.active ? "border-blue-500" : "";
  $: selectedClass = selected ? "ring-2 ring-blue-200 border-blue-400" : "";
  $: sequenceClass = data?.sequence_hidden ? "opacity-0 scale-95 pointer-events-none" : "opacity-100";
  $: wrapperClass = `inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider shadow-sm cursor-pointer transition-all duration-200 ${focusClass} ${highlightClass} ${dimClass} ${activeClass} ${selectedClass} ${sequenceClass}`;
</script>

<div class={wrapperClass}>
  {label}
</div>
