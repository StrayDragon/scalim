<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import TopBar from "$ui/panels/TopBar.svelte";
  import IssuesPanel from "$ui/panels/IssuesPanel.svelte";
  import OutlinePanel from "$ui/panels/OutlinePanel.svelte";
  import StatusBar from "$ui/panels/StatusBar.svelte";
  import YamlEditor from "$ui/editor/YamlEditor.svelte";
  import VisualPanel from "$ui/panels/VisualPanel.svelte";
  import PatchPreviewModal from "$ui/overlays/PatchPreviewModal.svelte";
  import AliasDecisionModal from "$ui/overlays/AliasDecisionModal.svelte";
  import SchemaHintPopoverLayer from "$ui/overlays/SchemaHintPopoverLayer.svelte";
  import { state as appState } from "$domain/state.svelte";
  import { MINIMAL_TEMPLATE } from "$services/templates";
  import { indexYamlText } from "$services/yaml_doc";

  let yamlIndexTimer: number | null = null;
  let splitContainer = $state(null as HTMLDivElement | null);
  let splitDragging = false;

  const syncYamlIndex = () => {
    const out = indexYamlText(appState.yamlText);
    appState.yamlLocations = out.locations;
    appState.outlineTargets = out.outline;
  };

  const ensureYamlIndex = (ms: number) => {
    if (yamlIndexTimer) window.clearTimeout(yamlIndexTimer);
    yamlIndexTimer = window.setTimeout(() => {
      syncYamlIndex();
    }, ms);
  };

  const clampSplitRatio = (ratio: number): number => {
    if (!Number.isFinite(ratio)) return 0.55;
    return Math.max(0.25, Math.min(0.75, ratio));
  };

  const loadSplitRatio = () => {
    try {
      const raw = window.localStorage.getItem("scalim_yaml_dsl_editor_split_ratio");
      const n = Number(raw);
      if (!Number.isFinite(n)) return;
      appState.splitRatio = clampSplitRatio(n);
    } catch {
      // ignore
    }
  };

  const persistSplitRatio = () => {
    try {
      window.localStorage.setItem("scalim_yaml_dsl_editor_split_ratio", String(appState.splitRatio));
    } catch {
      // ignore
    }
  };

  const onSplitMouseDown = (event: MouseEvent) => {
    if (!splitContainer) return;
    splitDragging = true;
    event.preventDefault();
  };

  const onSplitMouseMove = (event: MouseEvent) => {
    if (!splitDragging || !splitContainer) return;
    const rect = splitContainer.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = (event.clientX - rect.left) / rect.width;
    appState.splitRatio = clampSplitRatio(ratio);
    persistSplitRatio();
  };

  const onSplitMouseUp = () => {
    splitDragging = false;
  };

  onMount(async () => {
    loadSplitRatio();
    window.addEventListener("mousemove", onSplitMouseMove);
    window.addEventListener("mouseup", onSplitMouseUp);

    if (!appState.yamlText) {
      try {
        const res = await fetch("/examples/minimal.yaml", { cache: "no-cache" });
        appState.yamlText = res.ok ? await res.text() : MINIMAL_TEMPLATE;
      } catch {
        appState.yamlText = MINIMAL_TEMPLATE;
      }
    }
    syncYamlIndex();
  });

  $effect(() => {
    appState.yamlText;
    ensureYamlIndex(80);
  });

  onDestroy(() => {
    if (yamlIndexTimer) window.clearTimeout(yamlIndexTimer);
    window.removeEventListener("mousemove", onSplitMouseMove);
    window.removeEventListener("mouseup", onSplitMouseUp);
  });
</script>

<div class="flex h-screen flex-col">
  <TopBar />

  <div class="flex min-h-0 flex-1 gap-3 p-3">
    <div class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border bg-white shadow-sm">
      <div class="min-h-0 flex-1">
        <div
          class="grid h-full"
          bind:this={splitContainer}
          style={`grid-template-columns: ${Math.round(appState.splitRatio * 100)}% 12px 1fr;`}
        >
          <div class="min-w-0 overflow-hidden">
            <VisualPanel />
          </div>

          <button
            type="button"
            class="relative cursor-col-resize bg-slate-50 p-0 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
            aria-label="resize panes"
            onmousedown={onSplitMouseDown}
          >
            <div class="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-slate-200"></div>
          </button>

          <div class="min-w-0 overflow-hidden border-l">
            <YamlEditor />
          </div>
        </div>
      </div>
    </div>

    <div class="flex w-[420px] flex-col gap-3">
      <div class="min-h-0 flex-1 overflow-hidden rounded-xl border bg-white shadow-sm">
        <OutlinePanel />
      </div>
      <div class="min-h-0 flex-1 overflow-hidden rounded-xl border bg-white shadow-sm">
        <IssuesPanel />
      </div>
    </div>
  </div>

  <StatusBar />
</div>

<SchemaHintPopoverLayer />
<AliasDecisionModal />
<PatchPreviewModal />
