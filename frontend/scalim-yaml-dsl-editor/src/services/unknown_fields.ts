import type { DemandSchema } from "$services/schema";

export type UnknownField = {
  path: string;
  field: string;
  suggestions: string[];
};

const unescapeJsonPointer = (value: string) => {
  // Avoid String.prototype.replaceAll (ES2021); keep ES2020 lib compatibility.
  return value.split("~1").join("/").split("~0").join("~");
};

const resolveJsonPointer = (root: DemandSchema, pointer: string): DemandSchema | null => {
  if (!pointer.startsWith("#/")) return null;
  let current: any = root;
  for (const rawPart of pointer.slice(2).split("/")) {
    const part = unescapeJsonPointer(rawPart);
    if (current == null || typeof current !== "object") return null;
    if (!(part in current)) return null;
    current = current[part];
  }
  if (current == null || typeof current !== "object") return null;
  return current as DemandSchema;
};

const derefSchema = (schema: DemandSchema, rootSchema: DemandSchema): DemandSchema => {
  let current: DemandSchema = schema;
  for (let i = 0; i < 32; i += 1) {
    const ref = current["$ref"];
    if (typeof ref !== "string") return current;
    const resolved = resolveJsonPointer(rootSchema, ref);
    if (!resolved) return current;
    current = resolved;
  }
  return current;
};

const iterEffectiveSchemas = (schema: DemandSchema, rootSchema: DemandSchema, seen: Set<DemandSchema>): DemandSchema[] => {
  const current = derefSchema(schema, rootSchema);
  if (seen.has(current)) return [];
  seen.add(current);

  const schemas: DemandSchema[] = [current];
  const allOf = current["allOf"];
  if (Array.isArray(allOf)) {
    for (const item of allOf) {
      if (item && typeof item === "object") {
        schemas.push(...iterEffectiveSchemas(item as DemandSchema, rootSchema, seen));
      }
    }
  }
  return schemas;
};

const selectChildSchema = (schema: DemandSchema, rootSchema: DemandSchema, key: string): DemandSchema | null => {
  const variants = iterEffectiveSchemas(schema, rootSchema, new Set<DemandSchema>());
  for (const variant of variants) {
    const props = variant["properties"];
    if (props && typeof props === "object" && key in props) {
      const child = (props as any)[key];
      if (child && typeof child === "object") return child as DemandSchema;
    }
  }
  for (const variant of variants) {
    const additional = variant["additionalProperties"];
    if (additional && typeof additional === "object") {
      return additional as DemandSchema;
    }
  }
  return null;
};

const collectPropertyKeys = (schema: DemandSchema, rootSchema: DemandSchema): Set<string> | null => {
  const variants = iterEffectiveSchemas(schema, rootSchema, new Set<DemandSchema>());
  let sawProps = false;
  const keys = new Set<string>();
  for (const variant of variants) {
    const props = variant["properties"];
    if (props && typeof props === "object") {
      sawProps = true;
      for (const k of Object.keys(props)) keys.add(k);
    }
  }
  return sawProps ? keys : null;
};

const getSchemaProperties = (schema: DemandSchema, path: string[]): Set<string> | null => {
  const rootSchema = schema;
  let current: DemandSchema = schema;
  for (const key of path) {
    const next = selectChildSchema(current, rootSchema, key);
    if (!next) return null;
    current = next;
  }
  return collectPropertyKeys(current, rootSchema);
};

const levenshtein = (a: string, b: string): number => {
  const m = a.length;
  const n = b.length;
  if (!m) return n;
  if (!n) return m;
  const dp: number[] = [];
  for (let j = 0; j <= n; j += 1) dp[j] = j;
  for (let i = 1; i <= m; i += 1) {
    let prev = dp[0];
    dp[0] = i;
    for (let j = 1; j <= n; j += 1) {
      const tmp = dp[j];
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[j] = Math.min(dp[j] + 1, dp[j - 1] + 1, prev + cost);
      prev = tmp;
    }
  }
  return dp[n];
};

const closestKeys = (key: string, candidates: Iterable<string>, limit: number): string[] => {
  const scored: Array<{ k: string; s: number }> = [];
  for (const cand of candidates) {
    scored.push({ k: cand, s: levenshtein(key, cand) });
  }
  scored.sort((a, b) => a.s - b.s);
  return scored.slice(0, limit).map((item) => item.k);
};

export const findUnknownFields = (
  yamlData: unknown,
  schema: DemandSchema,
  path: string[] = []
): UnknownField[] => {
  if (yamlData == null || typeof yamlData !== "object" || Array.isArray(yamlData)) return [];

  const yamlObj = yamlData as Record<string, unknown>;
  const known = getSchemaProperties(schema, path);
  const unknown: UnknownField[] = [];

  for (const rawKey of Object.keys(yamlObj)) {
    const key = String(rawKey);
    if (key.startsWith("_")) continue;
    if (key === "<<") continue;
    const nextPath = [...path, key];
    const pathStr = nextPath.join(".");

    if (known && !known.has(key)) {
      const suggestions = closestKeys(key, known, 3);
      unknown.push({ path: pathStr, field: key, suggestions });
    }

    const value = yamlObj[rawKey];
    unknown.push(...collectNestedUnknowns(value, schema, nextPath));
  }

  return unknown;
};

const collectNestedUnknowns = (value: unknown, schema: DemandSchema, path: string[]): UnknownField[] => {
  if (value == null) return [];
  if (Array.isArray(value)) {
    const nested: UnknownField[] = [];
    for (let i = 0; i < value.length; i += 1) {
      const item = value[i];
      if (item && typeof item === "object" && !Array.isArray(item)) {
        nested.push(...findUnknownFields(item, schema, [...path, String(i)]));
      }
    }
    return nested;
  }
  if (typeof value === "object") {
    return findUnknownFields(value, schema, path);
  }
  return [];
};
