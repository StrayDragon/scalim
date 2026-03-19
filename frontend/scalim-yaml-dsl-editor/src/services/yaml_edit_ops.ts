import type { PatchResult } from "./yaml_patch.ts";
import {
  ensureEmptyMapAtPathDeep,
  ensureEmptySeqAtPathDeep,
  insertInlineItemAtPath,
  insertStringItemAtPath,
  moveSeqItemAtPath,
  removeKeyAtPath,
  removeSeqItemAtPath,
  setScalarAtPathDeep
} from "./yaml_patch.ts";

export type YamlEditOp =
  | {
      kind: "set";
      path: string[];
      value: string | number | boolean | null;
      createMissing?: boolean;
    }
  | {
      kind: "ensure_map";
      path: string[];
      createMissing?: boolean;
    }
  | {
      kind: "ensure_seq";
      path: string[];
      createMissing?: boolean;
    }
  | {
      kind: "insert";
      path: string[];
      index: number;
      value: string;
      valueKind?: "string" | "inline";
    }
  | {
      kind: "delete";
      path: string[];
      pruneEmptyParents?: boolean;
    }
  | {
      kind: "move";
      path: string[];
      from: number;
      to: number;
    }
  | {
      kind: "rename";
      path: string[];
      fromKey: string;
      toKey: string;
    };

export const applyYamlEditOp = (yamlText: string, op: YamlEditOp): PatchResult => {
  if (!op || typeof op !== "object") return { ok: false, error: "patch: invalid op" };

  if (op.kind === "set") {
    const createMissing = typeof op.createMissing === "boolean" ? op.createMissing : true;
    return setScalarAtPathDeep(yamlText, op.path, op.value, { createMissing });
  }

  if (op.kind === "ensure_map") {
    const createMissing = typeof op.createMissing === "boolean" ? op.createMissing : true;
    return ensureEmptyMapAtPathDeep(yamlText, op.path, { createMissing });
  }

  if (op.kind === "ensure_seq") {
    const createMissing = typeof op.createMissing === "boolean" ? op.createMissing : true;
    return ensureEmptySeqAtPathDeep(yamlText, op.path, { createMissing });
  }

  if (op.kind === "insert") {
    const kind = op.valueKind || "string";
    if (kind === "inline") return insertInlineItemAtPath(yamlText, op.path, op.index, op.value);
    return insertStringItemAtPath(yamlText, op.path, op.index, op.value);
  }

  if (op.kind === "delete") {
    const prune = typeof op.pruneEmptyParents === "boolean" ? op.pruneEmptyParents : true;
    const last = op.path && op.path.length ? String(op.path[op.path.length - 1]) : "";
    if (/^\\d+$/.test(last) && op.path.length >= 2) {
      const parent = op.path.slice(0, -1);
      const idx = Number(last);
      return removeSeqItemAtPath(yamlText, parent, idx);
    }
    return removeKeyAtPath(yamlText, op.path, { pruneEmptyParents: prune });
  }

  if (op.kind === "move") {
    return moveSeqItemAtPath(yamlText, op.path, op.from, op.to);
  }

  return { ok: false, error: "patch: rename is not supported yet", plan: { kind: "rewrite", reason: "rename" } };
};
