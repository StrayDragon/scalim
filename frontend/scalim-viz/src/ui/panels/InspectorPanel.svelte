<script lang="ts">
  import { onMount, tick } from "svelte";
  import Badge from "$ui/badge.svelte";
  import Button from "$ui/button.svelte";
  import { TIME_TOOLTIPS } from "$domain/tooltips";
  import {
    badgeVariantFromStatus,
    formatTimestamp,
    getEventActionLabel,
    getEventSummaryItems,
    isExpandableValue,
    openValueDialog,
    startPanelDrag,
    state,
    statusFromEvent,
    nodeSummary,
    currentBatchNum,
    currentBatchStageSpans,
    currentBatchDecisions,
    adaptiveSchedulerSummary,
    jumpToEventIndex,
    playbackClusterInfo,
    playbackEventMessage,
    playbackEventTone,
    playbackNodeLabel,
    playbackSummaryItems,
    selectedNodeEventMessage,
    selectedNodeEventTone,
    selectedNodeLastEvent,
    selectedNodeLastEventIndex,
    selectedStageSummary,
    snapshotStats,
    hasSelection
  } from "$domain/state.svelte";

  let root: HTMLDivElement | null = null;

  const clampIntoView = async () => {
    await tick();
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 12;
    const safeTop = Math.max(margin, state.panelDockTop);

    let dx = 0;
    let dy = 0;
    if (rect.left < margin) dx = margin - rect.left;
    if (rect.right > vw - margin) dx = (vw - margin) - rect.right;
    if (rect.top < safeTop) dy = safeTop - rect.top;
    if (rect.bottom > vh - margin) dy = (vh - margin) - rect.bottom;
    if (!dx && !dy) return;
    state.inspectorOffset = { x: state.inspectorOffset.x + dx, y: state.inspectorOffset.y + dy };
  };

  const openInspector = async () => {
    state.inspectorOpen = true;
    await clampIntoView();
  };

  onMount(() => {
    void clampIntoView();
    const onResize = () => {
      if (!state.inspectorOpen) return;
      void clampIntoView();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  });

</script>

{#if !state.inspectorOpen}
  <div
    class="fixed right-4 z-20"
    style={`top: ${state.panelDockTop}px; transform: translate(${state.inspectorOffset.x}px, ${state.inspectorOffset.y}px);`}
  >
    <Button variant="outline" size="sm" on:click={openInspector}>
      勘察
    </Button>
  </div>
{/if}

	{#if state.inspectorOpen}
	  <div
	    bind:this={root}
	    class="group fixed right-4 z-20 w-[320px] max-h-[calc(100vh-7rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white/90 shadow-sm backdrop-blur p-4 flex flex-col gap-4 transition-shadow transition-colors duration-150 hover:border-slate-300 hover:shadow-md hover:shadow-slate-200/70 hover:ring-2 hover:ring-blue-200/50"
	    style={`top: ${state.panelDockTop}px; transform: translate(${state.inspectorOffset.x}px, ${state.inspectorOffset.y}px);`}
	    on:pointerdown={(event) => startPanelDrag("inspector", event, root)}
	    role="region"
	    aria-label="勘察面板"
	  >
	    <div class="flex cursor-grab select-none items-center justify-between gap-2">
	      <div class="flex items-center gap-2">
	        <div class="text-sm font-semibold">勘察面板</div>
	      </div>
	      <Button variant="outline" size="sm" on:click={() => (state.inspectorOpen = false)}>收起</Button>
	    </div>

    <div class="flex flex-col gap-2 text-xs text-slate-600">
      <div class="text-[11px] uppercase tracking-wide text-slate-400">概览</div>
      <div class="grid grid-cols-2 gap-2">
        <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
          <span>节点</span>
          <span>{snapshotStats()?.nodeCount ?? "-"}</span>
        </div>
        <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
          <span>阶段</span>
          <span>{snapshotStats()?.stageCount ?? "-"}</span>
        </div>
      </div>
    </div>

	    {#if state.viewMode === "timeline" && state.mode !== "idle" && currentBatchNum() !== null}
	      <div class="flex flex-col gap-2 text-xs text-slate-600">
	        <div class="flex items-center justify-between gap-2">
	          <div class="text-[11px] uppercase tracking-wide text-slate-400">当前批次</div>
	          <span
	            class="cursor-help text-[10px] text-slate-400"
	            title="批次由 batch_started/batch_finished 事件界定,用于理解回放进度与分层决策."
	          >
	            ?
	          </span>
	        </div>
	        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-2 flex flex-col gap-2">
	          <div class="flex items-center justify-between">
	            <span class="text-[11px] text-slate-500">batch</span>
	            <span class="font-mono text-[11px] text-slate-700">{currentBatchNum()}</span>
	          </div>

	          {#if currentBatchStageSpans()}
	            <div class="flex flex-col gap-1">
	              <div class="flex items-center justify-between gap-2">
                <div class="text-[10px] uppercase tracking-wide text-slate-400">阶段耗时</div>
                <span
                  class="cursor-help font-mono text-[10px] text-slate-400"
                  title={TIME_TOOLTIPS.stageSpan}
                >
                  stage_span
                </span>
              </div>
	              <div class="flex items-center justify-between text-[11px] text-slate-500">
	                <span>total</span>
	                <span class="font-mono text-slate-700">{currentBatchStageSpans()!.totalMs}ms</span>
	              </div>
              <div class="h-2 w-full overflow-hidden rounded-full border border-slate-200 bg-slate-50">
                {#if currentBatchStageSpans()!.totalMs > 0}
                  <div class="flex h-full w-full">
                    <div
                      class="h-full bg-blue-400/70"
                      style={`width: ${(currentBatchStageSpans()!.loaderMs / currentBatchStageSpans()!.totalMs) * 100}%`}
                      title={`loader ${currentBatchStageSpans()!.loaderMs}ms`}
                    ></div>
                    <div
                      class="h-full bg-amber-400/70"
                      style={`width: ${(currentBatchStageSpans()!.computeMs / currentBatchStageSpans()!.totalMs) * 100}%`}
                      title={`compute ${currentBatchStageSpans()!.computeMs}ms`}
                    ></div>
                    <div
                      class="h-full bg-emerald-400/70"
                      style={`width: ${(currentBatchStageSpans()!.writeMs / currentBatchStageSpans()!.totalMs) * 100}%`}
                      title={`write ${currentBatchStageSpans()!.writeMs}ms`}
                    ></div>
                  </div>
                {/if}
              </div>
              <div class="grid grid-cols-3 gap-2 text-[10px] text-slate-500">
                <div class="flex items-center justify-between rounded-md border border-slate-200 bg-white/70 px-2 py-1">
                  <span>loader</span>
                  <span class="font-mono text-slate-700">{currentBatchStageSpans()!.loaderMs}ms</span>
                </div>
                <div class="flex items-center justify-between rounded-md border border-slate-200 bg-white/70 px-2 py-1">
                  <span>compute</span>
                  <span class="font-mono text-slate-700">{currentBatchStageSpans()!.computeMs}ms</span>
                </div>
                <div class="flex items-center justify-between rounded-md border border-slate-200 bg-white/70 px-2 py-1">
                  <span>write</span>
                  <span class="font-mono text-slate-700">{currentBatchStageSpans()!.writeMs}ms</span>
                </div>
              </div>
            </div>
          {/if}

	          {#if currentBatchDecisions().length}
	            <div class="flex flex-col gap-1">
	              <div class="flex items-center justify-between gap-2">
	                <div class="text-[10px] uppercase tracking-wide text-slate-400">调度决策</div>
	                <span
	                  class="cursor-help font-mono text-[10px] text-slate-400"
	                  title="adaptive_scheduler_decision:scheduler 对每个 layer 的并行/串行/后端选择(反映“计划/调度”,不等于真实并发执行时序)."
	                >
	                  adaptive_scheduler_decision
	                </span>
	              </div>
	              <div class="flex flex-wrap items-center gap-2">
	                {#each adaptiveSchedulerSummary().backendCounts.slice(0, 4) as item (item.key)}
	                  <Badge variant="secondary" className="font-mono" title="backend:决策使用的执行后端/策略">
	                    {item.key}:{item.count}
	                  </Badge>
	                {/each}
	                {#each adaptiveSchedulerSummary().reasonCounts.slice(0, 4) as item (item.key)}
	                  <Badge variant="outline" className="font-mono" title="reason:决策原因(简要标签)">
	                    {item.key}:{item.count}
	                  </Badge>
	                {/each}
	              </div>
	              <div class="flex flex-col gap-1">
                {#each currentBatchDecisions() as item (item.index)}
                  <button
                    type="button"
                    class="w-full rounded-md border border-slate-200 bg-white/60 px-2 py-1 text-left text-[11px] hover:bg-slate-50"
                    on:click={() => jumpToEventIndex(item.index)}
                    title="跳转到该决策事件"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-mono text-slate-700">
                        L{item.layerIndex ?? "-"} {item.decision || "-"} {item.backend ? `(${item.backend})` : ""}
                      </span>
                      <span class="font-mono text-slate-500">
                        {item.layerTaskCount !== null ? `tasks=${item.layerTaskCount}` : ""}
                      </span>
                    </div>
                    {#if item.reason}
                      <div class="mt-0.5 font-mono text-[10px] text-slate-500">reason={item.reason}</div>
                    {/if}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    {#if state.viewMode === "timeline" && state.mode !== "idle" && !hasSelection()}
      <div class="flex flex-col gap-2 text-xs text-slate-600">
        <div class="text-[11px] uppercase tracking-wide text-slate-400">当前事件</div>
        {#if state.playbackEvent}
          <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-2 flex flex-col gap-2">
            <div class="flex items-center justify-between gap-2">
              <div class="text-[12px] font-semibold text-slate-700">
                {getEventActionLabel(state.playbackEvent.event_type)}
              </div>
              <Badge variant={badgeVariantFromStatus(statusFromEvent(state.playbackEvent.event_type))} className="font-mono">
                {state.playbackEvent.event_type}
              </Badge>
            </div>
            <div class="flex items-center justify-between text-[11px] text-slate-500">
              <span>时间</span>
              <span class="cursor-help font-mono" title={TIME_TOOLTIPS.eventTimestamp}
                >{formatTimestamp(state.playbackEvent.timestamp)}</span
              >
            </div>
            <div class="flex items-center justify-between text-[11px]">
              <span class="text-slate-500">节点</span>
              <span class="font-mono text-slate-700">{playbackNodeLabel()}</span>
            </div>
            {#if playbackClusterInfo()}
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-500">节点内步骤</span>
                <span class="font-mono text-slate-700">
                  {playbackClusterInfo()?.position}/{playbackClusterInfo()?.size}
                </span>
              </div>
            {/if}
            {#if playbackSummaryItems().length}
              <div class="grid grid-cols-1 gap-2">
                {#each playbackSummaryItems() as item}
                  <div class="flex flex-col gap-1 rounded-md border border-slate-200 bg-white/70 px-2 py-1 text-[11px] leading-snug">
                    <span class="text-[10px] uppercase tracking-wide text-slate-400">{item.label}</span>
                    <div class="flex items-start justify-between gap-2">
                      <span
                        class="flex-1 break-words text-[11px] font-mono leading-snug text-slate-700"
                        title={item.value}
                      >
                        {item.value}
                      </span>
	                      {#if isExpandableValue(item.value)}
	                        <button
	                          type="button"
	                          class="shrink-0 text-[10px] text-blue-500 hover:text-blue-600"
	                          on:click={(event) => openValueDialog(item.label, item.value, event.currentTarget as HTMLElement)}
	                        >
	                          查看
	                        </button>
	                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
            {#if playbackEventMessage()}
              <div class={`text-[11px] ${playbackEventTone()}`}>{playbackEventMessage()}</div>
            {/if}
          </div>
        {:else}
          <div class="text-[11px] text-slate-500">拖动回放进度条以聚焦事件</div>
        {/if}
      </div>
    {/if}

    {#if nodeSummary()}
      <div class="flex flex-col gap-2 text-xs text-slate-600">
        <div class="text-[11px] uppercase tracking-wide text-slate-400">选中节点</div>
        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-2 flex flex-col gap-1">
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">id</span>
            <span class="font-mono text-[11px] text-slate-700 max-w-[160px] truncate" title={nodeSummary()?.id}>
              {nodeSummary()?.id}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">type</span>
            <span class="text-[11px] max-w-[160px] truncate" title={String(nodeSummary()?.type ?? "default")}>
              {nodeSummary()?.type ?? "default"}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">label</span>
            <span class="text-[11px] max-w-[160px] truncate" title={String(nodeSummary()?.data?.label ?? "-")}>
              {nodeSummary()?.data?.label ?? "-"}
            </span>
          </div>
          {#if nodeSummary()?.data?.field_key}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">field_key</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.field_key ?? "")}
              >
                {String(nodeSummary()?.data?.field_key)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.target_id}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">target_id</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.target_id ?? "")}
              >
                {String(nodeSummary()?.data?.target_id)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.kind}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">kind</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.kind ?? "")}
              >
                {String(nodeSummary()?.data?.kind)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.sheet_name}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">sheet_name</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.sheet_name ?? "")}
              >
                {String(nodeSummary()?.data?.sheet_name)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.output_path}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">output_path</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.output_path ?? "")}
              >
                {String(nodeSummary()?.data?.output_path)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.source_id}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">source_id</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.source_id ?? "")}
              >
                {String(nodeSummary()?.data?.source_id)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.loader_name}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">loader_name</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.loader_name ?? "")}
              >
                {String(nodeSummary()?.data?.loader_name)}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.stage_level !== undefined}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">stage_level</span>
              <span
                class="font-mono text-[11px] max-w-[160px] truncate"
                title={String(nodeSummary()?.data?.stage_level)}
              >
                {nodeSummary()?.data?.stage_level}
              </span>
            </div>
          {/if}
          {#if nodeSummary()?.data?.last_event_type}
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-slate-500">last_event</span>
              <Badge variant={badgeVariantFromStatus(String(nodeSummary()?.data?.status ?? ""))} className="font-mono">
                {nodeSummary()?.data?.last_event_type}
              </Badge>
            </div>
          {/if}
        </div>
      </div>
    {:else if !selectedStageSummary()}
      <div class="text-[11px] text-slate-500">点击节点查看详情</div>
    {/if}

    {#if selectedNodeLastEvent()}
      {@const selectedIndex = selectedNodeLastEventIndex()}
      {@const items = getEventSummaryItems(selectedNodeLastEvent())}
      <div class="flex flex-col gap-2 text-xs text-slate-600">
        <div class="text-[11px] uppercase tracking-wide text-slate-400">节点最新事件</div>
        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-2 flex flex-col gap-1">
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">event_type</span>
            <div class="flex items-center gap-2">
              {#if selectedIndex !== null && selectedIndex !== undefined}
                <button
                  type="button"
                  class="text-[10px] text-blue-500 hover:text-blue-600"
                  title="跳转到该事件"
                  on:click={() => jumpToEventIndex(selectedIndex)}
                >
                  跳转
                </button>
              {/if}
              <Badge
                variant={badgeVariantFromStatus(statusFromEvent(selectedNodeLastEvent()!.event_type))}
                className="font-mono"
              >
                {selectedNodeLastEvent()!.event_type}
              </Badge>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">timestamp</span>
            <span class="cursor-help font-mono text-[11px]" title={TIME_TOOLTIPS.eventTimestamp}
              >{formatTimestamp(selectedNodeLastEvent()!.timestamp)}</span
            >
          </div>
          {#if items.length}
            <div class="mt-1 grid grid-cols-1 gap-2">
              {#each items as item}
                <div class="flex flex-col gap-1 rounded-md border border-slate-200 bg-white/70 px-2 py-1 text-[11px] leading-snug">
                  <span class="text-[10px] uppercase tracking-wide text-slate-400">{item.label}</span>
                  <div class="flex items-start justify-between gap-2">
                    <span
                      class="flex-1 break-words text-[11px] font-mono leading-snug text-slate-700"
                      title={item.value}
                    >
                      {item.value}
                    </span>
                    {#if isExpandableValue(item.value)}
                      <button
                        type="button"
                        class="shrink-0 text-[10px] text-blue-500 hover:text-blue-600"
                        on:click={(event) => openValueDialog(item.label, item.value, event.currentTarget as HTMLElement)}
                      >
                        查看
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
          {#if selectedNodeEventMessage()}
            <div class={`text-[11px] ${selectedNodeEventTone()}`}>{selectedNodeEventMessage()}</div>
          {/if}
        </div>
      </div>
    {/if}

	    {#if selectedStageSummary()}
	      <div class="flex flex-col gap-2 text-xs text-slate-600">
	        <div class="text-[11px] uppercase tracking-wide text-slate-400">当前阶段</div>
	        <div class="rounded-lg border border-slate-200 bg-white/70 px-2 py-2 flex flex-col gap-1">
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">label</span>
            <span class="font-mono text-[11px] text-slate-700">{selectedStageSummary()?.label}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">level</span>
            <span class="font-mono text-[11px] text-slate-700">{selectedStageSummary()?.level}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">节点</span>
            <span class="font-mono text-[11px] text-slate-700">{selectedStageSummary()?.nodeCount}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-slate-500">loader</span>
            <span class="font-mono text-[11px] text-slate-700">{selectedStageSummary()?.loaderCount}</span>
          </div>
	          <div class="flex items-center justify-between">
	            <span class="text-[11px] text-slate-500">field</span>
	            <span class="font-mono text-[11px] text-slate-700">{selectedStageSummary()?.fieldCount}</span>
	          </div>
	          {#if selectedStageSummary()?.fieldKeys.length}
	            {@const keys = selectedStageSummary()!.fieldKeys}
	            <div class="flex items-start justify-between gap-2">
	              <span
	                class="text-[11px] text-slate-500"
	                title="该阶段包含的 field_key 列表(来自 snapshot.stages[*].field_keys)."
	              >
	                字段(field_keys)
	              </span>
	              <div class="flex min-w-0 flex-col items-end gap-1">
	                <span
	                  class="max-h-[2.4em] max-w-[160px] overflow-hidden break-words text-right text-[11px] font-mono leading-snug text-slate-700"
	                  title={keys.join("\n")}
	                >
	                  {keys.slice(0, 3).join(", ")}
	                  {keys.length > 3 ? ` … +${keys.length - 3}` : ""}
	                </span>
		                <button
		                  type="button"
		                  class="text-[10px] text-blue-500 hover:text-blue-600"
		                  on:click={(event) =>
		                    openValueDialog("字段(field_keys)", keys.join("\n") || "-", event.currentTarget as HTMLElement)}
		                >
		                  查看字段
		                </button>
	              </div>
	            </div>
	          {/if}
	        </div>
	      </div>
    {/if}
  </div>
{/if}
