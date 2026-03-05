<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import {
    cancelCloseSchemaHintPopover,
    closeSchemaHintPopover,
    scheduleCloseSchemaHintPopover,
    schemaHintPopover
  } from "$ui/overlays/schema_hint_popover.svelte";

  let popoverEl = $state(null as HTMLDivElement | null);
  let left = $state(0);
  let top = $state(0);
  let maxHeight = $state(320);

  const MARGIN = 12;
  const GAP = 8;

  const clamp = (n: number, min: number, max: number) => {
    return Math.max(min, Math.min(max, n));
  };

  const updatePositionNow = () => {
    if (!schemaHintPopover.open) return;
    const anchor = schemaHintPopover.anchorEl;
    if (!anchor) return;
    if (!anchor.isConnected) {
      closeSchemaHintPopover();
      return;
    }

    const vpW = window.innerWidth;
    const vpH = window.innerHeight;

    const anchorRect = anchor.getBoundingClientRect();
    const popRect = popoverEl ? popoverEl.getBoundingClientRect() : null;

    const width = popRect ? popRect.width : 360;
    const height = popRect ? popRect.height : 180;

    let x = anchorRect.right - width;
    x = clamp(x, MARGIN, vpW - width - MARGIN);

    // Prefer opening above the anchor to avoid covering the input below.
    let y = anchorRect.top - GAP - height;
    if (y < MARGIN) y = anchorRect.bottom + GAP;
    y = clamp(y, MARGIN, vpH - height - MARGIN);

    left = Math.round(x);
    top = Math.round(y);
    maxHeight = Math.round(clamp(vpH - MARGIN * 2, 0, 360));
  };

  const updatePosition = async () => {
    if (!schemaHintPopover.open) return;
    await tick();
    // Ensure layout has settled (esp. when content changes).
    window.requestAnimationFrame(updatePositionNow);
  };

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!schemaHintPopover.open) return;
      if (event.key === "Escape") closeSchemaHintPopover();
    };

    const onPointerDown = (event: PointerEvent) => {
      if (!schemaHintPopover.open) return;
      const target = event.target as Node | null;
      if (!target) return;
      if (popoverEl && popoverEl.contains(target)) return;
      const anchor = schemaHintPopover.anchorEl;
      if (anchor && anchor.contains(target)) return;
      closeSchemaHintPopover();
    };

    const onScrollOrResize = (event?: Event) => {
      if (!schemaHintPopover.open) return;
      if (event?.type === "scroll") {
        const target = event.target as Node | null;
        if (target && popoverEl && popoverEl.contains(target)) return;
      }
      updatePosition();
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onScrollOrResize);
    window.addEventListener("scroll", onScrollOrResize, true);
    document.addEventListener("scroll", onScrollOrResize, true);
    document.addEventListener("pointerdown", onPointerDown, true);

    onDestroy(() => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onScrollOrResize);
      window.removeEventListener("scroll", onScrollOrResize, true);
      document.removeEventListener("scroll", onScrollOrResize, true);
      document.removeEventListener("pointerdown", onPointerDown, true);
    });
  });

  $effect(() => {
    schemaHintPopover.open;
    schemaHintPopover.text;
    schemaHintPopover.label;
    schemaHintPopover.anchorEl;
    if (schemaHintPopover.open) updatePosition();
  });
</script>

{#if schemaHintPopover.open}
  <div class="pointer-events-none fixed inset-0 z-[9999]">
    <div
      bind:this={popoverEl}
      id="schema-hint-popover"
      class="pointer-events-auto fixed w-[360px] max-w-[calc(100vw-24px)] overflow-auto rounded-lg border bg-white p-2 text-[11px] text-slate-700 shadow-lg"
      style={`left:${left}px; top:${top}px; max-height:${maxHeight}px;`}
      role="dialog"
      aria-label={schemaHintPopover.label}
      tabindex="-1"
      onpointerenter={() => cancelCloseSchemaHintPopover()}
      onpointerleave={() => scheduleCloseSchemaHintPopover()}
    >
      <div class="mb-1 flex items-center justify-between gap-2 text-[10px] font-semibold text-slate-500">
        <div class="truncate">{schemaHintPopover.label}</div>
        <button
          type="button"
          class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          aria-label="close schema hint"
          onclick={closeSchemaHintPopover}
        >
          Esc
        </button>
      </div>
      <div class="whitespace-pre-wrap leading-relaxed text-slate-600">{schemaHintPopover.text}</div>
    </div>
  </div>
{/if}
