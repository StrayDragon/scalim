<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import { revealInYaml, state } from "$domain/state.svelte";

  const onJump = (line: number, column: number) => {
    revealInYaml(line, column || 1);
  };
</script>

<div class="flex h-full flex-col">
  <div class="flex items-center justify-between border-b bg-slate-50 px-3 py-2 text-xs">
    <div class="font-semibold text-slate-800">Outline</div>
    <div class="text-[11px] text-slate-500">{state.outlineTargets.length} items</div>
  </div>

  <div class="min-h-0 flex-1 overflow-auto p-2">
    {#if state.outlineTargets.length === 0}
      <div class="px-2 py-3 text-xs text-slate-500">未检测到顶层块(name/main_source/...)</div>
    {:else}
      <div class="flex flex-col gap-1">
        {#each state.outlineTargets as item (item.id)}
          <Button variant="ghost" className="justify-between" on:click={() => onJump(item.line, item.column)}>
            <span class="text-slate-800" style="padding-left: {item.depth * 12}px">{item.label}</span>
            <span class="text-[11px] text-slate-500">L{item.line}</span>
          </Button>
        {/each}
      </div>
    {/if}
  </div>
</div>
