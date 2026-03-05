const isObject = (value: any): boolean => {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
};

const decodeJsonPointerToken = (token: string): string => {
  return token.replace(/~1/g, "/").replace(/~0/g, "~");
};

const getByJsonPointer = (root: any, pointer: string): any => {
  if (!pointer) return null;
  const raw = pointer.startsWith("#") ? pointer.slice(1) : pointer;
  if (!raw) return root;
  if (!raw.startsWith("/")) return null;
  const parts = raw
    .slice(1)
    .split("/")
    .map((p) => decodeJsonPointerToken(p));

  let cur: any = root;
  for (const part of parts) {
    if (!isObject(cur) && !Array.isArray(cur)) return null;
    cur = (cur as any)[part];
    if (cur == null) return null;
  }
  return cur;
};

const resolveLocalRef = (rootSchema: any, ref: string): any => {
  if (typeof ref !== "string") return null;
  if (!ref.startsWith("#/")) return null;
  return getByJsonPointer(rootSchema, ref);
};

const deref = (rootSchema: any, schemaNode: any, depth: number): any => {
  let cur = schemaNode;
  for (let i = 0; i < 8 && depth < 16; i += 1) {
    if (!isObject(cur) || typeof (cur as any).$ref !== "string") return cur;
    const next = resolveLocalRef(rootSchema, (cur as any).$ref);
    if (!next) return cur;
    cur = next;
    depth += 1;
  }
  return cur;
};

const expandSchema = (rootSchema: any, schemaNode: any, depth = 0): any[] => {
  const node = deref(rootSchema, schemaNode, depth);
  if (!isObject(node)) return [];

  const out: any[] = [node];

  const allOf = (node as any).allOf;
  if (Array.isArray(allOf)) {
    for (const item of allOf) out.push(...expandSchema(rootSchema, item, depth + 1));
  }

  const anyOf = (node as any).anyOf;
  if (Array.isArray(anyOf)) {
    for (const item of anyOf) out.push(...expandSchema(rootSchema, item, depth + 1));
  }

  const oneOf = (node as any).oneOf;
  if (Array.isArray(oneOf)) {
    for (const item of oneOf) out.push(...expandSchema(rootSchema, item, depth + 1));
  }

  return out;
};

const parsePath = (path: string | string[]): string[] => {
  if (Array.isArray(path)) return path.filter((p) => p != null && String(p).trim() !== "").map((p) => String(p));
  return String(path || "")
    .split(".")
    .map((p) => p.trim())
    .filter(Boolean);
};

const pickArrayItemsSchema = (rootSchema: any, current: any): any | null => {
  const expanded = expandSchema(rootSchema, current);
  for (const node of expanded) {
    const items = (node as any).items;
    if (items == null) continue;
    if (Array.isArray(items)) return items[0] || null;
    return items;
  }
  return null;
};

const pickPropertySchema = (rootSchema: any, current: any, prop: string): any | null => {
  const expanded = expandSchema(rootSchema, current);
  for (const node of expanded) {
    const props = (node as any).properties;
    if (isObject(props) && (props as any)[prop] != null) return (props as any)[prop];

    const patterns = (node as any).patternProperties;
    if (isObject(patterns)) {
      for (const [pat, schema] of Object.entries(patterns)) {
        try {
          const re = new RegExp(pat);
          if (re.test(prop)) return schema;
        } catch {
          // ignore invalid regex
        }
      }
    }

    const additional = (node as any).additionalProperties;
    if (isObject(additional)) return additional;
  }
  return null;
};

const schemaForPath = (rootSchema: any, path: string | string[]): any | null => {
  const segments = parsePath(path);
  let cur: any = rootSchema;

  for (const seg of segments) {
    if (/^\d+$/.test(seg)) {
      const next = pickArrayItemsSchema(rootSchema, cur);
      if (!next) return null;
      cur = next;
      continue;
    }

    const next = pickPropertySchema(rootSchema, cur, seg);
    if (!next) return null;
    cur = next;
  }

  return cur;
};

export const schemaDescriptionForPath = (rootSchema: any, path: string | string[]): string => {
  const node = schemaForPath(rootSchema, path);
  if (!node) return "";

  const expanded = expandSchema(rootSchema, node);
  for (const n of expanded) {
    const desc = (n as any).description;
    if (typeof desc === "string" && desc.trim()) return desc.trim();
    const md = (n as any).markdownDescription;
    if (typeof md === "string" && md.trim()) return md.trim();
    const title = (n as any).title;
    if (typeof title === "string" && title.trim()) return title.trim();
  }

  return "";
};

const requiredPropsForObjectSchema = (rootSchema: any, schemaNode: any): Set<string> => {
  const node = deref(rootSchema, schemaNode, 0);
  const expanded = expandSchema(rootSchema, node);
  const out = new Set<string>();
  for (const n of expanded) {
    const req = (n as any).required;
    if (!Array.isArray(req)) continue;
    for (const item of req) {
      if (typeof item === "string" && item.trim()) out.add(item);
    }
  }
  return out;
};

export const schemaIsRequiredForPath = (rootSchema: any, path: string | string[]): boolean | null => {
  const segments = parsePath(path);
  if (!segments.length) return null;

  const parentPath = segments.slice(0, -1);
  const prop = segments[segments.length - 1] as string;
  const parentSchema = schemaForPath(rootSchema, parentPath);
  if (!parentSchema) return null;

  const req = requiredPropsForObjectSchema(rootSchema, parentSchema);
  return req.has(prop);
};
