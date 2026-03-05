<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import Button from "$components/ui/button.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { applyPatchResult } from "$services/patch_apply";
  import { composePatchResults } from "$services/patch_compose";
  import { lookupYamlLocation } from "$services/yaml_doc";
  import {
    detachAliasAtPath,
    ensureEmptyMapAtPathDeep,
    removeKeyAtPath,
    removeKeyAtPathKeepEmptyMap,
    setInlineValueAtPath,
    setScalarAtPathDeep
  } from "$services/yaml_patch";

  const close = () => {
    appState.pendingDecision = null;
  };

  const ensureNoDrift = (): boolean => {
    const pending = appState.pendingDecision;
    if (!pending) return false;
    if (appState.yamlText !== pending.beforeText) {
      close();
      return false;
    }
    return true;
  };

  const revealPath = (pathParts: string[] | null) => {
    if (!pathParts || !pathParts.length) return;
    const path = pathParts.join(".");
    const loc = lookupYamlLocation(path, appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };

  const applyOp = (yamlText: string, path: string[], op: any) => {
    if (!op || typeof op !== "object") return { ok: false as const, error: "patch: invalid decision op" };

    if (op.kind === "set_scalar") {
      return setScalarAtPathDeep(yamlText, path, op.value, { createMissing: Boolean(op.createMissing) });
    }
    if (op.kind === "set_inline") {
      return setInlineValueAtPath(yamlText, path, String(op.inlineValue || ""), { createMissing: Boolean(op.createMissing) });
    }
    if (op.kind === "ensure_map") {
      return ensureEmptyMapAtPathDeep(yamlText, path, { createMissing: Boolean(op.createMissing) });
    }
    if (op.kind === "remove_key") {
      const keepEmptyMap = Boolean(op.keepEmptyMap);
      const pruneEmptyParents = Boolean(op.pruneEmptyParents);
      if (keepEmptyMap) return removeKeyAtPathKeepEmptyMap(yamlText, path);
      return removeKeyAtPath(yamlText, path, { pruneEmptyParents });
    }
    return { ok: false as const, error: "patch: unsupported decision op: " + String(op.kind || "") };
  };

  const onEditTemplate = () => {
    if (!ensureNoDrift()) return;
    const pending = appState.pendingDecision;
    if (!pending) return;
    const decision = pending.decision;
    if (!decision || decision.kind !== "alias") return;

    const anchorPath = decision.alias.anchorPath;
    if (!anchorPath || !anchorPath.length) return;
    const targetPath = anchorPath.concat(decision.alias.remainingPath || []);

    close();
    const out = applyOp(appState.yamlText, targetPath, decision.op);
    applyPatchResult(out as any, { title: pending.title + " (template)" });
  };

  const onDetachAndApply = () => {
    if (!ensureNoDrift()) return;
    const pending = appState.pendingDecision;
    if (!pending) return;
    const decision = pending.decision;
    if (!decision || decision.kind !== "alias") return;

    const aliasPath = decision.alias.aliasPath || [];
    const opPath = (decision.op as any)?.path || [];

    close();
    const out = composePatchResults(appState.yamlText, [
      (t) => detachAliasAtPath(t, aliasPath),
      (t) => applyOp(t, opPath, decision.op) as any
    ]);
    applyPatchResult(out as any, { title: pending.title, reason: "alias detach" });
  };

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!appState.pendingDecision) return;
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    onDestroy(() => window.removeEventListener("keydown", onKeyDown));
  });
</script>

{#if appState.pendingDecision && appState.pendingDecision.decision.kind === "alias"}
  <div class="fixed inset-0 z-[10001]">
    <button type="button" class="absolute inset-0 bg-black/40" aria-label="close alias decision" onclick={close}></button>

    <div class="absolute left-1/2 top-1/2 w-[min(720px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border bg-white shadow-2xl">
      <div class="border-b bg-slate-50 px-4 py-3">
        <div class="text-sm font-semibold text-slate-800">{appState.pendingDecision.title}</div>
        <div class="mt-0.5 text-[11px] text-slate-500">
          检测到 YAML alias:<span class="font-mono text-slate-700">*{appState.pendingDecision.decision.alias.anchorName}</span>
          <span class="text-slate-400">·</span>
          请选择对 <span class="font-mono text-slate-700">{appState.pendingDecision.decision.alias.aliasPath.join(".")}</span> 的编辑策略
        </div>
      </div>

      <div class="space-y-3 px-4 py-4 text-xs text-slate-700">
        <div class="rounded-xl border bg-white p-3">
          <div class="text-xs font-semibold text-slate-800">选项</div>
          <div class="mt-1 text-[11px] text-slate-500">
            <div>“编辑共享模板”会修改 anchor 定义,影响所有引用该 alias 的位置.</div>
            <div>“拆分为实例”会把该处 alias 展开为独立配置,再应用本次修改.</div>
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={!appState.pendingDecision.decision.alias.anchorPath}
              on:click={onEditTemplate}
              title={appState.pendingDecision.decision.alias.anchorPath ? "修改 anchor 定义(影响全部引用)" : "未找到 anchor 定义位置"}
            >
              编辑共享模板
            </Button>
            <Button variant="outline" size="sm" on:click={onDetachAndApply} title="展开该处 alias 为独立配置(带 diff 预览)">
              拆分为实例 (detach)
            </Button>
            <Button variant="ghost" size="sm" on:click={close}>取消</Button>
          </div>
        </div>

        <div class="rounded-xl border bg-white p-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="text-xs font-semibold text-slate-800">定位</div>
            <div class="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                on:click={() => revealPath(appState.pendingDecision!.decision.alias.aliasPath)}
                title="定位到当前 alias"
              >
                定位 alias
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!appState.pendingDecision.decision.alias.anchorPath}
                on:click={() => revealPath(appState.pendingDecision!.decision.alias.anchorPath)}
                title="定位到 anchor 定义"
              >
                定位 anchor
              </Button>
            </div>
          </div>

          {#if !appState.pendingDecision.decision.alias.anchorPath}
            <div class="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
              未在文档中找到 <span class="font-mono">&{appState.pendingDecision.decision.alias.anchorName}</span> 的定义.你仍可 detach,或在 YAML 中手动处理.
            </div>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

