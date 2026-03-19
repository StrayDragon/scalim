import type { JsonSchemaNode, ScalarValue } from "./types.ts";

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

export const derefSchemaNode = (rootSchema: JsonSchemaNode, schemaNode: any, opts?: { maxDepth?: number }): JsonSchemaNode | null => {
  const maxDepth = opts && typeof opts.maxDepth === "number" ? opts.maxDepth : 16;
  let cur = schemaNode as any;
  for (let depth = 0; depth < maxDepth; depth += 1) {
    if (!isObject(cur)) return null;
    const ref = (cur as any).$ref;
    if (typeof ref !== "string") return cur as JsonSchemaNode;
    const next = resolveLocalRef(rootSchema, ref);
    if (!next) return cur as JsonSchemaNode;
    cur = next;
  }
  return isObject(cur) ? (cur as JsonSchemaNode) : null;
};

export const expandAllOf = (rootSchema: JsonSchemaNode, schemaNode: any, depth = 0): JsonSchemaNode[] => {
  if (depth > 16) return [];
  const node = derefSchemaNode(rootSchema, schemaNode);
  if (!node) return [];

  const out: JsonSchemaNode[] = [node];
  const allOf = (node as any).allOf;
  if (Array.isArray(allOf)) {
    for (const item of allOf) {
      out.push(...expandAllOf(rootSchema, item, depth + 1));
    }
  }
  return out;
};

const firstString = (items: any[], key: string): string => {
  for (const node of items) {
    const v = (node as any)?.[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
};

export const schemaTitle = (expandedNodes: JsonSchemaNode[], fallbackTitle: string): string => {
  const title = firstString(expandedNodes, "title");
  if (title) return title;
  return String(fallbackTitle || "").trim();
};

export const schemaDescription = (expandedNodes: JsonSchemaNode[]): string => {
  const md = firstString(expandedNodes, "markdownDescription");
  if (md) return md;
  return firstString(expandedNodes, "description");
};

export const schemaExamples = (expandedNodes: JsonSchemaNode[]): any[] => {
  for (const node of expandedNodes) {
    const ex = (node as any)?.examples;
    if (Array.isArray(ex) && ex.length) return ex.slice(0);
  }
  return [];
};

export const schemaType = (expandedNodes: JsonSchemaNode[]): string => {
  for (const node of expandedNodes) {
    const t = (node as any)?.type;
    if (typeof t === "string" && t.trim()) return t.trim();
  }
  return "unknown";
};

export const schemaConst = (expandedNodes: JsonSchemaNode[]): ScalarValue | undefined => {
  for (const node of expandedNodes) {
    const v = (node as any)?.const;
    if (v === null) return null;
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return v as ScalarValue;
  }
  return undefined;
};

export const schemaEnum = (expandedNodes: JsonSchemaNode[]): ScalarValue[] => {
  for (const node of expandedNodes) {
    const v = (node as any)?.enum;
    if (!Array.isArray(v)) continue;
    const out: ScalarValue[] = [];
    for (const item of v) {
      if (item === null || typeof item === "string" || typeof item === "number" || typeof item === "boolean") out.push(item as ScalarValue);
    }
    if (out.length) return out;
  }
  return [];
};

export const schemaProperties = (expandedNodes: JsonSchemaNode[]): Record<string, any> => {
  const out: Record<string, any> = {};
  for (const node of expandedNodes) {
    const props = (node as any)?.properties;
    if (!isObject(props)) continue;
    for (const [k, v] of Object.entries(props)) {
      out[String(k)] = v;
    }
  }
  return out;
};

export const schemaRequiredKeys = (expandedNodes: JsonSchemaNode[]): Set<string> => {
  const out = new Set<string>();
  for (const node of expandedNodes) {
    const req = (node as any)?.required;
    if (!Array.isArray(req)) continue;
    for (const item of req) {
      if (typeof item === "string" && item.trim()) out.add(item.trim());
    }
  }
  return out;
};

export const schemaItems = (expandedNodes: JsonSchemaNode[]): any | null => {
  for (const node of expandedNodes) {
    const items = (node as any)?.items;
    if (items == null) continue;
    if (Array.isArray(items)) return items[0] || null;
    return items;
  }
  return null;
};

export const schemaForObjectKey = (rootSchema: JsonSchemaNode, schemaNode: any, key: string): JsonSchemaNode | null => {
  const expanded = expandAllOf(rootSchema, schemaNode);
  for (const node of expanded) {
    const props = (node as any)?.properties;
    if (isObject(props) && (props as any)[key] != null) return (props as any)[key] as JsonSchemaNode;

    const patterns = (node as any)?.patternProperties;
    if (isObject(patterns)) {
      for (const [pat, schema] of Object.entries(patterns)) {
        try {
          const re = new RegExp(String(pat));
          if (re.test(key)) return schema as JsonSchemaNode;
        } catch {
          // ignore invalid regex
        }
      }
    }

    const additional = (node as any)?.additionalProperties;
    if (isObject(additional)) return additional as JsonSchemaNode;
  }
  return null;
};

export const mergeExpandedNodes = (expandedNodes: JsonSchemaNode[]): JsonSchemaNode => {
  const out: JsonSchemaNode = {};

  const mergeObj = (target: any, src: any) => {
    if (!isObject(src)) return;
    for (const [k, v] of Object.entries(src)) {
      (target as any)[k] = v;
    }
  };

  const required: string[] = [];
  for (const node of expandedNodes) {
    if (!isObject(node)) continue;
    if (typeof (node as any).type === "string" && typeof (out as any).type !== "string") (out as any).type = (node as any).type;

    for (const key of ["title", "markdownDescription", "description"] as const) {
      if (typeof (out as any)[key] === "string" && String((out as any)[key]).trim()) continue;
      const v = (node as any)[key];
      if (typeof v === "string" && v.trim()) (out as any)[key] = v;
    }

    if (!Array.isArray((out as any).examples) && Array.isArray((node as any).examples)) (out as any).examples = (node as any).examples;
    if ((out as any).default == null && (node as any).default != null) (out as any).default = (node as any).default;

    if ((out as any).const == null && (node as any).const != null) (out as any).const = (node as any).const;
    if (!Array.isArray((out as any).enum) && Array.isArray((node as any).enum)) (out as any).enum = (node as any).enum;

    if (!Array.isArray((out as any).anyOf) && Array.isArray((node as any).anyOf)) (out as any).anyOf = (node as any).anyOf;
    if (!Array.isArray((out as any).oneOf) && Array.isArray((node as any).oneOf)) (out as any).oneOf = (node as any).oneOf;
    if (!Array.isArray((out as any).allOf) && Array.isArray((node as any).allOf)) (out as any).allOf = (node as any).allOf;

    if ((out as any).items == null && (node as any).items != null) (out as any).items = (node as any).items;
    if ((out as any).additionalProperties == null && (node as any).additionalProperties != null) {
      (out as any).additionalProperties = (node as any).additionalProperties;
    }
    if (!isObject((out as any).patternProperties) && isObject((node as any).patternProperties)) {
      (out as any).patternProperties = (node as any).patternProperties;
    }

    mergeObj((out as any).properties || ((out as any).properties = {}), (node as any).properties);

    const req = (node as any).required;
    if (Array.isArray(req)) {
      for (const item of req) {
        if (typeof item === "string" && item.trim()) required.push(item.trim());
      }
    }
  }

  if (required.length) (out as any).required = Array.from(new Set(required));
  return out;
};
