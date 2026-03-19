import {
  isAlias,
  isMap,
  isScalar,
  isSeq,
  parse,
  parseDocument,
  Scalar,
  stringify,
  type Node,
  type Pair,
  type ParsedNode,
  type YAMLMap,
  type YAMLSeq
} from "yaml";

export type PatchPlan = { kind: "safe" | "rewrite"; reason?: string };

export type PatchDecision =
  | {
      kind: "alias";
      op:
        | { kind: "set_scalar"; path: string[]; value: string | number | boolean | null; createMissing: boolean }
        | { kind: "set_inline"; path: string[]; inlineValue: string; createMissing: boolean }
        | { kind: "ensure_map"; path: string[]; createMissing: boolean }
        | { kind: "remove_key"; path: string[]; pruneEmptyParents: boolean; keepEmptyMap: boolean };
      alias: {
        aliasPath: string[];
        anchorName: string;
        anchorPath: string[] | null;
        remainingPath: string[];
      };
    };

export type PatchOk = { ok: true; text: string; plan: PatchPlan; decision?: PatchDecision };
export type PatchErr = { ok: false; error: string; plan?: PatchPlan; decision?: PatchDecision };
export type PatchResult = PatchOk | PatchErr;

const lineStartOffset = (text: string, offset: number): number => {
  let i = Math.min(Math.max(0, offset), text.length);
  while (i > 0 && text.charCodeAt(i - 1) !== 10) i -= 1;
  return i;
};

const nodeStartOffset = (node: any): number | null => {
  const range = node?.range;
  if (Array.isArray(range) && typeof range[0] === "number") return range[0];
  const token = node?.srcToken;
  const tokenRange = token?.range;
  if (Array.isArray(tokenRange) && typeof tokenRange[0] === "number") return tokenRange[0];
  return null;
};

const countIndentSpaces = (text: string, offset: number): number => {
  let i = offset - 1;
  while (i >= 0 && text.charCodeAt(i) !== 10) i -= 1;
  const lineStart = i + 1;
  let n = 0;
  while (lineStart + n < text.length && text.charCodeAt(lineStart + n) === 32) n += 1;
  return n;
};

const scalarKeyToString = (keyNode: any): string => {
  if (isScalar(keyNode)) return String((keyNode as any).value ?? "");
  return String(keyNode?.value ?? "");
};

const getIn = (root: Node | null, path: string[]): Node | null => {
  let current: Node | null = root;
  for (const seg of path) {
    if (!current) return null;
    if (isMap(current)) {
      const mapNode = current as YAMLMap;
      let next: Node | null = null;
      for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
        if (scalarKeyToString(pair.key) === seg) {
          next = (pair.value as Node | null) || null;
          break;
        }
      }
      current = next;
      continue;
    }
    if (isSeq(current)) {
      const idx = Number(seg);
      if (!Number.isFinite(idx) || idx < 0) return null;
      const seqNode = current as YAMLSeq;
      current = ((seqNode.items as Node[])[idx] as Node | undefined) || null;
      continue;
    }
    return null;
  }
  return current;
};

const findPairInMap = (mapNode: YAMLMap, key: string): Pair<ParsedNode, ParsedNode | null> | null => {
  for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
    if (scalarKeyToString(pair.key) === key) return pair;
  }
  return null;
};

type AliasHit = { aliasNode: Node; aliasPath: string[]; remainingPath: string[] };

const findAliasHitInPath = (root: Node | null, path: string[]): AliasHit | null => {
  let current: Node | null = root;
  for (let i = 0; i < path.length; i += 1) {
    if (!current) return null;
    if (isAlias(current)) {
      return { aliasNode: current as Node, aliasPath: path.slice(0, i), remainingPath: path.slice(i) };
    }

    const seg = path[i] as string;
    if (isMap(current)) {
      const mapNode = current as YAMLMap;
      const pair = findPairInMap(mapNode, seg);
      current = (pair?.value as Node | null) || null;
      continue;
    }
    if (isSeq(current)) {
      const idx = Number(seg);
      if (!Number.isFinite(idx) || idx < 0) return null;
      const seqNode = current as YAMLSeq;
      current = ((seqNode.items as Node[])[idx] as Node | undefined) || null;
      continue;
    }
    return null;
  }

  if (current && isAlias(current)) {
    return { aliasNode: current as Node, aliasPath: path.slice(0), remainingPath: [] };
  }
  return null;
};

const findAnchorPathInDoc = (node: Node | null, path: string[], anchorName: string): string[] | null => {
  if (!node) return null;

  const anchor = (node as any).anchor;
  if (typeof anchor === "string" && anchor && anchor === anchorName) return path;

  if (isMap(node)) {
    const mapNode = node as YAMLMap;
    for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
      const key = scalarKeyToString(pair.key);
      const valueNode = (pair.value as Node | null) || null;
      const hit = findAnchorPathInDoc(valueNode, path.concat([key]), anchorName);
      if (hit) return hit;
    }
  } else if (isSeq(node)) {
    const seqNode = node as YAMLSeq;
    const items = (seqNode.items as Node[]) || [];
    for (let i = 0; i < items.length; i += 1) {
      const hit = findAnchorPathInDoc(items[i] || null, path.concat([String(i)]), anchorName);
      if (hit) return hit;
    }
  }
  return null;
};

const aliasDecisionFor = (
  root: Node | null,
  fullPath: string[],
  op: PatchDecision["op"]
): PatchDecision | null => {
  if (!root || !fullPath.length) return null;
  const aliasHit = findAliasHitInPath(root, fullPath);
  if (!aliasHit) return null;

  // Only require a decision when the edit goes *through* the alias to a deeper key/index.
  if (!aliasHit.remainingPath.length) return null;

  const anchorName = String((aliasHit.aliasNode as any)?.source || "").trim();
  const anchorPath = anchorName ? findAnchorPathInDoc(root, [], anchorName) : null;

  return {
    kind: "alias",
    op,
    alias: {
      aliasPath: aliasHit.aliasPath,
      anchorName,
      anchorPath,
      remainingPath: aliasHit.remainingPath
    }
  };
};

const formatScalarReplacement = (oldNode: any, value: string | number | boolean | null): string => {
  const stripTrailingNewlines = (text: string): string => {
    return text.replace(/\n+$/, "");
  };

  // Scalar#toString does not reliably preserve string type (e.g. "true"/"001" can round-trip as boolean/number).
  // Use YAML.stringify for stable scalar literals, and preserve existing quote style when possible.
  const preferType = typeof oldNode?.type === "string" ? oldNode.type : null;
  const opts: any = {
    directives: false,
    blockQuote: false,
    doubleQuotedAsJSON: true
  };

  if (typeof value === "string") {
    if (preferType === Scalar.QUOTE_SINGLE) {
      opts.defaultStringType = Scalar.QUOTE_SINGLE;
      opts.singleQuote = true;
    } else if (preferType === Scalar.QUOTE_DOUBLE) {
      opts.defaultStringType = Scalar.QUOTE_DOUBLE;
    } else if (preferType === Scalar.PLAIN) {
      opts.defaultStringType = Scalar.PLAIN;
    }
  }

  return stripTrailingNewlines(stringify(value as any, opts));
};

const applyRangePatch = (text: string, start: number, end: number, replacement: string): string => {
  return text.slice(0, start) + replacement + text.slice(end);
};

export const detachAliasAtPath = (yamlText: string, aliasPath: string[]): PatchResult => {
  if (!aliasPath.length) return { ok: false, error: "patch: empty path" };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const getNodeWithParent = (
    node: Node | null,
    path: string[]
  ): { node: Node | null; parent: Node | null; parentKey: string | number | null; parentKind: "map" | "seq" | null } => {
    let current: Node | null = node;
    let parent: Node | null = null;
    let parentKey: string | number | null = null;
    let parentKind: "map" | "seq" | null = null;

    for (const seg of path) {
      if (!current) return { node: null, parent, parentKey, parentKind };
      if (isMap(current)) {
        const mapNode = current as YAMLMap;
        const pair = findPairInMap(mapNode, seg);
        parent = current;
        parentKind = "map";
        parentKey = seg;
        current = (pair?.value as Node | null) || null;
        continue;
      }
      if (isSeq(current)) {
        const idx = Number(seg);
        if (!Number.isFinite(idx) || idx < 0) return { node: null, parent, parentKey, parentKind };
        const seqNode = current as YAMLSeq;
        parent = current;
        parentKind = "seq";
        parentKey = idx;
        current = ((seqNode.items as Node[])[idx] as Node | undefined) || null;
        continue;
      }
      return { node: null, parent, parentKey, parentKind };
    }

    return { node: current, parent, parentKey, parentKind };
  };

  const resolved = getNodeWithParent(root, aliasPath);
  const aliasNode = resolved.node;
  if (!aliasNode) return { ok: false, error: "patch: node not found", plan: { kind: "rewrite", reason: "missing node" } };
  if (!isAlias(aliasNode)) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  const anchorName = String((aliasNode as any).source || "").trim();
  if (!anchorName) return { ok: false, error: "patch: alias has empty source", plan: { kind: "rewrite", reason: "alias" } };

  const anchorPath = findAnchorPathInDoc(root, [], anchorName);
  if (!anchorPath) return { ok: false, error: "patch: unknown anchor: " + anchorName, plan: { kind: "rewrite", reason: "alias" } };

  const anchorNode = getIn(root, anchorPath);
  if (!anchorNode) return { ok: false, error: "patch: anchor node not found: " + anchorName, plan: { kind: "rewrite", reason: "alias" } };
  if (!isMap(anchorNode) && !isSeq(anchorNode)) {
    return {
      ok: false,
      error: "patch: cannot detach alias of non-container anchor '" + anchorName + "'",
      plan: { kind: "rewrite", reason: "alias" }
    };
  }

  const anchorRange = (anchorNode as any).range;
  if (!Array.isArray(anchorRange) || typeof anchorRange[0] !== "number" || typeof anchorRange[1] !== "number") {
    return { ok: false, error: "patch: anchor missing range", plan: { kind: "rewrite", reason: "missing range" } };
  }
  const anchorStart = anchorRange[0] as number;
  const anchorEnd = anchorRange[1] as number;
  const anchorIndent = countIndentSpaces(yamlText, anchorStart);
  const anchorIndentStr = anchorIndent ? " ".repeat(anchorIndent) : "";
  const anchorRaw = yamlText.slice(anchorStart, anchorEnd);

  const rawLines = anchorRaw.split(/\r?\n/);
  while (rawLines.length && rawLines[rawLines.length - 1] === "") rawLines.pop();
  const normalizedLines = rawLines.map((line) => {
    if (!anchorIndentStr) return line;
    return line.startsWith(anchorIndentStr) ? line.slice(anchorIndentStr.length) : line;
  });

  if (!normalizedLines.length) return { ok: false, error: "patch: empty anchor body", plan: { kind: "rewrite", reason: "alias" } };

  const aliasRange = (aliasNode as any).range;
  if (!Array.isArray(aliasRange) || typeof aliasRange[0] !== "number" || typeof aliasRange[1] !== "number") {
    return { ok: false, error: "patch: alias missing range", plan: { kind: "rewrite", reason: "missing range" } };
  }

  let patchStart = aliasRange[0] as number;
  const patchEnd = aliasRange[1] as number;
  if (patchStart > 0 && yamlText.charCodeAt(patchStart - 1) === 32) patchStart -= 1;

  if (resolved.parentKind === "seq") {
    const baseIndent = countIndentSpaces(yamlText, patchStart);
    const childIndentStr = " ".repeat(baseIndent + 2);
    const first = normalizedLines[0] as string;
    const rest = normalizedLines.slice(1).map((line) => "\n" + childIndentStr + line).join("");
    const replacement = first + rest;
    return { ok: true, text: applyRangePatch(yamlText, patchStart, patchEnd, replacement), plan: { kind: "rewrite", reason: "alias detach" } };
  }

  // Default: treat as map value replacement (`key: *alias` -> `key:\n  ...`).
  const keyIndent = countIndentSpaces(yamlText, patchStart);
  const childIndentStr = " ".repeat(keyIndent + 2);
  const indented = normalizedLines.map((line) => childIndentStr + line).join("\n");
  const replacement = "\n" + indented;
  return { ok: true, text: applyRangePatch(yamlText, patchStart, patchEnd, replacement), plan: { kind: "rewrite", reason: "alias detach" } };
};

const isPlainObject = (value: any): value is Record<string, any> => {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
};

const isIndexSegment = (seg: string): boolean => {
  return /^\d+$/.test(seg);
};

const normalizePath = (path: string[]): Array<string | number> => {
  return path.map((seg) => {
    const s = String(seg);
    return isIndexSegment(s) ? Number(s) : s;
  });
};

const extractLeadingCommentBlock = (yamlText: string): string => {
  const lines = yamlText.split(/\r?\n/);
  let i = 0;
  for (; i < lines.length; i += 1) {
    const t = (lines[i] || "").trim();
    if (!t) continue;
    if (t.startsWith("#")) continue;
    break;
  }
  return lines.slice(0, i).join("\n").trimEnd();
};

const stringifyWithLeadingCommentBlock = (originalText: string, value: any): string => {
  const preamble = extractLeadingCommentBlock(originalText);
  const body = String(
    stringify(value as any, {
      directives: false,
      blockQuote: false,
      doubleQuotedAsJSON: true
    } as any)
  ).replace(/^\s+/, "");

  const cleanedBody = body.replace(/\n+$/, "") + "\n";
  if (!preamble) return cleanedBody;
  return preamble + "\n\n" + cleanedBody;
};

type DeepEditResult = { ok: true; value: any } | { ok: false; error: string };

const deepSetInPlace = (root: any, path: string[], value: any, createMissing: boolean): DeepEditResult => {
  const normalized = normalizePath(path);
  if (!normalized.length) return { ok: false, error: "patch: empty path" };

  let current = root;
  let parent: any = null;
  let parentKey: string | number | null = null;

  const replaceCurrent = (next: any) => {
    if (parentKey == null) root = next;
    else parent[parentKey] = next;
    current = next;
  };

  for (let i = 0; i < normalized.length; i += 1) {
    const key = normalized[i] as any;
    const isLast = i === normalized.length - 1;
    const nextKey = !isLast ? (normalized[i + 1] as any) : null;
    const nextWantsArray = typeof nextKey === "number";

    if (isLast) {
      if (typeof key === "number") {
        if (!Array.isArray(current)) {
          if (!createMissing) return { ok: false, error: "patch: parent is not a sequence" };
          replaceCurrent([]);
        }
        while ((current as any[]).length <= key) (current as any[]).push(null);
        (current as any[])[key] = value;
        return { ok: true, value: root };
      }

      if (!isPlainObject(current)) {
        if (!createMissing) return { ok: false, error: "patch: parent is not a mapping" };
        replaceCurrent({});
      }
      (current as any)[key] = value;
      return { ok: true, value: root };
    }

    if (typeof key === "number") {
      if (!Array.isArray(current)) {
        if (!createMissing) return { ok: false, error: "patch: parent is not a sequence" };
        replaceCurrent([]);
      }
      while ((current as any[]).length <= key) (current as any[]).push(nextWantsArray ? [] : {});
      parent = current;
      parentKey = key;
      current = (current as any[])[key];
      continue;
    }

    if (!isPlainObject(current)) {
      if (!createMissing) return { ok: false, error: "patch: parent is not a mapping" };
      replaceCurrent({});
    }

    if (!Object.prototype.hasOwnProperty.call(current, key) || (current as any)[key] == null) {
      if (!createMissing) return { ok: false, error: "patch: parent not found" };
      (current as any)[key] = nextWantsArray ? [] : {};
    } else if (nextWantsArray && !Array.isArray((current as any)[key])) {
      (current as any)[key] = [];
    } else if (!nextWantsArray && typeof nextKey === "string" && !isPlainObject((current as any)[key])) {
      (current as any)[key] = {};
    }

    parent = current;
    parentKey = key;
    current = (current as any)[key];
  }

  return { ok: true, value: root };
};

const isEmptyContainer = (value: any): boolean => {
  if (Array.isArray(value)) return value.length === 0;
  if (isPlainObject(value)) return Object.keys(value).length === 0;
  return false;
};

const deepDeleteInPlace = (root: any, path: string[], pruneEmptyParents: boolean): DeepEditResult => {
  const normalized = normalizePath(path);
  if (!normalized.length) return { ok: false, error: "patch: empty path" };

  let current = root;
  const stack: Array<{ parent: any; key: string | number }> = [];

  for (let i = 0; i < normalized.length - 1; i += 1) {
    const key = normalized[i] as any;
    if (typeof key === "number") {
      if (!Array.isArray(current) || key < 0 || key >= (current as any[]).length) return { ok: true, value: root };
      stack.push({ parent: current, key });
      current = (current as any[])[key];
      continue;
    }
    if (!isPlainObject(current) || !Object.prototype.hasOwnProperty.call(current, key)) return { ok: true, value: root };
    stack.push({ parent: current, key });
    current = (current as any)[key];
  }

  const leaf = normalized[normalized.length - 1] as any;
  if (typeof leaf === "number") {
    if (Array.isArray(current) && leaf >= 0 && leaf < (current as any[]).length) (current as any[]).splice(leaf, 1);
  } else {
    if (isPlainObject(current)) delete (current as any)[leaf];
  }

  if (!pruneEmptyParents) return { ok: true, value: root };

  let node = current;
  for (let i = stack.length - 1; i >= 0; i -= 1) {
    if (!isEmptyContainer(node)) break;
    const { parent, key } = stack[i];
    if (typeof key === "number") {
      if (Array.isArray(parent) && key >= 0 && key < (parent as any[]).length) (parent as any[]).splice(key, 1);
    } else if (isPlainObject(parent)) {
      delete (parent as any)[key];
    }
    node = parent;
  }

  return { ok: true, value: root };
};

const appendKeyToMap = (yamlText: string, mapNode: YAMLMap, key: string, replacement: string): PatchResult => {
  const range = (mapNode as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }

  // If the map is an empty flow mapping ("{}"), convert it into a block mapping to allow further patching.
  // Example:
  //   field_id: {}
  // becomes
  //   field_id:
  //     name: ...
  if ((mapNode as any).flow) {
    const items = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) || [];
    if (items.length === 0) {
      const start = range[0] as number;
      const end = range[1] as number;
      const valueNeedsTrailingNewline = end < yamlText.length && yamlText.charCodeAt(end) !== 10;
      const lineStart = lineStartOffset(yamlText, start);
      const linePrefix = yamlText.slice(lineStart, start);
      const isOwnLine = linePrefix.trim().length === 0;

      // If "{}" is already on its own indented line, convert in-place without introducing a blank line.
      //   a:
      //     {}
      // -> a:
      //     x: 1
      if (isOwnLine) {
        const insertText = key + ": " + replacement + (valueNeedsTrailingNewline ? "\n" : "");
        return { ok: true, text: applyRangePatch(yamlText, start, end, insertText), plan: { kind: "safe" } };
      }

      // Inline flow map: "a: {}". Convert to block mapping under "a".
      const baseIndent = countIndentSpaces(yamlText, start);
      const childIndentStr = " ".repeat(baseIndent + 2);
      const insertText = "\n" + childIndentStr + key + ": " + replacement + (valueNeedsTrailingNewline ? "\n" : "");
      return { ok: true, text: applyRangePatch(yamlText, start, end, insertText), plan: { kind: "safe" } };
    }
    return {
      ok: false,
      error: "patch: cannot append key to flow mapping; edit YAML directly",
      plan: { kind: "rewrite", reason: "flow map" }
    };
  }

  const insertAt = range[1] as number;
  const firstPair = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>)[0];
  const firstKeyOffset = firstPair ? nodeStartOffset(firstPair.key) : null;
  const indent = firstKeyOffset != null ? countIndentSpaces(yamlText, firstKeyOffset) : 0;
  const indentStr = " ".repeat(indent);

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const insertText = (needsLeadingNewline ? "\n" : "") + indentStr + key + ": " + replacement + "\n";

  return {
    ok: true,
    text: applyRangePatch(yamlText, insertAt, insertAt, insertText),
    plan: { kind: "safe" }
  };
};

const appendBlockKeyToMap = (yamlText: string, mapNode: YAMLMap, key: string, blockValue: string): PatchResult => {
  const range = (mapNode as any).range;
  if (!Array.isArray(range) || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }

  const insertAt = range[1] as number;
  const firstPair = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>)[0];
  const firstKeyOffset = firstPair ? nodeStartOffset(firstPair.key) : null;
  const indent = firstKeyOffset != null ? countIndentSpaces(yamlText, firstKeyOffset) : 0;
  const indentStr = " ".repeat(indent);

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const value = String(blockValue || "");
  const normalizedValue = value.endsWith("\n") ? value : value + "\n";
  const insertText = (needsLeadingNewline ? "\n" : "") + indentStr + key + ":\n" + normalizedValue;

  return {
    ok: true,
    text: applyRangePatch(yamlText, insertAt, insertAt, insertText),
    plan: { kind: "safe" }
  };
};

export const setInlineValueAtPath = (
  yamlText: string,
  path: string[],
  inlineValue: string,
  opts?: { createMissing?: boolean }
): PatchResult => {
  const cleaned = String(inlineValue || "").trim();
  if (!cleaned) return { ok: false, error: "patch: empty inline value" };
  if (cleaned.includes("\n")) return { ok: false, error: "patch: inline value must be single-line", plan: { kind: "rewrite", reason: "multiline" } };
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  if (!path.length) return { ok: false, error: "patch: empty path" };

  const decision = aliasDecisionFor(root, path, { kind: "set_inline", path, inlineValue: cleaned, createMissing });
  if (decision) return { ok: true, text: yamlText, plan: { kind: "rewrite", reason: "alias" }, decision };

  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;

  const parentNode = getIn(root, parentPath);
  if (!parentNode) return { ok: false, error: "patch: parent not found", plan: { kind: "rewrite", reason: "parent not found" } };
  if (!isMap(parentNode)) {
    return { ok: false, error: "patch: parent is not a mapping", plan: { kind: "rewrite", reason: "parent not a mapping" } };
  }

  const mapNode = parentNode as YAMLMap;
  const pair = findPairInMap(mapNode, key);
  if (!pair) {
    if (createMissing) return appendKeyToMap(yamlText, mapNode, key, cleaned);
    return { ok: false, error: "patch: key not found: " + key, plan: { kind: "rewrite", reason: "key missing" } };
  }

  const node = (pair.value as Node | null) || null;
  if (!node) return { ok: false, error: "patch: missing value node", plan: { kind: "rewrite", reason: "missing node" } };

  const range = (node as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing value range", plan: { kind: "rewrite", reason: "missing range" } };
  }

  const start = range[0] as number;
  const end = range[1] as number;
  return { ok: true, text: applyRangePatch(yamlText, start, end, cleaned), plan: { kind: "safe" } };
};

const appendAnchoredBlockKeyToMap = (
  yamlText: string,
  mapNode: YAMLMap,
  key: string,
  anchor: string,
  blockLines: string[]
): PatchResult => {
  const range = (mapNode as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }

  const renderIndentedBlock = (indentSpaces: number) => {
    const indentStr = " ".repeat(indentSpaces);
    const normalized = (blockLines || []).map((line) => indentStr + String(line || ""));
    return normalized.join("\n");
  };

  if ((mapNode as any).flow) {
    const items = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) || [];
    if (items.length !== 0) {
      return {
        ok: false,
        error: "patch: cannot append key to flow mapping; edit YAML directly",
        plan: { kind: "rewrite", reason: "flow map" }
      };
    }

    const start = range[0] as number;
    const end = range[1] as number;
    const valueNeedsTrailingNewline = end < yamlText.length && yamlText.charCodeAt(end) !== 10;
    const lineStart = lineStartOffset(yamlText, start);
    const linePrefix = yamlText.slice(lineStart, start);
    const isOwnLine = linePrefix.trim().length === 0;

    const baseIndent = countIndentSpaces(yamlText, start);
    const keyIndentSpaces = isOwnLine ? baseIndent : baseIndent + 2;
    const keyIndentStr = " ".repeat(keyIndentSpaces);
    const nestedIndentSpaces = keyIndentSpaces + 2;
    const block = renderIndentedBlock(nestedIndentSpaces);

    const lines = [keyIndentStr + key + ": &" + anchor];
    if (blockLines && blockLines.length) lines.push(block);
    const body = lines.join("\n");
    const replacement = (isOwnLine ? "" : "\n") + body + (valueNeedsTrailingNewline ? "\n" : "");

    return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
  }

  const insertAt = range[1] as number;
  const firstPair = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>)[0];
  const firstKeyOffset = firstPair ? nodeStartOffset(firstPair.key) : null;
  const keyIndentSpaces = firstKeyOffset != null ? countIndentSpaces(yamlText, firstKeyOffset) : 0;
  const keyIndentStr = " ".repeat(keyIndentSpaces);
  const nestedIndentSpaces = keyIndentSpaces + 2;
  const block = renderIndentedBlock(nestedIndentSpaces);

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const lines = [keyIndentStr + key + ": &" + anchor];
  if (blockLines && blockLines.length) lines.push(block);
  const body = lines.join("\n") + "\n";
  const insertText = (needsLeadingNewline ? "\n" : "") + body;

  return {
    ok: true,
    text: applyRangePatch(yamlText, insertAt, insertAt, insertText),
    plan: { kind: "safe" }
  };
};

export const appendAnchoredBlockEntryAtPath = (
  yamlText: string,
  mapPath: string[],
  key: string,
  anchor: string,
  blockLines: string[]
): PatchResult => {
  const cleanedKey = String(key || "").trim();
  const cleanedAnchor = String(anchor || "").trim();
  if (!cleanedKey) return { ok: false, error: "patch: empty key" };
  if (!cleanedAnchor) return { ok: false, error: "patch: empty anchor" };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!mapPath.length) return { ok: false, error: "patch: empty path" };

  const node = getIn(root, mapPath);
  if (!node) return { ok: false, error: "patch: map not found", plan: { kind: "rewrite", reason: "missing map" } };
  if (isAlias(node)) {
    return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
  }
  if (!isMap(node)) return { ok: false, error: "patch: value is not a mapping", plan: { kind: "rewrite", reason: "non-mapping" } };

  const mapNode = node as YAMLMap;
  if (findPairInMap(mapNode, cleanedKey)) {
    return { ok: false, error: "patch: key already exists: " + cleanedKey };
  }

  return appendAnchoredBlockKeyToMap(yamlText, mapNode, cleanedKey, cleanedAnchor, blockLines);
};

export const setScalarAtPath = (
  yamlText: string,
  path: string[],
  value: string | number | boolean | null,
  opts?: { createMissing?: boolean }
): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  if (!path.length) return { ok: false, error: "patch: empty path" };
  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;

  const parentNode = getIn(root, parentPath);
  if (!parentNode) return { ok: false, error: "patch: parent not found", plan: { kind: "rewrite", reason: "parent not found" } };
  if (!isMap(parentNode)) {
    return { ok: false, error: "patch: parent is not a mapping", plan: { kind: "rewrite", reason: "parent not a mapping" } };
  }

  const mapNode = parentNode as YAMLMap;
  const pair = findPairInMap(mapNode, key);
  if (!pair) {
    if (opts && opts.createMissing) {
      const replacement = formatScalarReplacement(null, value);
      return appendKeyToMap(yamlText, mapNode, key, replacement);
    }
    return { ok: false, error: "patch: key not found: " + key, plan: { kind: "rewrite", reason: "key missing" } };
  }

  const node = (pair.value as Node | null) || null;
  if (!node) return { ok: false, error: "patch: missing value node", plan: { kind: "rewrite", reason: "missing node" } };
  if (isAlias(node)) {
    return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
  }
  if (!isScalar(node)) {
    return { ok: false, error: "patch: value is not scalar", plan: { kind: "rewrite", reason: "non-scalar" } };
  }

  const range = (node as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing scalar range", plan: { kind: "rewrite", reason: "missing range" } };
  }

  const start = range[0] as number;
  const end = range[1] as number;
  const replacement = formatScalarReplacement(node, value);
  return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
};

const indentForMapKeys = (yamlText: string, mapNode: YAMLMap): number => {
  const firstPair = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>)[0];
  const firstKeyOffset = firstPair ? nodeStartOffset(firstPair.key) : null;
  if (firstKeyOffset != null) return countIndentSpaces(yamlText, firstKeyOffset);
  const range = (mapNode as any).range;
  if (Array.isArray(range) && typeof range[0] === "number") return countIndentSpaces(yamlText, range[0] as number);
  return 0;
};

const setScalarAtPathDeepSafe = (
  yamlText: string,
  path: string[],
  value: string | number | boolean | null,
  opts?: { createMissing?: boolean }
): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  if (!path.length) return { ok: false, error: "patch: empty path" };

  // Fast path: if parent exists, delegate to existing safe patcher.
  {
    let doc: any;
    try {
      doc = parseDocument(yamlText, { keepSourceTokens: true });
    } catch (err: any) {
      return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
    }
    const root = (doc?.contents as Node | null) || null;
    if (!root) return { ok: false, error: "YAML document is empty" };

    const decision = aliasDecisionFor(root, path, { kind: "set_scalar", path, value, createMissing });
    if (decision) return { ok: true, text: yamlText, plan: { kind: "rewrite", reason: "alias" }, decision };

    const parentNode = getIn(root, path.slice(0, -1));
    if (parentNode && isMap(parentNode)) {
      return setScalarAtPath(yamlText, path, value, { createMissing });
    }
  }

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!isMap(root)) return { ok: false, error: "patch: root is not a mapping", plan: { kind: "rewrite", reason: "root not a mapping" } };

  const decision = aliasDecisionFor(root, path, { kind: "ensure_map", path, createMissing });
  if (decision) return { ok: true, text: yamlText, plan: { kind: "rewrite", reason: "alias" }, decision };

  const parentPath = path.slice(0, -1);
  const leafKey = path[path.length - 1] as string;

  let current: Node = root as any;
  let currentMap = current as YAMLMap;
  let missingAt = parentPath.length;

  for (let i = 0; i < parentPath.length; i += 1) {
    const seg = parentPath[i] as string;
    if (!isMap(current)) return { ok: false, error: "patch: parent is not a mapping", plan: { kind: "rewrite", reason: "non-mapping parent" } };
    currentMap = current as YAMLMap;
    const pair = findPairInMap(currentMap, seg);
    if (!pair || !pair.value) {
      missingAt = i;
      break;
    }
    const next = (pair.value as Node | null) || null;
    if (!next || !isMap(next)) {
      return { ok: false, error: "patch: existing node is not a mapping: " + seg, plan: { kind: "rewrite", reason: "non-mapping node" } };
    }
    current = next;
  }

  if (missingAt === parentPath.length) {
    // Parent exists but wasn't detected above due to non-map; fallback to setScalarAtPath behavior.
    return setScalarAtPath(yamlText, path, value, { createMissing });
  }
  if (!createMissing) {
    return { ok: false, error: "patch: parent not found", plan: { kind: "rewrite", reason: "parent not found" } };
  }

  const remaining = parentPath.slice(missingAt);
  const segmentsToCreate = remaining.concat([leafKey]);

  const range = (currentMap as any).range;
  if (!Array.isArray(range) || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }
  const insertAt = range[1] as number;
  const baseIndent = indentForMapKeys(yamlText, currentMap);
  const indentStep = 2;

  const replacement = formatScalarReplacement(null, value);
  let block = "";
  let indent = baseIndent;
  for (let i = 0; i < segmentsToCreate.length - 1; i += 1) {
    block += " ".repeat(indent) + segmentsToCreate[i] + ":\n";
    indent += indentStep;
  }
  block += " ".repeat(indent) + segmentsToCreate[segmentsToCreate.length - 1] + ": " + replacement + "\n";

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const insertText = (needsLeadingNewline ? "\n" : "") + block;

  return { ok: true, text: applyRangePatch(yamlText, insertAt, insertAt, insertText), plan: { kind: "safe" } };
};

export const setScalarAtPathDeep = (
  yamlText: string,
  path: string[],
  value: string | number | boolean | null,
  opts?: { createMissing?: boolean }
): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  const out = setScalarAtPathDeepSafe(yamlText, path, value, { createMissing });
  if (out.ok) return out;
  if (!out.plan || out.plan.kind !== "rewrite") return out;

  let root: any;
  try {
    root = parse(yamlText);
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown"), plan: out.plan };
  }
  if (!isPlainObject(root) && !Array.isArray(root)) root = {};

  const edit = deepSetInPlace(root, path, value, createMissing);
  if (!edit.ok) return { ok: false, error: edit.error, plan: out.plan };

  return {
    ok: true,
    text: stringifyWithLeadingCommentBlock(yamlText, edit.value),
    plan: { kind: "rewrite", reason: out.plan.reason || "unsafe patch" }
  };
};

const ensureEmptyMapAtPathDeepSafe = (yamlText: string, path: string[], opts?: { createMissing?: boolean }): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  if (!path.length) return { ok: false, error: "patch: empty path" };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!isMap(root)) return { ok: false, error: "patch: root is not a mapping", plan: { kind: "rewrite", reason: "root not a mapping" } };

  const parentPath = path.slice(0, -1);
  const leafKey = path[path.length - 1] as string;

  const parentNode = getIn(root, parentPath);
  if (parentNode && isMap(parentNode)) {
    const mapNode = parentNode as YAMLMap;
    const pair = findPairInMap(mapNode, leafKey);
    if (pair && pair.value) {
      const valueNode = pair.value as Node;
      if (isAlias(valueNode)) {
        return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
      }
      if (isMap(valueNode)) return { ok: true, text: yamlText, plan: { kind: "safe" } };
      const range = (valueNode as any).range;
      if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
        return { ok: false, error: "patch: missing value range", plan: { kind: "rewrite", reason: "missing range" } };
      }
      return { ok: true, text: applyRangePatch(yamlText, range[0] as number, range[1] as number, "{}"), plan: { kind: "safe" } };
    }

    if (createMissing) return appendKeyToMap(yamlText, mapNode, leafKey, "{}");
    return { ok: false, error: "patch: key not found: " + leafKey, plan: { kind: "rewrite", reason: "key missing" } };
  }

  if (!createMissing) return { ok: false, error: "patch: parent not found", plan: { kind: "rewrite", reason: "parent not found" } };

  // Create missing parent mappings and add the leaf key as an empty mapping.
  const deepKey = path[path.length - 1] as string;
  const parentSegments = path.slice(0, -1);

  let current: Node = root as any;
  let currentMap = current as YAMLMap;
  let missingAt = parentSegments.length;

  for (let i = 0; i < parentSegments.length; i += 1) {
    const seg = parentSegments[i] as string;
    if (!isMap(current)) return { ok: false, error: "patch: parent is not a mapping", plan: { kind: "rewrite", reason: "non-mapping parent" } };
    currentMap = current as YAMLMap;
    const pair = findPairInMap(currentMap, seg);
    if (!pair || !pair.value) {
      missingAt = i;
      break;
    }
    const next = (pair.value as Node | null) || null;
    if (!next || !isMap(next)) {
      return { ok: false, error: "patch: existing node is not a mapping: " + seg, plan: { kind: "rewrite", reason: "non-mapping node" } };
    }
    current = next;
  }

  const remaining = parentSegments.slice(missingAt);
  const segmentsToCreate = remaining.concat([deepKey]);

  const range = (currentMap as any).range;
  if (!Array.isArray(range) || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }
  const insertAt = range[1] as number;
  const baseIndent = indentForMapKeys(yamlText, currentMap);
  const indentStep = 2;

  let block = "";
  let indent = baseIndent;
  for (let i = 0; i < segmentsToCreate.length - 1; i += 1) {
    block += " ".repeat(indent) + segmentsToCreate[i] + ":\n";
    indent += indentStep;
  }
  block += " ".repeat(indent) + segmentsToCreate[segmentsToCreate.length - 1] + ": {}\n";

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const insertText = (needsLeadingNewline ? "\n" : "") + block;
  return { ok: true, text: applyRangePatch(yamlText, insertAt, insertAt, insertText), plan: { kind: "safe" } };
};

export const ensureEmptyMapAtPathDeep = (yamlText: string, path: string[], opts?: { createMissing?: boolean }): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  const out = ensureEmptyMapAtPathDeepSafe(yamlText, path, { createMissing });
  if (out.ok) return out;
  if (!out.plan || out.plan.kind !== "rewrite") return out;

  let root: any;
  try {
    root = parse(yamlText);
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown"), plan: out.plan };
  }
  if (!isPlainObject(root) && !Array.isArray(root)) root = {};

  const edit = deepSetInPlace(root, path, {}, createMissing);
  if (!edit.ok) return { ok: false, error: edit.error, plan: out.plan };

  return {
    ok: true,
    text: stringifyWithLeadingCommentBlock(yamlText, edit.value),
    plan: { kind: "rewrite", reason: out.plan.reason || "unsafe patch" }
  };
};

const ensureEmptySeqAtPathDeepSafe = (yamlText: string, path: string[], opts?: { createMissing?: boolean }): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  if (!path.length) return { ok: false, error: "patch: empty path" };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!isMap(root)) return { ok: false, error: "patch: root is not a mapping", plan: { kind: "rewrite", reason: "non-mapping root" } };

  const deepKey = path[path.length - 1] as string;
  const parentSegments = path.slice(0, -1);

  let current: Node = root as any;
  let currentMap = current as YAMLMap;
  let missingAt = parentSegments.length;

  for (let i = 0; i < parentSegments.length; i += 1) {
    const seg = parentSegments[i] as string;
    if (!isMap(current)) return { ok: false, error: "patch: parent is not a mapping", plan: { kind: "rewrite", reason: "non-mapping parent" } };
    currentMap = current as YAMLMap;
    const pair = findPairInMap(currentMap, seg);
    if (!pair || !pair.value) {
      missingAt = i;
      break;
    }
    const next = (pair.value as Node | null) || null;
    if (!next || !isMap(next)) {
      return { ok: false, error: "patch: existing node is not a mapping: " + seg, plan: { kind: "rewrite", reason: "non-mapping node" } };
    }
    current = next;
  }

  if (!createMissing && missingAt < parentSegments.length) {
    return { ok: true, text: yamlText, plan: { kind: "safe" } };
  }

  if (isMap(current)) {
    currentMap = current as YAMLMap;
    const existing = findPairInMap(currentMap, deepKey);
    if (existing && existing.value && isSeq(existing.value as any)) return { ok: true, text: yamlText, plan: { kind: "safe" } };
    if (existing && existing.value && isAlias(existing.value as any)) {
      return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
    }
    if (existing && existing.value && !isSeq(existing.value as any)) {
      return { ok: false, error: "patch: existing value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
    }
  }

  const remaining = parentSegments.slice(missingAt);
  const segmentsToCreate = remaining.concat([deepKey]);

  const range = (currentMap as any).range;
  if (!Array.isArray(range) || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing parent range", plan: { kind: "rewrite", reason: "missing map range" } };
  }
  const insertAt = range[1] as number;
  const baseIndent = indentForMapKeys(yamlText, currentMap);
  const indentStep = 2;

  let block = "";
  let indent = baseIndent;
  for (let i = 0; i < segmentsToCreate.length - 1; i += 1) {
    block += " ".repeat(indent) + segmentsToCreate[i] + ":\n";
    indent += indentStep;
  }
  block += " ".repeat(indent) + segmentsToCreate[segmentsToCreate.length - 1] + ": []\n";

  const needsLeadingNewline = insertAt > 0 && yamlText.charCodeAt(insertAt - 1) !== 10;
  const insertText = (needsLeadingNewline ? "\n" : "") + block;
  return { ok: true, text: applyRangePatch(yamlText, insertAt, insertAt, insertText), plan: { kind: "safe" } };
};

export const ensureEmptySeqAtPathDeep = (yamlText: string, path: string[], opts?: { createMissing?: boolean }): PatchResult => {
  const createMissing = opts && typeof opts.createMissing === "boolean" ? opts.createMissing : true;
  const out = ensureEmptySeqAtPathDeepSafe(yamlText, path, { createMissing });
  if (out.ok) return out;
  if (!out.plan || out.plan.kind !== "rewrite") return out;

  let root: any;
  try {
    root = parse(yamlText);
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown"), plan: out.plan };
  }
  if (!isPlainObject(root) && !Array.isArray(root)) root = {};

  const edit = deepSetInPlace(root, path, [], createMissing);
  if (!edit.ok) return { ok: false, error: edit.error, plan: out.plan };

  return {
    ok: true,
    text: stringifyWithLeadingCommentBlock(yamlText, edit.value),
    plan: { kind: "rewrite", reason: out.plan.reason || "unsafe patch" }
  };
};

type MapSpan = { start: number; end: number; key: string };

const mapSpans = (yamlText: string, mapNode: YAMLMap): { ok: true; end: number; spans: MapSpan[] } | { ok: false; error: string } => {
  const items = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) || [];
  const range = (mapNode as any).range;
  if (!Array.isArray(range) || typeof range[1] !== "number") {
    return { ok: false, error: "patch: mapping has no range" };
  }
  const mapEnd = range[1] as number;
  if (!items.length) return { ok: true, end: mapEnd, spans: [] };

  const spans: MapSpan[] = [];
  for (let i = 0; i < items.length; i += 1) {
    const pair = items[i];
    const keyOffset0 = nodeStartOffset(pair.key);
    if (keyOffset0 == null) return { ok: false, error: "patch: mapping pair missing key range" };
    const start = lineStartOffset(yamlText, keyOffset0);
    let end = mapEnd;
    if (i + 1 < items.length) {
      const nextKeyOffset0 = nodeStartOffset(items[i + 1].key);
      if (nextKeyOffset0 == null) return { ok: false, error: "patch: mapping pair missing next key range" };
      end = lineStartOffset(yamlText, nextKeyOffset0);
    }
    spans.push({ start, end, key: scalarKeyToString(pair.key) });
  }

  return { ok: true, end: mapEnd, spans };
};

const removeKeyOnce = (yamlText: string, path: string[]): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;
  const parentNode = getIn(root, parentPath);
  if (!parentNode || !isMap(parentNode)) {
    return { ok: true, text: yamlText, plan: { kind: "safe" } };
  }

  const mapNode = parentNode as YAMLMap;
  const pair = findPairInMap(mapNode, key);
  if (!pair) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  const spansOut = mapSpans(yamlText, mapNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const span = spansOut.spans.find((s) => s.key === key);
  if (!span) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  return { ok: true, text: applyRangePatch(yamlText, span.start, span.end, ""), plan: { kind: "safe" } };
};

const isEmptyContainerNode = (node: Node | null): boolean => {
  if (!node) return false;
  if (isMap(node)) return ((node as YAMLMap).items || []).length === 0;
  if (isSeq(node)) return ((node as YAMLSeq).items || []).length === 0;
  if (isScalar(node)) {
    const v = (node as any).value;
    return v == null;
  }
  return false;
};

const removeKeyAtPathSafe = (yamlText: string, path: string[], opts?: { pruneEmptyParents?: boolean }): PatchResult => {
  const prune = Boolean(opts && opts.pruneEmptyParents);
  let text = yamlText;
  let currentPath = path.slice(0);

  const out0 = removeKeyOnce(text, currentPath);
  if (!out0.ok) return out0;
  text = out0.text;

  if (!prune) return out0;

  for (let i = 0; i < 8; i += 1) {
    if (currentPath.length < 2) break;
    const parentKeyPath = currentPath.slice(0, -1);

    let doc: any;
    try {
      doc = parseDocument(text, { keepSourceTokens: true });
    } catch {
      break;
    }
    const root = (doc?.contents as Node | null) || null;
    if (!root) break;
    const parentNode = getIn(root, parentKeyPath);
    if (!isEmptyContainerNode(parentNode)) break;

    const out = removeKeyOnce(text, parentKeyPath);
    if (!out.ok) return out;
    text = out.text;
    currentPath = parentKeyPath;
  }

  return { ok: true, text, plan: { kind: "safe" } };
};

export const removeKeyAtPath = (yamlText: string, path: string[], opts?: { pruneEmptyParents?: boolean }): PatchResult => {
  const prune = Boolean(opts && opts.pruneEmptyParents);

  try {
    const doc = parseDocument(yamlText, { keepSourceTokens: true });
    const root = (doc?.contents as Node | null) || null;
    const decision = aliasDecisionFor(root, path, { kind: "remove_key", path, pruneEmptyParents: prune, keepEmptyMap: false });
    if (decision) return { ok: true, text: yamlText, plan: { kind: "rewrite", reason: "alias" }, decision };
  } catch {
    // ignore
  }

  const out = removeKeyAtPathSafe(yamlText, path, { pruneEmptyParents: prune });
  if (out.ok) return out;
  if (!out.plan || out.plan.kind !== "rewrite") return out;

  let root: any;
  try {
    root = parse(yamlText);
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown"), plan: out.plan };
  }
  if (!isPlainObject(root) && !Array.isArray(root)) root = {};

  const edit = deepDeleteInPlace(root, path, prune);
  if (!edit.ok) return { ok: false, error: edit.error, plan: out.plan };

  return {
    ok: true,
    text: stringifyWithLeadingCommentBlock(yamlText, edit.value),
    plan: { kind: "rewrite", reason: out.plan.reason || "unsafe patch" }
  };
};

const removeKeyAtPathKeepEmptyMapSafe = (yamlText: string, path: string[]): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;
  const parentNode = getIn(root, parentPath);
  if (!parentNode || !isMap(parentNode)) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  const mapNode = parentNode as YAMLMap;
  const items = (mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) || [];
  const pair = findPairInMap(mapNode, key);
  if (!pair) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  if ((mapNode as any).flow) {
    // Only handle the simplest flow case: {key: ...} -> {}.
    if (items.length !== 1) {
      return { ok: false, error: "patch: cannot remove key from flow mapping safely", plan: { kind: "rewrite", reason: "flow map" } };
    }
    const range = (mapNode as any).range;
    if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
      return { ok: false, error: "patch: mapping has no range", plan: { kind: "rewrite", reason: "missing range" } };
    }
    return { ok: true, text: applyRangePatch(yamlText, range[0] as number, range[1] as number, "{}"), plan: { kind: "safe" } };
  }

  if (items.length <= 1) {
    const range = (mapNode as any).range;
    if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
      return { ok: false, error: "patch: mapping has no range", plan: { kind: "rewrite", reason: "missing range" } };
    }
    const start = range[0] as number;
    const end = range[1] as number;
    const original = yamlText.slice(start, end);
    const replacement = original.endsWith("\n") ? "{}\n" : "{}";
    return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
  }

  // Map has other keys; remove just this key span.
  const spansOut = mapSpans(yamlText, mapNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };
  const span = spansOut.spans.find((s) => s.key === key);
  if (!span) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  return { ok: true, text: applyRangePatch(yamlText, span.start, span.end, ""), plan: { kind: "safe" } };
};

export const removeKeyAtPathKeepEmptyMap = (yamlText: string, path: string[]): PatchResult => {
  try {
    const doc = parseDocument(yamlText, { keepSourceTokens: true });
    const root = (doc?.contents as Node | null) || null;
    const decision = aliasDecisionFor(root, path, { kind: "remove_key", path, pruneEmptyParents: false, keepEmptyMap: true });
    if (decision) return { ok: true, text: yamlText, plan: { kind: "rewrite", reason: "alias" }, decision };
  } catch {
    // ignore
  }

  const out = removeKeyAtPathKeepEmptyMapSafe(yamlText, path);
  if (out.ok) return out;
  if (!out.plan || out.plan.kind !== "rewrite") return out;

  let root: any;
  try {
    root = parse(yamlText);
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown"), plan: out.plan };
  }
  if (!isPlainObject(root) && !Array.isArray(root)) root = {};

  const edit = deepDeleteInPlace(root, path, false);
  if (!edit.ok) return { ok: false, error: edit.error, plan: out.plan };

  return {
    ok: true,
    text: stringifyWithLeadingCommentBlock(yamlText, edit.value),
    plan: { kind: "rewrite", reason: out.plan.reason || "unsafe patch" }
  };
};

type SeqSpan = { start: number; end: number; node: Node };

const seqSpans = (
  yamlText: string,
  seqNode: YAMLSeq
): { ok: true; blockStart: number; blockEnd: number; spans: SeqSpan[]; itemIndent: string } | { ok: false; error: string } => {
  const items = (seqNode.items as Node[]) || [];
  const range = (seqNode as any).range;
  const seqEnd = Array.isArray(range) && typeof range[2] === "number" ? (range[2] as number) : null;
  if (!seqEnd) return { ok: false, error: "patch: sequence has no range" };
  if (!items.length) return { ok: false, error: "patch: empty sequence" };

  const spans: SeqSpan[] = [];
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    const itemRange = (item as any).range;
    if (!Array.isArray(itemRange) || typeof itemRange[0] !== "number") {
      return { ok: false, error: "patch: sequence item missing range" };
    }
    const start0 = itemRange[0] as number;
    const start = lineStartOffset(yamlText, start0);

    let end = seqEnd;
    if (i + 1 < items.length) {
      const nextRange = (items[i + 1] as any).range;
      if (Array.isArray(nextRange) && typeof nextRange[0] === "number") {
        end = lineStartOffset(yamlText, nextRange[0] as number);
      }
    }
    spans.push({ start, end, node: item });
  }

  const indentSpaces = countIndentSpaces(yamlText, (items[0] as any).range[0] as number);
  return {
    ok: true,
    blockStart: spans[0].start,
    blockEnd: spans[spans.length - 1].end,
    spans,
    itemIndent: " ".repeat(indentSpaces)
  };
};

const ensurePrimaryOutputTargetMap = (root: Node | null): YAMLMap | null => {
  const outputsNode = getIn(root, ["outputs"]);
  if (outputsNode && isSeq(outputsNode)) {
    const items = ((outputsNode as YAMLSeq).items as Node[]) || [];
    const first = items[0];
    if (first && isMap(first)) return first as YAMLMap;
  }
  const outputNode = getIn(root, ["output"]);
  if (outputNode && isMap(outputNode)) return outputNode as YAMLMap;
  return null;
};

const renderOutputFieldLine = (itemIndent: string, item: { kind: "alias"; anchor: string } | { kind: "field_id"; fieldId: string }): string => {
  if (item.kind === "alias") return itemIndent + "- *" + item.anchor + "\n";
  const fieldIdScalar = formatScalarReplacement(null, item.fieldId);
  return itemIndent + "- {field_id: " + fieldIdScalar + "}\n";
};

const insertIntoOutputFields = (
  yamlText: string,
  index: number,
  item: { kind: "alias"; anchor: string } | { kind: "field_id"; fieldId: string }
): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const outputMap = ensurePrimaryOutputTargetMap(root);
  if (!outputMap) return { ok: false, error: "patch: output target not found", plan: { kind: "rewrite", reason: "missing output" } };

  const fieldsPair = findPairInMap(outputMap, "fields");
  if (!fieldsPair) {
    // Create fields as a block sequence.
    const firstPair = (outputMap.items as Array<Pair<ParsedNode, ParsedNode | null>>)[0];
    const firstKeyOffset = firstPair ? nodeStartOffset(firstPair.key) : null;
    const keyIndentSpaces = firstKeyOffset != null ? countIndentSpaces(yamlText, firstKeyOffset) : 2;
    const itemIndent = " ".repeat(keyIndentSpaces + 2);
    const blockValue = renderOutputFieldLine(itemIndent, item);
    return appendBlockKeyToMap(yamlText, outputMap, "fields", blockValue);
  }

  const valueNode = (fieldsPair.value as Node | null) || null;
  if (!valueNode) return { ok: false, error: "patch: fields is empty", plan: { kind: "rewrite", reason: "missing node" } };
  if (!isSeq(valueNode)) {
    return { ok: false, error: "patch: fields is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
  }

  const seqNode = valueNode as YAMLSeq;
  const items = (seqNode.items as Node[]) || [];
  if (!items.length) {
    // Convert flow `[]` to a block list containing our item.
    const keyOffset = nodeStartOffset(fieldsPair.key);
    const keyIndentSpaces = keyOffset != null ? countIndentSpaces(yamlText, keyOffset) : 0;
    const itemIndent = " ".repeat(keyIndentSpaces + 2);
    const range = (seqNode as any).range;
    if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[2] !== "number") {
      return { ok: false, error: "patch: fields missing range", plan: { kind: "rewrite", reason: "missing range" } };
    }
    const start = range[0] as number;
    const end = range[2] as number;
    const replacement = "\n" + renderOutputFieldLine(itemIndent, item);
    return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
  }

  const spansOut = seqSpans(yamlText, seqNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const safeIndex = Math.max(0, Math.min(index, spansOut.spans.length));
  const chunks: string[] = [];
  for (let i = 0; i < spansOut.spans.length; i += 1) {
    if (i === safeIndex) chunks.push(renderOutputFieldLine(spansOut.itemIndent, item));
    const span = spansOut.spans[i];
    chunks.push(yamlText.slice(span.start, span.end));
  }
  if (safeIndex === spansOut.spans.length) chunks.push(renderOutputFieldLine(spansOut.itemIndent, item));

  return {
    ok: true,
    text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, chunks.join("")),
    plan: { kind: "safe" }
  };
};

export const insertOutputFieldAliasAt = (yamlText: string, index: number, anchor: string): PatchResult => {
  const cleaned = String(anchor || "").trim().replace(/^\*/, "");
  if (!cleaned) return { ok: false, error: "patch: empty anchor" };
  return insertIntoOutputFields(yamlText, index, { kind: "alias", anchor: cleaned });
};

export const insertOutputFieldIdAt = (yamlText: string, index: number, fieldId: string): PatchResult => {
  const cleaned = String(fieldId || "").trim();
  if (!cleaned) return { ok: false, error: "patch: empty field_id" };
  return insertIntoOutputFields(yamlText, index, { kind: "field_id", fieldId: cleaned });
};

export const removeOutputFieldAt = (yamlText: string, index: number): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const outputMap = ensurePrimaryOutputTargetMap(root);
  if (!outputMap) return { ok: false, error: "patch: output target not found", plan: { kind: "rewrite", reason: "missing output" } };
  const fieldsPair = findPairInMap(outputMap, "fields");
  if (!fieldsPair) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  const valueNode = (fieldsPair.value as Node | null) || null;
  if (!valueNode || !isSeq(valueNode)) {
    return { ok: false, error: "patch: fields is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
  }

  const seqNode = valueNode as YAMLSeq;
  const items = (seqNode.items as Node[]) || [];
  if (!items.length) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (index < 0 || index >= items.length) return { ok: false, error: "patch: index out of range" };

  const spansOut = seqSpans(yamlText, seqNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const remaining: string[] = [];
  for (let i = 0; i < spansOut.spans.length; i += 1) {
    if (i === index) continue;
    const span = spansOut.spans[i];
    remaining.push(yamlText.slice(span.start, span.end));
  }

  if (!remaining.length) {
    const replacement = spansOut.itemIndent + "[]\n";
    return { ok: true, text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, replacement), plan: { kind: "safe" } };
  }

  return {
    ok: true,
    text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, remaining.join("")),
    plan: { kind: "safe" }
  };
};

export const moveOutputField = (yamlText: string, from: number, to: number): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const outputMap = ensurePrimaryOutputTargetMap(root);
  if (!outputMap) return { ok: false, error: "patch: output target not found", plan: { kind: "rewrite", reason: "missing output" } };
  const fieldsPair = findPairInMap(outputMap, "fields");
  if (!fieldsPair) return { ok: false, error: "patch: fields not found" };

  const valueNode = (fieldsPair.value as Node | null) || null;
  if (!valueNode || !isSeq(valueNode)) {
    return { ok: false, error: "patch: fields is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
  }

  const seqNode = valueNode as YAMLSeq;
  const items = (seqNode.items as Node[]) || [];
  if (!items.length) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (from < 0 || from >= items.length) return { ok: false, error: "patch: from out of range" };

  const safeTo = Math.max(0, Math.min(to, items.length - 1));
  if (from === safeTo) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  const spansOut = seqSpans(yamlText, seqNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const slices = spansOut.spans.map((s) => yamlText.slice(s.start, s.end));
  const moving = slices.splice(from, 1)[0];
  slices.splice(safeTo, 0, moving);

  return {
    ok: true,
    text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, slices.join("")),
    plan: { kind: "safe" }
  };
};

const renderStringSeqLine = (itemIndent: string, value: string): string => {
  const scalar = formatScalarReplacement(null, value);
  return itemIndent + "- " + scalar + "\n";
};

const renderInlineSeqLine = (itemIndent: string, inlineValue: string): string => {
  return itemIndent + "- " + inlineValue + "\n";
};

export const insertStringItemAtPath = (yamlText: string, path: string[], index: number, value: string): PatchResult => {
  const cleaned = String(value || "").trim();
  if (!cleaned) return { ok: false, error: "patch: empty item" };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;
  const parentNode = getIn(root, parentPath);
  if (!parentNode || !isMap(parentNode)) {
    return { ok: false, error: "patch: parent mapping not found", plan: { kind: "rewrite", reason: "parent not found" } };
  }
  const mapNode = parentNode as YAMLMap;

  const pair = findPairInMap(mapNode, key);
  if (!pair) {
    const keyIndent = indentForMapKeys(yamlText, mapNode);
    const itemIndent = " ".repeat(keyIndent + 2);
    return appendBlockKeyToMap(yamlText, mapNode, key, renderStringSeqLine(itemIndent, cleaned));
  }

  const valueNode = (pair.value as Node | null) || null;
  if (!valueNode) return { ok: false, error: "patch: sequence is empty", plan: { kind: "rewrite", reason: "missing node" } };
  if (isAlias(valueNode)) {
    return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
  }
  if (!isSeq(valueNode)) {
    return { ok: false, error: "patch: value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
  }

  const seqNode = valueNode as YAMLSeq;
  const items = (seqNode.items as Node[]) || [];
  if (!items.length) {
    const keyOffset = nodeStartOffset(pair.key);
    const keyIndentSpaces = keyOffset != null ? countIndentSpaces(yamlText, keyOffset) : indentForMapKeys(yamlText, mapNode);
    const itemIndent = " ".repeat(keyIndentSpaces + 2);
    const range = (seqNode as any).range;
    if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[2] !== "number") {
      return { ok: false, error: "patch: sequence missing range", plan: { kind: "rewrite", reason: "missing range" } };
    }
    const start = range[0] as number;
    const end = range[2] as number;
    const replacement = "\n" + renderStringSeqLine(itemIndent, cleaned);
    return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
  }

  if ((seqNode as any).flow) {
    return { ok: false, error: "patch: cannot insert into flow list safely; edit YAML directly", plan: { kind: "rewrite", reason: "flow seq" } };
  }

  const spansOut = seqSpans(yamlText, seqNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const safeIndex = Math.max(0, Math.min(index, spansOut.spans.length));
  const chunks: string[] = [];
  for (let i = 0; i < spansOut.spans.length; i += 1) {
    if (i === safeIndex) chunks.push(renderStringSeqLine(spansOut.itemIndent, cleaned));
    const span = spansOut.spans[i];
    chunks.push(yamlText.slice(span.start, span.end));
  }
  if (safeIndex === spansOut.spans.length) chunks.push(renderStringSeqLine(spansOut.itemIndent, cleaned));

  return {
    ok: true,
    text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, chunks.join("")),
    plan: { kind: "safe" }
  };
};

export const insertInlineItemAtPath = (yamlText: string, path: string[], index: number, inlineValue: string): PatchResult => {
  const cleaned = String(inlineValue || "").trim();
  if (!cleaned) return { ok: false, error: "patch: empty item" };
  if (cleaned.includes("\n")) return { ok: false, error: "patch: inline item must be single-line", plan: { kind: "rewrite", reason: "multiline" } };

  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const parentPath = path.slice(0, -1);
  const key = path[path.length - 1] as string;
  const parentNode = getIn(root, parentPath);
  if (!parentNode || !isMap(parentNode)) {
    return { ok: false, error: "patch: parent mapping not found", plan: { kind: "rewrite", reason: "parent not found" } };
  }
  const mapNode = parentNode as YAMLMap;

  const pair = findPairInMap(mapNode, key);
  if (!pair) {
    const keyIndent = indentForMapKeys(yamlText, mapNode);
    const itemIndent = " ".repeat(keyIndent + 2);
    return appendBlockKeyToMap(yamlText, mapNode, key, renderInlineSeqLine(itemIndent, cleaned));
  }

  const valueNode = (pair.value as Node | null) || null;
  if (!valueNode) return { ok: false, error: "patch: sequence is empty", plan: { kind: "rewrite", reason: "missing node" } };
  if (isAlias(valueNode)) {
    return { ok: false, error: "patch: value is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
  }
  if (!isSeq(valueNode)) {
    return { ok: false, error: "patch: value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };
  }

  const seqNode = valueNode as YAMLSeq;
  const items = (seqNode.items as Node[]) || [];
  if (!items.length) {
    const keyOffset = nodeStartOffset(pair.key);
    const keyIndentSpaces = keyOffset != null ? countIndentSpaces(yamlText, keyOffset) : indentForMapKeys(yamlText, mapNode);
    const itemIndent = " ".repeat(keyIndentSpaces + 2);
    const range = (seqNode as any).range;
    if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[2] !== "number") {
      return { ok: false, error: "patch: sequence missing range", plan: { kind: "rewrite", reason: "missing range" } };
    }
    const start = range[0] as number;
    const end = range[2] as number;
    const replacement = "\n" + renderInlineSeqLine(itemIndent, cleaned);
    return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
  }

  if ((seqNode as any).flow) {
    return { ok: false, error: "patch: cannot insert into flow list safely; edit YAML directly", plan: { kind: "rewrite", reason: "flow seq" } };
  }

  const spansOut = seqSpans(yamlText, seqNode);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const safeIndex = Math.max(0, Math.min(index, spansOut.spans.length));
  const chunks: string[] = [];
  for (let i = 0; i < spansOut.spans.length; i += 1) {
    if (i === safeIndex) chunks.push(renderInlineSeqLine(spansOut.itemIndent, cleaned));
    const span = spansOut.spans[i];
    chunks.push(yamlText.slice(span.start, span.end));
  }
  if (safeIndex === spansOut.spans.length) chunks.push(renderInlineSeqLine(spansOut.itemIndent, cleaned));

  return {
    ok: true,
    text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, chunks.join("")),
    plan: { kind: "safe" }
  };
};

export const removeSeqItemAtPath = (yamlText: string, path: string[], index: number): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const seqNode = getIn(root, path);
  if (!seqNode) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (!isSeq(seqNode)) return { ok: false, error: "patch: value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };

  const seq = seqNode as YAMLSeq;
  const items = (seq.items as Node[]) || [];
  if (!items.length) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (index < 0 || index >= items.length) return { ok: false, error: "patch: index out of range" };

  if ((seq as any).flow) {
    return { ok: false, error: "patch: cannot remove from flow list safely; edit YAML directly", plan: { kind: "rewrite", reason: "flow seq" } };
  }

  const spansOut = seqSpans(yamlText, seq);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const remaining: string[] = [];
  for (let i = 0; i < spansOut.spans.length; i += 1) {
    if (i === index) continue;
    const span = spansOut.spans[i];
    remaining.push(yamlText.slice(span.start, span.end));
  }

  if (!remaining.length) {
    const replacement = spansOut.itemIndent + "[]\n";
    return { ok: true, text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, replacement), plan: { kind: "safe" } };
  }

  return { ok: true, text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, remaining.join("")), plan: { kind: "safe" } };
};

export const moveSeqItemAtPath = (yamlText: string, path: string[], from: number, to: number): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };
  if (!path.length) return { ok: false, error: "patch: empty path" };

  const seqNode = getIn(root, path);
  if (!seqNode) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (!isSeq(seqNode)) return { ok: false, error: "patch: value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };

  const seq = seqNode as YAMLSeq;
  const items = (seq.items as Node[]) || [];
  if (!items.length) return { ok: true, text: yamlText, plan: { kind: "safe" } };
  if (from < 0 || from >= items.length) return { ok: false, error: "patch: from out of range" };

  const safeTo = Math.max(0, Math.min(to, items.length - 1));
  if (from === safeTo) return { ok: true, text: yamlText, plan: { kind: "safe" } };

  if ((seq as any).flow) {
    return { ok: false, error: "patch: cannot move in flow list safely; edit YAML directly", plan: { kind: "rewrite", reason: "flow seq" } };
  }

  const spansOut = seqSpans(yamlText, seq);
  if (!spansOut.ok) return { ok: false, error: spansOut.error, plan: { kind: "rewrite", reason: spansOut.error } };

  const slices = spansOut.spans.map((s) => yamlText.slice(s.start, s.end));
  const moving = slices.splice(from, 1)[0];
  slices.splice(safeTo, 0, moving);

  return { ok: true, text: applyRangePatch(yamlText, spansOut.blockStart, spansOut.blockEnd, slices.join("")), plan: { kind: "safe" } };
};

export const setScalarAtSeqIndex = (
  yamlText: string,
  seqPath: string[],
  index: number,
  value: string | number | boolean | null
): PatchResult => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const seqNode = getIn(root, seqPath);
  if (!seqNode) return { ok: false, error: "patch: list not found", plan: { kind: "rewrite", reason: "missing list" } };
  if (!isSeq(seqNode)) return { ok: false, error: "patch: value is not a list", plan: { kind: "rewrite", reason: "non-sequence" } };

  const seq = seqNode as YAMLSeq;
  const items = (seq.items as Node[]) || [];
  if (index < 0 || index >= items.length) return { ok: false, error: "patch: index out of range" };

  const node = items[index] as Node;
  if (!node) return { ok: false, error: "patch: missing list item", plan: { kind: "rewrite", reason: "missing item" } };
  if (isAlias(node)) {
    return { ok: false, error: "patch: item is alias, requires detach or rewrite", plan: { kind: "rewrite", reason: "alias" } };
  }
  if (!isScalar(node)) {
    return { ok: false, error: "patch: item is not scalar", plan: { kind: "rewrite", reason: "non-scalar" } };
  }

  const range = (node as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[1] !== "number") {
    return { ok: false, error: "patch: missing scalar range", plan: { kind: "rewrite", reason: "missing range" } };
  }
  const start = range[0] as number;
  const end = range[1] as number;
  const replacement = formatScalarReplacement(node, value);
  return { ok: true, text: applyRangePatch(yamlText, start, end, replacement), plan: { kind: "safe" } };
};
