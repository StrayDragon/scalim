<script lang="ts">
	  import { onMount, tick } from "svelte";
	  import Badge from "$ui/badge.svelte";
	  import Button from "$ui/button.svelte";
	  import Input from "$ui/input.svelte";
	  import {
	    applyDecorations,
	    clearPlanLensSelection,
	    currentPlanLayerIndex,
	    openValueDialog,
	    reachedPlanLayerIndices,
	    restorePlanLensSelection,
	    selectPlanTaskGroup,
	    startPanelDrag,
	    state
	  } from "$domain/state.svelte";

  const hasAdaptiveEvidence = () => {
    return state.eventsAll.some((evt) => evt.event_type === "adaptive_scheduler_decision");
  };

  const layers = () => {
    return state.schedulePlan?.load_ref?.layers ?? [];
  };

  const isTimeline = () => {
    return state.viewMode === "timeline" && state.mode !== "idle";
  };

  const activeLayerIndex = () => {
    if (isTimeline() && state.planLensFollowTimeline) {
      const idx = currentPlanLayerIndex();
      if (idx !== null && idx !== undefined) {
        return idx;
      }
    }
    return 0;
  };

  const reachedLayerSet = () => {
    return reachedPlanLayerIndices();
  };

  const hasPlan = () => layers().length > 0;

  const isAvailable = () => hasPlan() || hasAdaptiveEvidence();

	  const barrierCount = () => layers().filter((layer) => Boolean(layer?.rows_binding_barrier)).length;

	  const canRestore = () => Boolean(state.planLastSelection);

	  let taskFilter = "";

	  const normalizeToken = (value: any) => {
	    return String(value ?? "").toLowerCase();
	  };

	  const matchesFilter = (task: any, token: string) => {
	    if (!token) return true;
	    if (normalizeToken(task?.task_id).includes(token)) return true;
	    if (normalizeToken((task?.chain ?? []).join(" -> ")).includes(token)) return true;
	    for (const field of task?.fields ?? []) {
	      if (normalizeToken(field).includes(token)) return true;
	    }
	    return false;
	  };

	  const visibleTasksForLayer = (layer: any) => {
	    const tasks = layer?.tasks ?? [];
	    const token = taskFilter.trim().toLowerCase();
	    if (!token) return tasks;
	    return tasks.filter((task: any) => matchesFilter(task, token));
	  };

	  const selectedTaskInfo = () => {
	    const layerIndex = state.planSelectedLayerIndex;
	    const taskId = state.planSelectedTaskId;
	    if (layerIndex === null || layerIndex === undefined) return null;
	    if (!taskId) return null;
	    const layer = layers().find((item) => Number(item?.layer_index) === Number(layerIndex));
	    if (!layer) return null;
	    const task = (layer.tasks ?? []).find((item: any) => String(item?.task_id ?? "") === String(taskId));
	    if (!task) return null;
	    return { layer, task };
	  };

		  const openSelectedFields = (event: CustomEvent<MouseEvent>) => {
		    const info = selectedTaskInfo();
		    if (!info) return;
		    const fields = (info.task.fields ?? []) as string[];
		    const title = `L${info.layer.layer_index} ${info.task.task_id} fields`;
		    const anchor = (event.detail?.currentTarget ?? null) as HTMLElement | null;
		    openValueDialog(title, fields.length ? fields.join("\n") : "-", anchor);
		  };

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
    state.planLensOffset = { x: state.planLensOffset.x + dx, y: state.planLensOffset.y + dy };
  };

  const openPlanLens = async () => {
    state.planLensOpen = true;
    await clampIntoView();
  };

  onMount(() => {
    void clampIntoView();
    const onResize = () => {
      void clampIntoView();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  });

</script>

{#if isAvailable() && !state.planLensOpen}
  <div
    bind:this={root}
    class="fixed left-4 z-20"
    style={`top: ${state.panelDockTop}px; transform: translate(${state.planLensOffset.x}px, ${state.planLensOffset.y}px);`}
  >
    <Button variant="outline" size="sm" on:click={openPlanLens}>
      执行计划
    </Button>
  </div>
{/if}

	{#if isAvailable() && state.planLensOpen}
	  <div
	    bind:this={root}
	    class="group fixed left-4 z-20 w-[360px] max-h-[calc(100vh-7rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white/90 shadow-sm backdrop-blur p-4 flex flex-col gap-4 text-xs text-slate-600 transition-shadow transition-colors duration-150 hover:border-slate-300 hover:shadow-md hover:shadow-slate-200/70 hover:ring-2 hover:ring-blue-200/50"
	    style={`top: ${state.panelDockTop}px; transform: translate(${state.planLensOffset.x}px, ${state.planLensOffset.y}px);`}
	    on:pointerdown={(event) => startPanelDrag("planLens", event, root)}
	    role="region"
	    aria-label="执行计划"
	  >
	    <div class="flex cursor-grab select-none items-center justify-between gap-2">
	      <div class="flex items-center gap-2">
	        <div class="text-sm font-semibold text-slate-700">执行计划</div>
	      </div>
      <Button variant="ghost" size="sm" on:click={() => (state.planLensOpen = false)}>关闭</Button>
    </div>

    {#if !hasPlan()}
      <div class="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-[11px] text-amber-700">
        未找到 <span class="font-mono">viz_schedule_plan.json</span>,计划视角不可用.
        <div class="mt-1 text-amber-600/90">
          当前仅检测到 <span class="font-mono">adaptive_scheduler_decision</span> 事件(证据视角).
        </div>
      </div>
	    {:else}
	      <div class="flex flex-col gap-2">
	        <div class="text-[11px] uppercase tracking-wide text-slate-400">概览</div>
	        <div class="grid grid-cols-2 gap-2">
	          <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
	            <span title="最终输出字段数量(目标字段)">目标字段</span>
	            <span>{state.schedulePlan?.targets?.length ?? state.schedulePlan?.meta?.target_fields?.length ?? "-"}</span>
	          </div>
	          <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
	            <span title="需要进行引用加载(load_ref)的算子数量">load_ref ops</span>
	            <span>{state.schedulePlan?.load_ref?.op_count ?? "-"}</span>
	          </div>
	          <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
	            <span title="load_ref 的拓扑层数(层与层之间存在依赖顺序)">layers</span>
	            <span>{layers().length}</span>
	          </div>
	          <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
	            <span title="包含 rows binding 的层数(可能触发更保守的并行策略)">barriers</span>
	            <span>{barrierCount()}</span>
	          </div>
	        </div>

	        <div class="mt-1 flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            on:click={clearPlanLensSelection}
            disabled={!(state.planHighlightNodeIds.length || state.planSelectedTaskId)}
          >
            清除高亮
          </Button>
          <Button variant="outline" size="sm" on:click={restorePlanLensSelection} disabled={!canRestore()}>
            恢复
          </Button>
	          <Button
	            variant={state.planOverlayEnabled ? "default" : "outline"}
	            size="sm"
	            title="在依赖图上绘制 fanout/fanin 虚拟节点,帮助看出分叉/汇聚(不代表真实并发)"
	            on:click={() => {
	              state.planOverlayEnabled = !state.planOverlayEnabled;
	              applyDecorations();
	            }}
	          >
	            Overlay
	          </Button>
	        </div>

	        <div class="rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-[11px] text-slate-500">
	          说明:这是 <span class="font-mono">plan</span> 视角(fanout/fanin/屏障),用于理解“计划后大致形状”,不表示真实并发时序.
	        </div>

	        <details class="group rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-[11px] text-slate-500">
	          <summary class="flex cursor-pointer list-none items-center justify-between gap-2">
	            <span class="text-slate-600">术语说明</span>
	            <span class="text-[10px] text-slate-400 group-open:rotate-180 transition-transform">▾</span>
	          </summary>
	          <div class="mt-2 flex flex-col gap-1 leading-snug">
	            <div>
	              <span class="font-mono">L0/L1</span>:按依赖分层后的 <span class="font-mono">load_ref</span> 拓扑层;后层依赖前层.
	            </div>
	            <div>
	              <span class="font-mono">t0/t1</span>:同一层中,按相同 <span class="font-mono">chain</span> 分组后的任务组(可视为 fanout 单元).
	            </div>
	            <div>
	              <span class="font-mono">chain</span>:该任务组的引用链(关系/表的 lookup 路径).
	            </div>
	            <div>
	              <span class="font-mono">fields</span>:该任务组包含的 <span class="font-mono">field_key</span> 列表;点击任务会在图上高亮这些字段节点.
	            </div>
	            <div>
	              <span class="font-mono">rows</span>/<span class="font-mono">rows barrier</span>:存在 row-binding,通常意味着需要屏障/更保守的并行策略.
	            </div>
	            <div>
	              <span class="font-mono">current/reached/pending</span>:在时序回放中,按已出现的决策事件推断层的“到达”状态(不是实际执行完成).
	            </div>
	          </div>
	        </details>

	        {#if selectedTaskInfo()}
	          {@const info = selectedTaskInfo()!}
	          <div class="rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-[11px] text-slate-600">
	            <div class="flex items-start justify-between gap-2">
	              <div class="min-w-0">
	                <div class="font-mono text-[12px] font-semibold text-slate-700">
	                  L{info.layer.layer_index} {info.task.task_id}
	                </div>
	                <div class="mt-0.5 truncate text-[11px] text-slate-500" title={(info.task.chain ?? []).join(" -> ")}>
	                  chain: <span class="font-mono">{(info.task.chain ?? []).join(" -> ") || "-"}</span>
	                </div>
	              </div>
	              <div class="flex shrink-0 flex-col items-end gap-1">
	                {#if info.layer.rows_binding_barrier}
	                  <Badge variant="warning" className="font-mono">rows barrier</Badge>
	                {/if}
	                {#if info.task.rows_binding}
	                  <Badge variant="warning" className="font-mono">rows</Badge>
	                {/if}
	              </div>
	            </div>
	            <div class="mt-2 flex items-center justify-between">
	              <span class="text-slate-500">fields</span>
	              <span class="font-mono text-slate-700">{info.task.fields?.length ?? 0}</span>
	            </div>
	            {#if (info.task.fields?.length ?? 0) > 0}
	              {@const fields = info.task.fields ?? []}
	              <div class="mt-1 flex flex-wrap gap-1">
	                {#each fields.slice(0, 6) as field (field)}
	                  <span
	                    class="rounded-md border border-slate-200 bg-white/80 px-1.5 py-0.5 font-mono text-[10px] text-slate-600"
	                    title={field}
	                  >
	                    {field}
	                  </span>
	                {/each}
	                {#if fields.length > 6}
	                  <span
	                    class="rounded-md border border-slate-200 bg-white/80 px-1.5 py-0.5 text-[10px] text-slate-500"
	                    title={fields.join("\n")}
	                  >
	                    +{fields.length - 6}
	                  </span>
	                {/if}
	              </div>
	              <div class="mt-2">
	                <Button variant="outline" size="sm" on:click={openSelectedFields}>
	                  查看字段
	                </Button>
	              </div>
	            {/if}
	          </div>
	        {/if}
	      </div>

	      <div class="flex flex-col gap-2">
	        <div class="flex items-center justify-between gap-2">
	          <div class="text-[11px] uppercase tracking-wide text-slate-400">Load Ref Layers</div>
	          {#if isTimeline()}
	            <label class="flex items-center gap-2 text-[11px] text-slate-500" title="开启后,层的 current/reached 会跟随时序回放进度(基于决策事件推断)">
	              <input
	                type="checkbox"
	                class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
	                bind:checked={state.planLensFollowTimeline}
	              />
	              <span>跟随回放</span>
	            </label>
	          {/if}
	        </div>

	        <div class="flex flex-col gap-1">
	          <div class="flex items-center justify-between gap-2">
	            <div class="text-[11px] uppercase tracking-wide text-slate-400">过滤</div>
	            {#if taskFilter}
	              <button
	                type="button"
	                class="text-[10px] text-blue-500 hover:text-blue-600"
	                on:click={() => (taskFilter = "")}
	              >
	                清空
	              </button>
	            {/if}
	          </div>
	          <Input
	            placeholder="搜索 task / chain / field_key…"
	            bind:value={taskFilter}
	            className="bg-white/70"
	          />
	        </div>

	        {#each layers() as layer (layer.layer_index)}
	          {@const visibleTasks = visibleTasksForLayer(layer)}
	          {@const reached = reachedLayerSet().has(layer.layer_index)}
	          {@const current = layer.layer_index === activeLayerIndex()}
	          {#if visibleTasks.length}
	            <div
	              class={`rounded-xl border p-2 ${current ? "border-blue-200 bg-blue-50/40" : "border-slate-200 bg-white/70"}`}
	            >
	              <details open={layer.layer_index === activeLayerIndex() || Boolean(taskFilter)} class="group">
	                <summary class="flex cursor-pointer list-none items-center justify-between gap-2">
	                  <div class="flex min-w-0 items-center gap-2">
	                    <span class="font-mono text-slate-700">L{layer.layer_index}</span>
	                    <span
	                      class="text-[11px] text-slate-500"
	                      title="ops=本层 load_ref 算子数 · tasks=本层任务组数(按 chain 分组)"
	                    >
	                      ops={layer.op_count ?? "-"} · tasks={layer.task_group_count ?? layer.tasks?.length ?? "-"}
	                    </span>
	                  </div>
	                  <div class="flex items-center gap-1">
	                    {#if isTimeline()}
	                      {#if current}
	                        <Badge variant="default" className="font-mono">current</Badge>
	                      {:else if reached}
	                        <Badge variant="success" className="font-mono">reached</Badge>
	                      {:else}
	                        <Badge variant="outline" className="font-mono">pending</Badge>
	                      {/if}
	                    {/if}
	                    {#if layer.rows_binding_barrier}
	                      <Badge variant="warning" className="font-mono">rows barrier</Badge>
	                    {/if}
	                    <span class="text-[10px] text-slate-400 group-open:rotate-180 transition-transform">▾</span>
	                  </div>
	                </summary>

	                <div class="mt-2 flex flex-col gap-2">
	                  {#each visibleTasks as task (task.task_id)}
	                    <button
	                      type="button"
	                      class={`w-full rounded-lg border px-2 py-1 text-left transition-colors ${
	                        state.planSelectedLayerIndex === layer.layer_index && state.planSelectedTaskId === task.task_id
	                          ? "border-blue-300 bg-blue-50/80"
	                          : "border-slate-200 bg-white/60 hover:bg-slate-50/80"
	                      }`}
	                      title="点击以高亮该任务组的字段节点(plan 视角)"
	                      on:click={() =>
	                        selectPlanTaskGroup({
	                          layerIndex: layer.layer_index,
	                          taskId: task.task_id,
	                          fieldKeys: task.fields ?? []
	                        })}
	                    >
	                      <div class="flex items-start justify-between gap-2">
	                        <div class="min-w-0">
	                          <div class="flex items-center gap-2">
	                            <span class="font-mono text-[11px] text-slate-700">{task.task_id}</span>
	                            {#if task.rows_binding}
	                              <Badge variant="warning" className="font-mono">rows</Badge>
	                            {/if}
	                          </div>
	                          <div
	                            class="mt-0.5 truncate text-[11px] text-slate-500"
	                            title={(task.chain ?? []).join(" -> ")}
	                          >
	                            {(task.chain ?? []).join(" -> ") || "-"}
	                          </div>
	                        </div>
	                        <div class="shrink-0 text-[11px] text-slate-500">
	                          {task.fields?.length ?? 0} 字段
	                        </div>
	                      </div>
	                    </button>
	                  {/each}
	                </div>
	              </details>
	            </div>
	          {/if}
	        {/each}
	      </div>
	    {/if}
	  </div>
{/if}
