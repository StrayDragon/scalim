import { isMap, isScalar, isSeq, parseDocument, type Node, type ParsedNode, type Pair, type Scalar, type YAMLMap, type YAMLSeq } from "yaml";

export type YamlLocation = {
  offset: number;
  line: number;
  column: number;
};

export type YamlLocationIndex = Record<string, YamlLocation>;

export type OutlineTarget = {
  id: string;
  label: string;
  depth: number;
  line: number;
  column: number;
};

const buildLineStarts = (text: string): number[] => {
  const starts = [0];
  for (let i = 0; i < text.length; i += 1) {
    if (text.charCodeAt(i) === 10) starts.push(i + 1);
  }
  return starts;
};

const upperBound = (arr: number[], x: number): number => {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
};

const offsetToLineCol = (offset: number, lineStarts: number[]): { line: number; column: number } => {
  if (offset < 0) return { line: 1, column: 1 };
  const idx = Math.max(0, upperBound(lineStarts, offset) - 1);
  const lineStart = lineStarts[idx] || 0;
  return { line: idx + 1, column: offset - lineStart + 1 };
};

const nodeStartOffset = (node: any): number | null => {
  const range = node?.range;
  if (Array.isArray(range) && typeof range[0] === "number") return range[0];
  const token = node?.srcToken;
  const tokenRange = token?.range;
  if (Array.isArray(tokenRange) && typeof tokenRange[0] === "number") return tokenRange[0];
  return null;
};

const scalarKeyToString = (key: Scalar | unknown): string => {
  if (isScalar(key)) return String(key.value ?? "");
  return String((key as any)?.value ?? "");
};

const recordLocation = (locations: YamlLocationIndex, path: string[], offset: number, lineStarts: number[]) => {
  const pathKey = path.join(".");
  if (pathKey in locations) return;
  const pos = offsetToLineCol(offset, lineStarts);
  locations[pathKey] = { offset, line: pos.line, column: pos.column };
};

const indexYamlNode = (node: Node | null, path: string[], locations: YamlLocationIndex, lineStarts: number[]) => {
  if (!node) return;
  const startOffset = nodeStartOffset(node);
  if (startOffset != null) recordLocation(locations, path, startOffset, lineStarts);

  if (isMap(node)) {
    const mapNode = node as YAMLMap;
    for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
      const keyNode = pair.key;
      const valueNode = pair.value as Node | null;
      const key = scalarKeyToString(keyNode);
      const keyPath = [...path, key];
      const keyOffset = nodeStartOffset(keyNode);
      if (keyOffset != null) recordLocation(locations, keyPath, keyOffset, lineStarts);
      indexYamlNode(valueNode, keyPath, locations, lineStarts);
    }
  } else if (isSeq(node)) {
    const seqNode = node as YAMLSeq;
    const items = seqNode.items as Node[];
    for (let i = 0; i < items.length; i += 1) {
      const itemNode = items[i];
      const idxPath = [...path, String(i)];
      const itemOffset = nodeStartOffset(itemNode);
      if (itemOffset != null) recordLocation(locations, idxPath, itemOffset, lineStarts);
      indexYamlNode(itemNode, idxPath, locations, lineStarts);
    }
  }
};

const getNodeAtPath = (root: Node | null, path: string[]): Node | null => {
  let current: Node | null = root;
  for (const seg of path) {
    if (!current) return null;
    if (isMap(current)) {
      const mapNode = current as YAMLMap;
      let next: Node | null = null;
      for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
        const key = scalarKeyToString(pair.key);
        if (key === seg) {
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
      const items = seqNode.items as Node[];
      current = items[idx] || null;
      continue;
    }
    return null;
  }
  return current;
};

export const lookupYamlLocation = (path: string | undefined, locations: YamlLocationIndex): YamlLocation | null => {
  const cleaned = (path || "").trim();
  if (cleaned in locations) return locations[cleaned] || null;
  if (!cleaned) return locations[""] || null;
  const parts = cleaned.split(".");
  while (parts.length) {
    parts.pop();
    const candidate = parts.join(".");
    if (candidate in locations) return locations[candidate] || null;
  }
  return locations[""] || null;
};

export const getYamlLocationExact = (path: string | undefined, locations: YamlLocationIndex): YamlLocation | null => {
  const cleaned = (path || "").trim();
  if (!cleaned) return locations[""] || null;
  if (cleaned in locations) return locations[cleaned] || null;
  return null;
};

const outlineForMapKeys = (root: Node | null, basePath: string, locations: YamlLocationIndex, depth: number): OutlineTarget[] => {
  const node = getNodeAtPath(root, basePath ? basePath.split(".") : []);
  if (!node || !isMap(node)) return [];
  const items: OutlineTarget[] = [];
  const mapNode = node as YAMLMap;
  for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
    const key = scalarKeyToString(pair.key);
    const path = basePath ? basePath + "." + key : key;
    const loc = getYamlLocationExact(path, locations);
    if (!loc) continue;
    items.push({ id: path, label: key, depth, line: loc.line, column: loc.column });
  }
  return items;
};

const findPairInMap = (mapNode: YAMLMap, key: string): Pair<ParsedNode, ParsedNode | null> | null => {
  for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
    const k = scalarKeyToString(pair.key as any);
    if (k === key) return pair;
  }
  return null;
};

const scalarString = (node: Node | null): string => {
  if (!node || !isScalar(node)) return "";
  return String((node as any).value ?? "");
};

const outlineForSeqItems = (
  root: Node | null,
  basePath: string,
  locations: YamlLocationIndex,
  depth: number,
  opts?: { labelPrefix?: string; nameKey?: string }
): OutlineTarget[] => {
  const node = getNodeAtPath(root, basePath ? basePath.split(".") : []);
  if (!node || !isSeq(node)) return [];
  const seqNode = node as YAMLSeq;
  const items: OutlineTarget[] = [];
  const prefix = String(opts?.labelPrefix || "").trim();
  const nameKey = String(opts?.nameKey || "name").trim() || "name";

  const seqItems = (seqNode.items as Node[]) || [];
  for (let i = 0; i < seqItems.length; i += 1) {
    const itemNode = seqItems[i];
    const path = basePath ? basePath + "." + String(i) : String(i);
    const loc = getYamlLocationExact(path, locations);
    if (!loc) continue;

    let label = prefix ? prefix + "[" + String(i) + "]" : "[" + String(i) + "]";
    if (itemNode && isMap(itemNode)) {
      const namePair = findPairInMap(itemNode as any, nameKey);
      const nameValue = scalarString(((namePair?.value as Node | null) || null) as Node | null).trim();
      if (nameValue) label = nameValue;
    }

    items.push({ id: path, label, depth, line: loc.line, column: loc.column });
  }

  return items;
};

export const indexYamlText = (yamlText: string): { locations: YamlLocationIndex; outline: OutlineTarget[] } => {
  const lineStarts = buildLineStarts(yamlText);
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch {
    return { locations: {}, outline: [] };
  }
  const locations: YamlLocationIndex = {};
  indexYamlNode((doc?.contents as Node | null) || null, [], locations, lineStarts);

  const outline: OutlineTarget[] = [];
  const sections = [
    { path: "name", label: "name" },
    { path: "imports", label: "imports" },
    { path: "$import", label: "$import" },
    { path: "main_source", label: "main_source" },
    { path: "sources", label: "sources" },
    { path: "relations", label: "relations" },
    { path: "fields", label: "fields" },
    { path: "outputs", label: "outputs" },
    { path: "observability", label: "observability" },
    { path: "guardrails", label: "guardrails" }
  ];

  for (const sec of sections) {
    const loc = getYamlLocationExact(sec.path, locations);
    if (loc) outline.push({ id: sec.path, label: sec.label, depth: 0, line: loc.line, column: loc.column });
    if (sec.path === "main_source") {
      const fieldsLoc = getYamlLocationExact("main_source.fields", locations);
      if (fieldsLoc) {
        outline.push({
          id: "main_source.fields",
          label: "fields",
          depth: 1,
          line: fieldsLoc.line,
          column: fieldsLoc.column
        });
        outline.push(...outlineForMapKeys(((doc?.contents as Node | null) || null) as Node | null, "main_source.fields", locations, 2));
      }
    }
    if (sec.path === "sources") {
      outline.push(
        ...outlineForMapKeys(((doc?.contents as Node | null) || null) as Node | null, "sources", locations, 1).map((it) => ({
          ...it,
          label: "sources." + it.label
        }))
      );
    }
    if (sec.path === "imports") {
      outline.push(
        ...outlineForMapKeys(((doc?.contents as Node | null) || null) as Node | null, "imports", locations, 1).map((it) => ({
          ...it,
          label: "imports." + it.label
        }))
      );
    }
    if (sec.path === "relations") {
      outline.push(
        ...outlineForMapKeys(((doc?.contents as Node | null) || null) as Node | null, "relations", locations, 1).map((it) => ({
          ...it,
          label: "relations." + it.label
        }))
      );
    }
    if (sec.path === "fields") {
      outline.push(
        ...outlineForMapKeys(((doc?.contents as Node | null) || null) as Node | null, "fields", locations, 1).map((it) => ({
          ...it,
          label: "fields." + it.label
        }))
      );
    }
    if (sec.path === "outputs") {
      outline.push(...outlineForSeqItems(((doc?.contents as Node | null) || null) as Node | null, "outputs", locations, 1, { labelPrefix: "outputs" }));
    }
  }

  return { locations, outline };
};
