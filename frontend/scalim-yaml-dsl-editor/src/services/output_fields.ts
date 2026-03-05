import {
  isAlias,
  isMap,
  isScalar,
  isSeq,
  parseDocument,
  type Alias,
  type Node,
  type Pair,
  type ParsedNode,
  type Scalar,
  type YAMLMap,
  type YAMLSeq
} from "yaml";

import type { YamlLocationIndex } from "$services/yaml_doc";
import { lookupYamlLocation } from "$services/yaml_doc";

export type OutputHeaderBy = "field_id" | "name";

export type OutputFieldItem = {
  id: string;
  kind: "alias" | "map" | "scalar" | "unknown";
  label: string;
  raw: string;
  anchor?: string;
  fieldId?: string;
  name?: string;
  line?: number;
  column?: number;
};

export type OutputFieldsRead =
  | { ok: true; headerBy: OutputHeaderBy; items: OutputFieldItem[] }
  | { ok: false; error: string };

export type FieldCandidate = {
  id: string;
  origin: string;
  fieldId: string;
  anchor?: string;
  name?: string;
};

const scalarKeyToString = (keyNode: any): string => {
  if (isScalar(keyNode)) return String((keyNode as any).value ?? "");
  return String(keyNode?.value ?? "");
};

const findPairInMap = (mapNode: YAMLMap, key: string): Pair<ParsedNode, ParsedNode | null> | null => {
  for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
    if (scalarKeyToString(pair.key) === key) return pair;
  }
  return null;
};

const getIn = (root: Node | null, path: string[]): Node | null => {
  let current: Node | null = root;
  for (const seg of path) {
    if (!current) return null;
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
  return current;
};

const lineStartOffset = (text: string, offset: number): number => {
  let i = Math.min(Math.max(0, offset), text.length);
  while (i > 0 && text.charCodeAt(i - 1) !== 10) i -= 1;
  return i;
};

const nodeLineText = (yamlText: string, node: Node): string => {
  const range = (node as any).range;
  if (!Array.isArray(range) || typeof range[0] !== "number" || typeof range[2] !== "number") return "";
  const start = lineStartOffset(yamlText, range[0] as number);
  const end = range[2] as number;
  return yamlText.slice(start, end);
};

const scalarString = (node: Node | null): string => {
  if (!node || !isScalar(node)) return "";
  const s = node as Scalar;
  return String((s as any).value ?? "");
};

const readHeaderBy = (outputMap: YAMLMap): OutputHeaderBy => {
  const pair = findPairInMap(outputMap, "header_fields_output_by");
  const value = scalarString(((pair?.value as Node | null) || null) as Node | null).trim();
  return value === "name" ? "name" : "field_id";
};

const resolveAliasName = (aliasNode: Alias, doc: any): string => {
  try {
    const resolved = aliasNode.resolve(doc);
    if (!resolved || !isMap(resolved)) return "";
    const pair = findPairInMap(resolved as any, "name");
    return scalarString(((pair?.value as Node | null) || null) as Node | null);
  } catch {
    return "";
  }
};

const mapFieldIdName = (mapNode: YAMLMap): { fieldId: string; name: string } => {
  const fieldId = scalarString((findPairInMap(mapNode, "field_id")?.value as Node | null) || null);
  const name = scalarString((findPairInMap(mapNode, "name")?.value as Node | null) || null);
  return { fieldId, name };
};

export const readOutputFields = (yamlText: string, locations?: YamlLocationIndex): OutputFieldsRead => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch (err: any) {
    return { ok: false, error: "YAML parse failed: " + String(err?.message || err || "unknown") };
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root) return { ok: false, error: "YAML document is empty" };

  const outputNode = getIn(root, ["output"]);
  if (!outputNode || !isMap(outputNode)) return { ok: true, headerBy: "field_id", items: [] };
  const outputMap = outputNode as YAMLMap;
  const headerBy = readHeaderBy(outputMap);

  const fieldsNode = getIn(outputMap as any, ["fields"]);
  if (!fieldsNode || !isSeq(fieldsNode)) return { ok: true, headerBy, items: [] };
  const seqNode = fieldsNode as YAMLSeq;

  const items: OutputFieldItem[] = [];
  const seqItems = (seqNode.items as Node[]) || [];
  for (let i = 0; i < seqItems.length; i += 1) {
    const node = seqItems[i];
    const raw = nodeLineText(yamlText, node);
    const loc = locations ? lookupYamlLocation("output.fields." + String(i), locations) : null;

    if (isAlias(node)) {
      const aliasNode = node as unknown as Alias;
      const anchor = String(aliasNode.source || "");
      const name = resolveAliasName(aliasNode, doc);
      const label = "*" + anchor + (name ? " — " + name : "");
      items.push({
        id: "output.fields." + String(i),
        kind: "alias",
        label,
        raw,
        anchor,
        fieldId: anchor,
        name,
        line: loc?.line,
        column: loc?.column
      });
      continue;
    }

    if (isMap(node)) {
      const mapNode = node as YAMLMap;
      const out = mapFieldIdName(mapNode);
      const label = out.fieldId ? out.fieldId + (out.name ? " — " + out.name : "") : "(field)";
      items.push({
        id: "output.fields." + String(i),
        kind: "map",
        label,
        raw,
        fieldId: out.fieldId || undefined,
        name: out.name || undefined,
        line: loc?.line,
        column: loc?.column
      });
      continue;
    }

    if (isScalar(node)) {
      const value = scalarString(node);
      items.push({
        id: "output.fields." + String(i),
        kind: "scalar",
        label: value,
        raw,
        line: loc?.line,
        column: loc?.column
      });
      continue;
    }

    items.push({
      id: "output.fields." + String(i),
      kind: "unknown",
      label: "(unknown)",
      raw,
      line: loc?.line,
      column: loc?.column
    });
  }

  return { ok: true, headerBy, items };
};

const collectFieldsFromMap = (mapNode: YAMLMap, origin: string): FieldCandidate[] => {
  const items: FieldCandidate[] = [];
  for (const pair of mapNode.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
    const fieldId = scalarKeyToString(pair.key);
    const value = (pair.value as Node | null) || null;
    if (!value || !isMap(value)) continue;
    const fieldMap = value as YAMLMap;
    const anchor = (fieldMap as any).anchor ? String((fieldMap as any).anchor) : "";
    const name = scalarString((findPairInMap(fieldMap, "name")?.value as Node | null) || null);
    items.push({
      id: origin + ":" + fieldId,
      origin,
      fieldId,
      anchor: anchor || undefined,
      name: name || undefined
    });
  }
  return items;
};

export const collectFieldCandidates = (yamlText: string): FieldCandidate[] => {
  let doc: any;
  try {
    doc = parseDocument(yamlText, { keepSourceTokens: true });
  } catch {
    return [];
  }
  const root = (doc?.contents as Node | null) || null;
  if (!root || !isMap(root)) return [];

  const candidates: FieldCandidate[] = [];

  const mainFields = getIn(root, ["main_source", "fields"]);
  if (mainFields && isMap(mainFields)) {
    candidates.push(...collectFieldsFromMap(mainFields as any, "main_source.fields"));
  }

  const sourcesNode = getIn(root, ["sources"]);
  if (sourcesNode && isMap(sourcesNode)) {
    const sourcesMap = sourcesNode as YAMLMap;
    for (const pair of sourcesMap.items as Array<Pair<ParsedNode, ParsedNode | null>>) {
      const sourceId = scalarKeyToString(pair.key);
      const sourceNode = (pair.value as Node | null) || null;
      if (!sourceNode || !isMap(sourceNode)) continue;
      const fields = getIn(sourceNode, ["fields"]);
      if (fields && isMap(fields)) {
        candidates.push(...collectFieldsFromMap(fields as any, "sources." + sourceId + ".fields"));
      }
    }
  }

  const derivedFields = getIn(root, ["fields"]);
  if (derivedFields && isMap(derivedFields)) {
    candidates.push(...collectFieldsFromMap(derivedFields as any, "fields"));
  }

  candidates.sort((a, b) => {
    const ao = a.origin.localeCompare(b.origin);
    if (ao) return ao;
    return a.fieldId.localeCompare(b.fieldId);
  });

  return candidates;
};

export const computeHeaderPreview = (
  headerBy: OutputHeaderBy,
  items: OutputFieldItem[]
): { headers: string[]; duplicates: Array<{ value: string; count: number }> } => {
  const headers: string[] = [];
  const counts = new Map<string, number>();

  for (const item of items) {
    let header = "";
    if (headerBy === "name") header = (item.name || "").trim();
    if (!header) header = (item.fieldId || "").trim();
    if (!header) header = item.label;
    headers.push(header);
    counts.set(header, (counts.get(header) || 0) + 1);
  }

  const duplicates: Array<{ value: string; count: number }> = [];
  for (const [value, count] of counts.entries()) {
    if (value && count > 1) duplicates.push({ value, count });
  }
  duplicates.sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));

  return { headers, duplicates };
};

