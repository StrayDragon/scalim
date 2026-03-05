<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import type * as Monaco from "monaco-editor";
  import Button from "$components/ui/button.svelte";
  import { state as appState } from "$domain/state.svelte";
  import { cancelPendingPatch, confirmPendingPatch } from "$services/patch_apply";

  let container = $state(null as HTMLDivElement | null);

  let monaco: typeof Monaco | null = null;
  let diffEditor: any = null;
  let originalModel: any = null;
  let modifiedModel: any = null;

  const disposeEditor = () => {
    try {
      diffEditor?.dispose?.();
    } catch {
      // ignore
    }
    diffEditor = null;
    try {
      originalModel?.dispose?.();
    } catch {
      // ignore
    }
    originalModel = null;
    try {
      modifiedModel?.dispose?.();
    } catch {
      // ignore
    }
    modifiedModel = null;
  };

  const ensureEditor = async () => {
    if (!container) return;
    const pending = appState.pendingPatch;
    if (!pending) return;

    await tick();
    if (!container) return;
    if (!appState.pendingPatch) return;

    if (!monaco) monaco = await import("monaco-editor");
    disposeEditor();

    diffEditor = monaco.editor.createDiffEditor(container, {
      readOnly: true,
      automaticLayout: true,
      minimap: { enabled: false },
      renderSideBySide: true,
      scrollBeyondLastLine: false,
      originalEditable: false,
      wordWrap: "on"
    } as any);

    originalModel = monaco.editor.createModel(pending.beforeText, "yaml", monaco.Uri.parse("inmemory://patch/original.yaml"));
    modifiedModel = monaco.editor.createModel(pending.afterText, "yaml", monaco.Uri.parse("inmemory://patch/modified.yaml"));
    diffEditor.setModel({ original: originalModel, modified: modifiedModel });
  };

  const onBackdrop = () => {
    cancelPendingPatch();
  };

  const onCopyAfter = async () => {
    const pending = appState.pendingPatch;
    if (!pending) return;
    try {
      await navigator.clipboard.writeText(pending.afterText);
    } catch {
      // ignore
    }
  };

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!appState.pendingPatch) return;
      if (event.key === "Escape") cancelPendingPatch();
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") confirmPendingPatch();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  $effect(() => {
    appState.pendingPatch;
    if (!appState.pendingPatch) {
      disposeEditor();
      return;
    }
    ensureEditor();
  });

  onDestroy(() => {
    disposeEditor();
  });
</script>

{#if appState.pendingPatch}
  <div class="fixed inset-0 z-[10000]">
    <button type="button" class="absolute inset-0 bg-black/40" aria-label="cancel patch preview" onclick={onBackdrop}></button>

    <div class="absolute left-1/2 top-1/2 w-[min(1100px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border bg-white shadow-2xl">
      <div class="flex items-start justify-between gap-3 border-b bg-slate-50 px-4 py-3">
        <div class="min-w-0">
          <div class="truncate text-sm font-semibold text-slate-800">{appState.pendingPatch.title}</div>
          <div class="mt-0.5 text-[11px] text-slate-500">
            plan: {appState.pendingPatch.planKind}
            {#if appState.pendingPatch.planReason}
              · {appState.pendingPatch.planReason}
            {/if}
          </div>
          <div class="mt-0.5 text-[11px] text-slate-400">Esc 取消 · Ctrl/⌘+Enter 应用</div>
        </div>

        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" on:click={onCopyAfter}>复制修改后 YAML</Button>
          <Button variant="outline" size="sm" on:click={cancelPendingPatch}>取消</Button>
          <Button variant="secondary" size="sm" on:click={confirmPendingPatch}>应用</Button>
        </div>
      </div>

      <div class="h-[60vh] min-h-[360px] bg-white" bind:this={container}></div>
    </div>
  </div>
{/if}
