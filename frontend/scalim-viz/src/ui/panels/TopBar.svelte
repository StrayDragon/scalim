<script lang="ts">
  import { afterUpdate, onMount } from "svelte";
  import Button from "$ui/button.svelte";
  import Label from "$ui/label.svelte";
  import { TIME_TOOLTIPS } from "$domain/tooltips";
  import {
    applyDecorations,
    collapseAllPanels,
    displaySourceLabel,
    eventModeLabel,
    formatTimestamp,
    modeLabel,
    relayoutNodes,
    resetView,
    runId,
    runEnv,
    runLabel,
    setPlaybackIndex,
    stageOptions,
    state,
    stopPlayback
  } from "$domain/state.svelte";

  let root: HTMLDivElement | null = null;
  let observed: HTMLDivElement | null = null;
  let observer: ResizeObserver | null = null;

  const updateDock = () => {
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const nextBottom = Math.round(rect.bottom);
    const nextDockTop = Math.max(96, nextBottom + 12);
    if (state.topBarBottom !== nextBottom) state.topBarBottom = nextBottom;
    if (state.panelDockTop !== nextDockTop) state.panelDockTop = nextDockTop;
  };

  const ensureObserved = () => {
    if (!observer) return;
    if (!root) return;
    if (observed === root) return;
    observer.disconnect();
    observer.observe(root);
    observed = root;
  };

  onMount(() => {
    observer = new ResizeObserver(() => updateDock());
    ensureObserved();
    updateDock();
    return () => observer?.disconnect();
  });

  afterUpdate(() => {
    ensureObserved();
    updateDock();
  });
</script>

{#if state.toolbarCollapsed}
  <div bind:this={root} data-scalim-topbar class="absolute top-2 left-1/2 z-20 -translate-x-1/2">
    <button
      type="button"
      class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/85 px-3 py-1 text-[11px] text-slate-600 shadow-sm backdrop-blur transition-colors hover:bg-white"
      title="展开顶部栏"
      aria-expanded={false}
      on:click={() => (state.toolbarCollapsed = false)}
    >
      <span class="font-mono font-semibold text-slate-700">Scalim Viz</span>
      <span class="text-[10px] uppercase tracking-wide text-slate-400">展开</span>
    </button>
  </div>
{:else}
  <div
    bind:this={root}
    data-scalim-topbar
    class="absolute top-4 left-4 right-4 z-20 rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 shadow-sm backdrop-blur"
  >
    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <div class="font-mono font-semibold">Scalim Viz</div>
          <div
            class="max-w-[320px] truncate text-[11px] text-slate-500"
            title={runLabel() !== runId() ? `run_id: ${runId()}` : runId()}
          >
            Run: {runLabel()}
          </div>
          {#if runEnv()}
            <div class="text-[11px] text-slate-500" title="meta.viz.env">Env: {runEnv()}</div>
          {/if}
        </div>
        <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600">
          <span>模式: {modeLabel()}</span>
          <span>状态: {state.status}</span>
          <span>事件: {eventModeLabel()}</span>
          {#if state.lastUpdated}
            <span class="cursor-help" title={TIME_TOOLTIPS.lastUpdated}>更新: {formatTimestamp(state.lastUpdated)}</span>
          {/if}
          {#if state.stageFilterEnabled}
            <span>
              阶段过滤: {state.stageFilterMode === "manual" ? "手动" : "自动"}
              {#if state.currentStageFilterLevel !== null}
                (L{state.currentStageFilterLevel})
              {/if}
            </span>
          {/if}
        </div>
        <div class="mt-1 truncate text-xs text-slate-500" title={displaySourceLabel()}>目录: {displaySourceLabel()}</div>
      </div>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div class="flex items-center gap-2">
          <span class="text-[10px] uppercase tracking-wide text-slate-400">视图</span>
          <div class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white/90 p-1">
            <Button
              variant={state.viewMode === "graph" ? "default" : "ghost"}
              size="sm"
              title="依赖关系视图"
              on:click={() => {
                state.viewMode = "graph";
                stopPlayback();
                applyDecorations();
              }}
            >
              依赖图
            </Button>
            {#if state.mode !== "idle"}
              <Button
                variant={state.viewMode === "timeline" ? "default" : "ghost"}
                size="sm"
                title="按事件推进展示数据流转"
                on:click={() => {
                  state.viewMode = "timeline";
                  stopPlayback();
                  setPlaybackIndex(0, true, true);
                }}
              >
                时序图
              </Button>
            {/if}
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-[10px] uppercase tracking-wide text-slate-400">筛选</span>
          <Button
            variant={state.stageFilterEnabled ? "default" : "outline"}
            size="sm"
            title="只看当前阶段相关节点"
            on:click={() => {
              state.stageFilterEnabled = !state.stageFilterEnabled;
              applyDecorations();
            }}
          >
            仅当前阶段
          </Button>
          {#if state.stageFilterEnabled}
            <div class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 p-1">
              <Button
                variant={state.stageFilterMode === "auto" ? "default" : "ghost"}
                size="sm"
                title="根据当前事件自动选择阶段"
                on:click={() => {
                  state.stageFilterMode = "auto";
                  applyDecorations();
                }}
              >
                自动
              </Button>
              <Button
                variant={state.stageFilterMode === "manual" ? "default" : "ghost"}
                size="sm"
                title="手动选择阶段"
                on:click={() => {
                  state.stageFilterMode = "manual";
                  applyDecorations();
                }}
              >
                手动
              </Button>
            </div>
            {#if state.stageFilterMode === "manual"}
              <Label for="stage-filter-select" className="sr-only">阶段选择</Label>
              <select
                id="stage-filter-select"
                name="stage-filter-select"
                aria-label="阶段选择"
                class="text-xs border border-slate-200 bg-white/80 rounded-md px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200 focus-visible:border-blue-400"
                on:change={(event) => {
                  state.manualStageLevel = Number((event.target as HTMLSelectElement).value);
                  applyDecorations();
                }}
              >
                {#each stageOptions() as option}
                  <option value={option.level} selected={state.manualStageLevel === option.level}>
                    {option.label} (L{option.level})
                  </option>
                {/each}
              </select>
            {/if}
          {/if}
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-[10px] uppercase tracking-wide text-slate-400">连线</span>
          <Button
            variant={state.edgeShowDependsOn ? "default" : "outline"}
            size="sm"
            title="显示/隐藏 depends_on 连线"
            on:click={() => {
              state.edgeShowDependsOn = !state.edgeShowDependsOn;
              applyDecorations();
            }}
          >
            依赖
          </Button>
          <Button
            variant={state.edgeShowRefLookup ? "default" : "outline"}
            size="sm"
            title="显示/隐藏 ref_lookup 连线"
            on:click={() => {
              state.edgeShowRefLookup = !state.edgeShowRefLookup;
              applyDecorations();
            }}
          >
            引用
          </Button>
          <Button
            variant={state.edgeShowLoadsFrom ? "default" : "outline"}
            size="sm"
            title="显示/隐藏 loads_from 连线"
            on:click={() => {
              state.edgeShowLoadsFrom = !state.edgeShowLoadsFrom;
              applyDecorations();
            }}
          >
            读入
          </Button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-[10px] uppercase tracking-wide text-slate-400">操作</span>
          <Button
            variant={state.autoFollow ? "default" : "outline"}
            size="sm"
            title="切换自动聚焦到选中节点/事件"
            on:click={() => (state.autoFollow = !state.autoFollow)}
          >
            自动聚焦
          </Button>
          <Button
            variant={state.autoFitTimeline ? "default" : "outline"}
            size="sm"
            title="时序图自动适应可见节点范围"
            on:click={() => {
              state.autoFitTimeline = !state.autoFitTimeline;
              if (state.autoFitTimeline) {
                applyDecorations();
              }
            }}
            disabled={state.viewMode !== "timeline"}
          >
            自适应
          </Button>
          <Button
            variant="outline"
            size="sm"
            title="恢复默认布局"
            on:click={relayoutNodes}
            disabled={!state.snapshot}
          >
            整理节点
          </Button>
          <Button variant="outline" size="sm" title="还原视角" on:click={resetView}>
            还原视角
          </Button>
          <Button variant="outline" size="sm" title="打开数据源面板" on:click={() => (state.dataPanelOpen = !state.dataPanelOpen)}>
            加载
          </Button>
          <Button variant="outline" size="sm" title="收起所有可折叠面板" on:click={collapseAllPanels}>
            收起全部
          </Button>
          <Button variant="ghost" size="sm" title="收起顶部栏" aria-expanded={true} on:click={() => (state.toolbarCollapsed = true)}>
            收起
          </Button>
        </div>
      </div>
    </div>
  </div>
{/if}
