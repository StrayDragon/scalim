export type JsonSchemaNode = Record<string, any>;

export type YamlPath = string[];

export type BlockKind = "scalar" | "enum" | "object" | "array" | "map" | "union" | "custom" | "unsupported";

export type ScalarValue = string | number | boolean | null;

export type ScalarType = "string" | "number" | "integer" | "boolean" | "null" | "unknown";

export type SchemaNodeInfo = {
  raw: JsonSchemaNode | null;
  expanded: JsonSchemaNode;
  expandedNodes: JsonSchemaNode[];
};

export type BlockAction =
  | {
      kind: "set";
      path: YamlPath;
      value: ScalarValue;
      createMissing: boolean;
    }
  | {
      kind: "delete";
      path: YamlPath;
      pruneEmptyParents: boolean;
    }
  | {
      kind: "ensure_map";
      path: YamlPath;
      createMissing: boolean;
    }
  | {
      kind: "ensure_seq";
      path: YamlPath;
      createMissing: boolean;
    }
  | {
      kind: "insert";
      path: YamlPath;
      index: number;
      valueKind: "string" | "inline";
      value: string;
    }
  | {
      kind: "remove";
      path: YamlPath;
      index: number;
    }
  | {
      kind: "move";
      path: YamlPath;
      from: number;
      to: number;
    };

export type BlockActions = {
  setScalar?: (value: ScalarValue, opts?: { createMissing?: boolean }) => BlockAction;
  deletePath?: (opts?: { pruneEmptyParents?: boolean }) => BlockAction;
  ensureMap?: (opts?: { createMissing?: boolean }) => BlockAction;
  ensureSeq?: (opts?: { createMissing?: boolean }) => BlockAction;
  insertSeqItem?: (index: number, value: string, opts?: { valueKind?: "string" | "inline" }) => BlockAction;
  removeSeqItem?: (index: number) => BlockAction;
  moveSeqItem?: (from: number, to: number) => BlockAction;
};

export type UnionOption = {
  id: string;
  title: string;
  schemaNode: SchemaNodeInfo;
  discriminator: null | { kind: "const"; path: YamlPath; value: ScalarValue } | { kind: "required_keys"; keys: string[] };
};

export type EditableBlock = {
  id: string;
  yamlPath: YamlPath;
  kind: BlockKind;
  title: string;
  description: string;
  required: boolean | null;
  present: boolean;
  schemaNode: SchemaNodeInfo;
  actions: BlockActions;
  children: EditableBlock[];

  scalar?: {
    value: ScalarValue | undefined;
    type: ScalarType;
  };
  enum?: {
    values: ScalarValue[];
    value: ScalarValue | undefined;
  };
  array?: {
    length: number | null;
    itemsSchema: SchemaNodeInfo | null;
  };
  map?: {
    keys: string[];
    valueSchema: SchemaNodeInfo | null;
  };
  union?: {
    options: UnionOption[];
    inferredOptionId: string | null;
  };
  custom?: {
    // Component is intentionally `unknown` to keep schema_blocks independent of Svelte types.
    component: unknown;
    props?: Record<string, any>;
  };
  unsupported?: {
    reason: string;
    rawYamlPath: YamlPath;
  };
};

export const yamlPathToId = (yamlPath: YamlPath): string => {
  return yamlPath.join(".");
};
