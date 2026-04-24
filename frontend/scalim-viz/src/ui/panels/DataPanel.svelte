<script lang="ts">
  import Button from "$ui/button.svelte";
  import Label from "$ui/label.svelte";
  import { VIZ_DIR_NAME } from "../../generated/project_constants";
	  import {
	    activeRun,
	    onEventSourceSelect,
	    onEventRunSelect,
	    onPickReplay,
	    onTraceCollapseToggle,
	    onRunSelect,
	    onVizFolder,
	    state,
	    toggleHiddenEventType
	  } from "$domain/state.svelte";
</script>

{#if state.dataPanelOpen}
  <div
    class="fixed right-4 z-30 w-[340px] max-h-[calc(100vh-7rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white/90 shadow-sm backdrop-blur p-4 flex flex-col gap-4 text-xs text-slate-600"
    style={`top: ${state.panelDockTop}px;`}
  >
    <div class="flex items-center justify-between">
      <div class="text-sm font-semibold text-slate-700">数据源</div>
      <Button variant="ghost" size="sm" on:click={() => (state.dataPanelOpen = false)}>关闭</Button>
    </div>

    <div class="flex flex-col gap-3">
      <Label>目录导入({VIZ_DIR_NAME})</Label>
	      <div class="flex flex-wrap gap-2">
	        <Button variant="outline" size="sm" on:click={onPickReplay}>
	          选择目录(回放)
	        </Button>
        <Label for="replay-folder-input" className="sr-only">选择回放目录</Label>
        <input
          class="sr-only"
          bind:this={state.replayInput}
          type="file"
          id="replay-folder-input"
          name="replay-folder-input"
          aria-label="选择回放目录"
          webkitdirectory
          on:change={onVizFolder}
	        />
	      </div>

	      {#if state.runSources.length}
	        <label class="flex flex-col gap-1 text-xs" for="run-select-replay">
          <span class="text-[11px] text-slate-500">运行选择</span>
          <select
            id="run-select-replay"
            name="run-select-replay"
            class="text-xs border border-slate-200 bg-white/80 rounded-md px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200 focus-visible:border-blue-400"
            bind:value={state.activeRunId}
            on:change={onRunSelect}
          >
            {#each state.runSources as run}
              <option value={run.id}>{run.label}</option>
            {/each}
          </select>
        </label>

        {#if activeRun() && !activeRun()?.eventsFile}
          <div class="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-[11px] text-amber-700">
	            当前 run 未找到 <span class="font-mono">viz_events.jsonl</span>,时序图不可用.
	            <div class="mt-1 text-amber-600/90">
	              说明: <span class="font-mono">yaml-dsl viz compile</span> 仅导出静态产物(<span class="font-mono">viz_snapshot.json</span> /
	              <span class="font-mono">viz_schedule_plan.json</span>),不会生成运行时事件流.
	            </div>
	          </div>
	        {/if}

        <label class="flex flex-col gap-1 text-xs" for="event-source-select-replay">
          <span class="text-[11px] text-slate-500">事件源</span>
          <select
            id="event-source-select-replay"
            name="event-source-select-replay"
            class="text-xs border border-slate-200 bg-white/80 rounded-md px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200 focus-visible:border-blue-400"
            bind:value={state.eventSourceMode}
            on:change={onEventSourceSelect}
          >
            <option value="events">events-only</option>
            <option value="events+trace" disabled={!activeRun()?.traceFile}>events+trace</option>
          </select>
          {#if state.eventSourceMode === "events+trace"}
            <div class="text-[11px] text-slate-400">
              {#if !activeRun()?.traceFile}
                当前 run 未找到 viz_trace.jsonl
              {:else if state.traceStatus === "loading"}
                正在加载 trace…
              {:else if state.traceStatus === "loaded"}
                trace 已加载
              {:else if state.traceStatus === "error"}
                trace 加载失败
              {/if}
            </div>
          {/if}
        </label>

        <div class="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white/70 p-2">
          <div class="text-[11px] uppercase tracking-wide text-slate-400">过滤</div>
          <label class="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
              checked={!state.hiddenEventTypes.includes("memory_released")}
              on:change={() => toggleHiddenEventType("memory_released")}
            />
            <span class="font-mono text-slate-700">memory_released</span>
          </label>
          {#if state.eventSourceMode === "events+trace"}
            <label class="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                checked={!state.hiddenEventTypes.includes("field_computed")}
                on:change={() => toggleHiddenEventType("field_computed")}
              />
              <span class="font-mono text-slate-700">field_computed</span>
            </label>
            <label class="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                checked={!state.hiddenEventTypes.includes("row_written")}
                on:change={() => toggleHiddenEventType("row_written")}
              />
              <span class="font-mono text-slate-700">row_written</span>
            </label>
            <label class="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                checked={!state.hiddenEventTypes.includes("row_released")}
                on:change={() => toggleHiddenEventType("row_released")}
              />
              <span class="font-mono text-slate-700">row_released</span>
            </label>
            <label class="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                checked={!state.hiddenEventTypes.includes("relation_lookup")}
                on:change={() => toggleHiddenEventType("relation_lookup")}
              />
              <span class="font-mono text-slate-700">relation_lookup</span>
            </label>
            <div class="mt-1 border-t border-slate-200/70 pt-2">
              <label class="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                  bind:checked={state.traceCollapse}
                  on:change={onTraceCollapseToggle}
                />
                <span class="text-slate-700">聚合 trace(减少事件数)</span>
              </label>
            </div>
          {/if}
        </div>
      {/if}

      {#if state.eventRunIds.length > 1}
        <label class="flex flex-col gap-1 text-xs" for="event-run-select-replay">
          <span class="text-[11px] text-slate-500">事件 run_id</span>
          <select
            id="event-run-select-replay"
            name="event-run-select-replay"
            class="text-xs border border-slate-200 bg-white/80 rounded-md px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200 focus-visible:border-blue-400"
            bind:value={state.activeEventRunId}
            on:change={onEventRunSelect}
          >
            <option value="">全部</option>
            {#each state.eventRunIds as runId}
              <option value={runId}>{runId}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>
  </div>
{/if}
