<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import Button from "$ui/button.svelte";
	  import {
	    applyDecorations,
	    autoloadReplayFromQuery,
	    closeValueDialog,
	    ensurePlaybackTimer,
	    handleDocumentPointerDown,
	    handlePanelMove,
	    handlePanelUp,
    jumpOptions,
    registerValueDialogRoot,
    repositionValueDialog,
    stageOptions,
    state as vizState,
    stopPlayback
  } from "$domain/state.svelte";
  import GraphCanvas from "$panels/GraphCanvas.svelte";
  import DataPanel from "$panels/DataPanel.svelte";
  import PlanLensPanel from "$panels/PlanLensPanel.svelte";
  import InspectorPanel from "$panels/InspectorPanel.svelte";
  import PlaybackPanel from "$panels/PlaybackPanel.svelte";
  import TopBar from "$panels/TopBar.svelte";

  let copied = $state(false);
  let copyError = $state(false);
  let valuePopupRoot: HTMLDivElement | null = $state(null);

  const copyValueDialogContent = async () => {
    const value = vizState.valueDialogContent || "";
    if (!value) return;
    copied = false;
    copyError = false;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        throw new Error("clipboard unavailable");
      }
      copied = true;
    } catch {
      copyError = true;
    }
    window.setTimeout(() => {
      copied = false;
      copyError = false;
    }, 1200);
  };

	  onMount(() => {
	    void autoloadReplayFromQuery();
	    document.addEventListener("pointerdown", handleDocumentPointerDown);
	    window.addEventListener("pointermove", handlePanelMove);
	    window.addEventListener("pointerup", handlePanelUp);
	    window.addEventListener("resize", repositionValueDialog);
    window.addEventListener("scroll", repositionValueDialog, true);
    return () => {
      document.removeEventListener("pointerdown", handleDocumentPointerDown);
      window.removeEventListener("pointermove", handlePanelMove);
      window.removeEventListener("pointerup", handlePanelUp);
      window.removeEventListener("resize", repositionValueDialog);
      window.removeEventListener("scroll", repositionValueDialog, true);
    };
  });

  onDestroy(() => {
    stopPlayback();
  });

  $effect(() => {
    if (!vizState.valueDialogOpen) {
      copied = false;
      copyError = false;
    }
  });

  $effect(() => {
    registerValueDialogRoot(valuePopupRoot);
  });

  $effect(() => {
    const options = stageOptions();
    if (vizState.stageFilterEnabled && vizState.stageFilterMode === "manual" && options.length) {
      const levels = options.map((item) => item.level);
      if (vizState.manualStageLevel === null || !levels.includes(vizState.manualStageLevel)) {
        vizState.manualStageLevel = levels[0];
        applyDecorations();
      }
    }
  });

  $effect(() => {
    ensurePlaybackTimer();
  });

  $effect(() => {
    const options = jumpOptions();
    if (!vizState.jumpDefaultsApplied && options.length) {
      const defaults = ["error", "diagnostic_warning", "adaptive_scheduler_decision", "stage_span", "field_computed"];
      const available = new Set(options.map((option) => option.value));
      const next = defaults.filter((token) => available.has(token));
      if (next.length === 0 && options.length) {
        next.push(options[0].value);
      }
      vizState.jumpEventTokens = next;
      vizState.jumpDefaultsApplied = true;
    }
  });
</script>

<div
  class="relative h-screen overflow-hidden font-sans text-slate-900 bg-slate-50 bg-fixed [background-image:radial-gradient(900px_520px_at_10%_-10%,rgba(37,99,235,0.14),transparent_60%),radial-gradient(820px_480px_at_90%_0%,rgba(249,115,22,0.12),transparent_60%),linear-gradient(180deg,#ffffff_0%,#f8fafc_55%,#f1f5f9_100%)]"
	>
	  <GraphCanvas />
	  {#if vizState.dataPanelOpen}
	    <div class="absolute inset-0 z-10 bg-slate-900/20 backdrop-blur-[1px] pointer-events-none"></div>
	  {/if}

	  <TopBar />

  <div class="absolute right-4 top-24 z-20 flex flex-col items-end gap-2">
    <DataPanel />
    <PlanLensPanel />
    <InspectorPanel />
  </div>

		  <PlaybackPanel />

		  {#if vizState.valueDialogOpen}
		    <div
		      bind:this={valuePopupRoot}
		      class="fixed z-40 w-[380px] max-w-[calc(100%-2rem)] rounded-2xl border border-slate-200 bg-white/95 shadow-lg backdrop-blur p-4 flex flex-col gap-3"
		      style={`left: ${vizState.valueDialogPosition?.left ?? 12}px; top: ${vizState.valueDialogPosition?.top ?? vizState.panelDockTop}px; max-height: ${vizState.valueDialogPosition?.maxHeight ?? 280}px;`}
		      role="dialog"
		      aria-label="值预览"
		    >
		      <div class="flex items-center justify-between gap-2">
		        <div class="text-sm font-semibold text-slate-800">{vizState.valueDialogTitle}</div>
		        <div class="flex items-center gap-2">
		          <Button
		            variant="outline"
		            size="sm"
		            on:click={copyValueDialogContent}
		            disabled={!vizState.valueDialogContent}
		          >
		            复制
		          </Button>
		          <Button variant="ghost" size="sm" on:click={closeValueDialog}>关闭</Button>
		        </div>
		      </div>
		      {#if copied}
		        <div class="text-[10px] text-emerald-600">已复制</div>
		      {:else if copyError}
		        <div class="text-[10px] text-amber-600">复制失败(浏览器权限限制)</div>
		      {/if}
		      <div class="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-xs text-slate-700">
		        {vizState.valueDialogContent || "-"}
		      </div>
		    </div>
		  {/if}
</div>
