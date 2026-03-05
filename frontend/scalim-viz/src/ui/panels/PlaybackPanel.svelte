<script lang="ts">
  import Badge from "$ui/badge.svelte";
  import Button from "$ui/button.svelte";
  import Input from "$ui/input.svelte";
  import Label from "$ui/label.svelte";
  import { TIME_TOOLTIPS } from "$domain/tooltips";
  import {
    badgeVariantFromStatus,
    formatTimestamp,
    jumpOptions,
    jumpToBatchBoundary,
    jumpToCustom,
    jumpToNodeBoundary,
    openJumpDropdown,
    playbackEventMessage,
    playbackEventTone,
    setPlaybackIndex,
    startPanelDrag,
    state,
    statusFromEvent,
    stepPlayback,
    toggleJumpEvent,
    togglePlayback
  } from "$domain/state.svelte";

  let root: HTMLDivElement | null = null;
</script>

{#if state.viewMode === "timeline" && state.mode !== "idle"}
  <div
    bind:this={root}
    class={`group absolute bottom-4 left-1/2 z-20 w-[640px] max-w-[calc(100%-2rem)] -translate-x-1/2 rounded-2xl border border-slate-200 bg-white/90 shadow-lg backdrop-blur transition-shadow transition-colors duration-150 hover:border-slate-300 hover:shadow-xl hover:ring-2 hover:ring-blue-200/50 ${
      state.playbackCompact ? "px-3 py-2" : "p-3"
    }`}
    style={`transform: translate(calc(-50% + ${state.playbackOffset.x}px), ${state.playbackOffset.y}px);`}
    on:pointerdown={(event) => startPanelDrag("playback", event, root)}
    role="region"
    aria-label="回放控制"
  >
    <div class="flex cursor-grab select-none items-center justify-between text-[11px] uppercase tracking-wide text-slate-400">
      <div class="flex items-center gap-2">
        <span>回放控制</span>
      </div>
      <div class="flex items-center gap-2 text-slate-500">
        <span>{state.playbackIndex}/{state.events.length}</span>
        <Button variant="ghost" size="sm" on:click={() => (state.playbackCompact = !state.playbackCompact)}>
          {state.playbackCompact ? "展开" : "最小化"}
        </Button>
      </div>
    </div>
    <div class="mt-2">
      <Label for="playback-position" className="sr-only">回放进度</Label>
      <input
        type="range"
        id="playback-position"
        name="playback-position"
        min="0"
        max={state.events.length}
        step="1"
        value={state.playbackIndex}
        disabled={state.events.length === 0 || state.viewMode !== "timeline"}
        class="w-full accent-blue-500"
        on:input={(evt) => setPlaybackIndex(Number((evt.target as HTMLInputElement).value))}
        aria-label="回放进度"
      />
    </div>
    <div class="mt-1 flex items-center justify-between text-[10px] text-slate-400">
      <span class="cursor-help" title={TIME_TOOLTIPS.eventTimestamp}>事件时间</span>
      <span class="cursor-help" title={TIME_TOOLTIPS.eventTimestamp}
        >{state.playbackEvent ? formatTimestamp(state.playbackEvent.timestamp) : "暂无事件"}</span
      >
    </div>
    {#if !state.playbackCompact}
      <div class="mt-2 flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <div class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50/80 px-1 py-1">
            <Button
              variant="outline"
              size="sm"
              on:click={() => jumpToBatchBoundary(-1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex <= 0}
            >
              上一个批次
            </Button>
            <Button
              variant="outline"
              size="sm"
              on:click={() => jumpToNodeBoundary(-1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex <= 0}
            >
              上一个节点
            </Button>
            <Button
              variant="outline"
              size="sm"
              on:click={() => stepPlayback(-1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex <= 0}
            >
              上一个
            </Button>
            <Button
              variant={state.playbackPlaying ? "default" : "outline"}
              size="sm"
              on:click={togglePlayback}
              disabled={state.viewMode !== "timeline" || state.events.length === 0}
            >
              {state.playbackPlaying ? "暂停" : "播放"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              on:click={() => stepPlayback(1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex >= state.events.length}
            >
              下一个
            </Button>
            <Button
              variant="outline"
              size="sm"
              on:click={() => jumpToNodeBoundary(1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex >= state.events.length}
            >
              下一个节点
            </Button>
            <Button
              variant="outline"
              size="sm"
              on:click={() => jumpToBatchBoundary(1)}
              disabled={state.viewMode !== "timeline" || state.playbackIndex >= state.events.length}
            >
              下一个批次
            </Button>
          </div>
        </div>
        <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white/80 px-2 py-1 text-[11px] text-slate-600">
          <span class="text-slate-500">当前事件</span>
          <div class="flex items-center gap-2 whitespace-nowrap">
            {#if state.playbackEvent}
              <Badge variant={badgeVariantFromStatus(statusFromEvent(state.playbackEvent.event_type))} className="font-mono">
                {state.playbackEvent.event_type}
              </Badge>
              <span class="cursor-help font-mono text-slate-500" title={TIME_TOOLTIPS.eventTimestamp}
                >{formatTimestamp(state.playbackEvent.timestamp)}</span
              >
            {:else}
              <span class="text-slate-400">暂无事件</span>
            {/if}
          </div>
        </div>
      </div>
      {#if playbackEventMessage()}
        <div class={`mt-1 text-[11px] ${playbackEventTone()}`}>{playbackEventMessage()}</div>
      {/if}
      <div class="mt-2 flex items-center gap-2">
        <Label for="playback-interval">步进间隔(ms)</Label>
        <Input
          id="playback-interval"
          name="playback-interval"
          type="number"
          min="200"
          step="100"
          bind:value={state.playbackIntervalMs}
          className="w-24"
          disabled={state.viewMode !== "timeline"}
        />
      </div>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <Button
          variant={state.autoPauseOnAlert ? "default" : "outline"}
          size="sm"
          on:click={() => (state.autoPauseOnAlert = !state.autoPauseOnAlert)}
          disabled={state.viewMode !== "timeline"}
        >
          告警自动停
        </Button>
      </div>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <Label className="text-[11px] whitespace-nowrap">关键事件</Label>
        <div class="flex flex-wrap items-center gap-2">
          <div class="flex min-h-[32px] max-w-[240px] flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-white/70 px-2 py-1">
            {#if state.jumpEventTokens.length === 0}
              <span class="text-[11px] text-slate-400">未选择</span>
            {:else}
              {#each state.jumpEventTokens as token}
                <Badge variant="secondary" className="font-mono">
                  {token}
                </Badge>
              {/each}
            {/if}
          </div>
          <div class="relative" bind:this={state.jumpDropdownAnchor}>
            <Button
              variant="ghost"
              size="sm"
              on:click={() => {
                if (state.jumpDropdownOpen) {
                  state.jumpDropdownOpen = false;
                } else {
                  openJumpDropdown();
                }
              }}
              disabled={state.viewMode !== "timeline"}
            >
              预设
            </Button>
            {#if state.jumpDropdownOpen}
              <div
                class={`absolute z-30 max-h-56 w-64 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg ${
                  state.jumpDropdownPlacement === "top" ? "bottom-full mb-1" : "top-full mt-1"
                }`}
              >
                {#if jumpOptions().length === 0}
                  <div class="px-3 py-2 text-[11px] text-slate-500">暂无事件</div>
                {:else}
                  {#each jumpOptions() as option}
                    <label class="flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-[11px] hover:bg-slate-50">
                      <div class="flex items-center gap-2">
                        <input
                          type="checkbox"
                          class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                          checked={state.jumpEventTokens.includes(option.value)}
                          on:change={() => toggleJumpEvent(option.value)}
                        />
                        <span class="font-mono text-slate-700">{option.value}</span>
                      </div>
                      {#if option.count !== null}
                        <span class="rounded-full bg-slate-100 px-1.5 text-[10px] text-slate-500">{option.count}</span>
                      {/if}
                    </label>
                  {/each}
                {/if}
              </div>
            {/if}
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          on:click={() => jumpToCustom(-1, state.jumpEventTokens)}
          disabled={state.viewMode !== "timeline"}
        >
          上一个关键
        </Button>
        <Button
          variant="outline"
          size="sm"
          on:click={() => jumpToCustom(1, state.jumpEventTokens)}
          disabled={state.viewMode !== "timeline"}
        >
          下一个关键
        </Button>
      </div>
      <div class="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span>拖动进度条可聚焦节点与事件</span>
        <span>Alt + 点击节点只看关联</span>
      </div>
    {/if}
  </div>
{/if}
