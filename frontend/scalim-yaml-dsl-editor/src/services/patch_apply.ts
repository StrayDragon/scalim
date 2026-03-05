import { state } from "$domain/state.svelte";
import type { PatchResult } from "$services/yaml_patch";

const MAX_UNDO = 50;

const yamlHasMergeKey = (yamlText: string): boolean => {
  const lines = String(yamlText || "").split(/\r?\n/);
  for (const line of lines) {
    const t = String(line || "").trimStart();
    if (!t) continue;
    if (t.startsWith("#")) continue;
    if (/^<<\s*:/.test(t)) return true;
  }
  return false;
};

const pushUndo = (beforeText: string) => {
  state.undoStack.push(beforeText);
  if (state.undoStack.length > MAX_UNDO) {
    state.undoStack.splice(0, state.undoStack.length - MAX_UNDO);
  }
};

export const canUndo = (): boolean => {
  return state.undoStack.length > 0;
};

export const undoLast = () => {
  if (!state.undoStack.length) return;
  const prev = state.undoStack.pop();
  if (typeof prev !== "string") return;
  state.yamlText = prev;
};

export const cancelPendingPatch = () => {
  state.pendingPatch = null;
};

export const confirmPendingPatch = () => {
  const pending = state.pendingPatch;
  if (!pending) return;
  // Best-effort safety: only apply if no drift.
  if (state.yamlText !== pending.beforeText) {
    state.pendingPatch = null;
    return;
  }
  pushUndo(pending.beforeText);
  state.yamlText = pending.afterText;
  state.pendingPatch = null;
};

export const applyPatchResult = (
  out: PatchResult,
  meta?: {
    title?: string;
    reason?: string;
  }
): { ok: true } | { ok: false; error: string } => {
  if (!out.ok) return { ok: false, error: out.error || "patch failed" };

  const beforeText = state.yamlText;
  const afterText = out.text;

  const title = String(meta?.title || "Apply changes");
  let planKind = out.plan?.kind || "safe";
  let planReason = String(meta?.reason || out.plan?.reason || "").trim() || undefined;

  if (out.decision) {
    state.pendingDecision = {
      title,
      beforeText,
      decision: out.decision
    };
    return { ok: true };
  }

  if (planKind === "safe" && afterText !== beforeText && yamlHasMergeKey(beforeText)) {
    planKind = "rewrite";
    const mergeReason = "YAML merge (<<) detected";
    planReason = planReason ? mergeReason + "; " + planReason : mergeReason;
  }

  if (planKind === "rewrite") {
    state.pendingPatch = {
      title,
      planKind,
      planReason,
      beforeText,
      afterText
    };
    return { ok: true };
  }

  if (afterText !== beforeText) pushUndo(beforeText);
  state.yamlText = afterText;
  return { ok: true };
};
