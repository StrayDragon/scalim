import type { PatchResult } from "../../services/yaml_patch.ts";
import { applyYamlEditOp, type YamlEditOp } from "../../services/yaml_edit_ops.ts";
import type { BlockAction } from "./types.ts";

export const blockActionToYamlEditOp = (action: BlockAction): YamlEditOp => {
  if (action.kind === "set") {
    return { kind: "set", path: action.path, value: action.value, createMissing: action.createMissing };
  }
  if (action.kind === "delete") {
    return { kind: "delete", path: action.path, pruneEmptyParents: action.pruneEmptyParents };
  }
  if (action.kind === "ensure_map") {
    return { kind: "ensure_map", path: action.path, createMissing: action.createMissing };
  }
  if (action.kind === "ensure_seq") {
    return { kind: "ensure_seq", path: action.path, createMissing: action.createMissing };
  }
  if (action.kind === "insert") {
    return { kind: "insert", path: action.path, index: action.index, value: action.value, valueKind: action.valueKind };
  }
  if (action.kind === "remove") {
    return { kind: "delete", path: action.path.concat([String(action.index)]), pruneEmptyParents: true };
  }
  return { kind: "move", path: action.path, from: action.from, to: action.to };
};

export const applyBlockAction = (yamlText: string, action: BlockAction): PatchResult => {
  const op: YamlEditOp = blockActionToYamlEditOp(action);
  return applyYamlEditOp(yamlText, op);
};
