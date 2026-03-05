<script lang="ts">
  import {
    cancelCloseSchemaHintPopover,
    closeSchemaHintPopover,
    openSchemaHintPopover,
    scheduleCloseSchemaHintPopover,
    schemaHintPopover,
    updateSchemaHintPopover
  } from "$ui/overlays/schema_hint_popover.svelte";

  type Props = {
    text?: string;
    label?: string;
    mode?: "inline" | "block";
  };

  let { text = "", label = "Schema 提示", mode = "inline" }: Props = $props();

  let anchorEl = $state(null as HTMLButtonElement | null);
  let openTimer: number | null = $state(null);

  const isOpen = () => {
    return schemaHintPopover.open && schemaHintPopover.anchorEl === anchorEl;
  };

  const open = (pinned: boolean) => {
    if (!text || !anchorEl) return;
    cancelCloseSchemaHintPopover();
    openSchemaHintPopover({ anchorEl, text, label, pinned });
  };

  const scheduleOpen = (pinned: boolean) => {
    if (!text || !anchorEl) return;
    if (openTimer != null) window.clearTimeout(openTimer);
    openTimer = window.setTimeout(() => {
      openTimer = null;
      if (!anchorEl) return;
      open(pinned);
    }, 120);
  };

  const onToggle = () => {
    if (!text || !anchorEl) return;
    if (isOpen()) closeSchemaHintPopover();
    else open(true);
  };

  const onPointerEnter = () => {
    if (!text || !anchorEl) return;
    // If already pinned open, don't override.
    if (isOpen() && schemaHintPopover.pinned) return;
    scheduleOpen(false);
  };

  const onPointerLeave = () => {
    if (openTimer != null) {
      window.clearTimeout(openTimer);
      openTimer = null;
    }
    scheduleCloseSchemaHintPopover();
  };

  const onFocus = () => {
    if (!text || !anchorEl) return;
    if (isOpen() && schemaHintPopover.pinned) return;
    open(false);
  };

  const onBlur = () => {
    scheduleCloseSchemaHintPopover();
  };

  $effect(() => {
    if (!text) return;
    if (!isOpen()) return;
    updateSchemaHintPopover({ text, label });
  });
</script>

{#if text}
  {#if mode === "inline"}
    <button
      bind:this={anchorEl}
      type="button"
      class="cursor-pointer select-none inline-flex h-5 w-5 items-center justify-center rounded-md text-[11px] font-semibold text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
      class:border-sky-300={isOpen()}
      class:bg-sky-50={isOpen()}
      class:text-slate-800={isOpen()}
      aria-label={label}
      title={label}
      aria-controls="schema-hint-popover"
      aria-expanded={isOpen()}
      onclick={onToggle}
      onpointerenter={onPointerEnter}
      onpointerleave={onPointerLeave}
      onfocus={onFocus}
      onblur={onBlur}
    >
      ?
    </button>
  {:else}
    <details class="rounded-lg border bg-slate-50/70 px-3 py-2 text-[11px] text-slate-600">
      <summary
        class="list-none cursor-pointer select-none text-[11px] font-medium text-slate-600 transition-colors hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
      >
        {label}
      </summary>
      <div class="mt-2 whitespace-pre-wrap leading-relaxed text-slate-600">{text}</div>
    </details>
  {/if}
{/if}

<style>
  summary {
    list-style: none;
  }
  summary::-webkit-details-marker {
    display: none;
  }
</style>
