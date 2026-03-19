import type { YamlLocationIndex } from "../../services/yaml_doc.ts";
import type { JsonSchemaNode, ScalarType, ScalarValue, SchemaNodeInfo, EditableBlock, YamlPath, UnionOption } from "./types.ts";
import { yamlPathToId } from "./types.ts";
import { expandAllOf, mergeExpandedNodes, schemaConst, schemaDescription, schemaEnum, schemaForObjectKey, schemaItems, schemaProperties, schemaRequiredKeys, schemaTitle, schemaType } from "./schema_traversal.ts";
import type { OverrideRegistry } from "./override_registry.ts";

const isPlainObject = (value: any): boolean => {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
};

const isPresentAtPath = (yamlPath: YamlPath, locations?: YamlLocationIndex): boolean => {
  if (!locations) return false;
  const key = yamlPath.join(".");
  return Boolean((locations as any)[key]);
};

const getYamlValueAtPath = (data: any, yamlPath: YamlPath): any => {
  let cur = data;
  for (const seg of yamlPath) {
    if (cur == null) return undefined;
    if (/^\\d+$/.test(seg)) {
      const idx = Number(seg);
      if (!Array.isArray(cur)) return undefined;
      cur = cur[idx];
      continue;
    }
    if (!isPlainObject(cur)) return undefined;
    cur = (cur as any)[seg];
  }
  return cur;
};

const schemaNodeInfo = (rootSchema: JsonSchemaNode, raw: any): SchemaNodeInfo => {
  const expandedNodes = expandAllOf(rootSchema, raw);
  const expanded = mergeExpandedNodes(expandedNodes);
  return { raw: (isPlainObject(raw) ? (raw as JsonSchemaNode) : null) as JsonSchemaNode | null, expanded, expandedNodes };
};

const scalarTypeFor = (expandedNodes: JsonSchemaNode[]): ScalarType => {
  const t = schemaType(expandedNodes);
  if (t === "string" || t === "number" || t === "integer" || t === "boolean" || t === "null") return t;
  return "unknown";
};

const baseActionsForPath = (yamlPath: YamlPath): EditableBlock["actions"] => {
  return {
    setScalar: (value, opts) => ({
      kind: "set" as const,
      path: yamlPath,
      value,
      createMissing: typeof opts?.createMissing === "boolean" ? opts.createMissing : true
    }),
    deletePath: (opts) => ({
      kind: "delete" as const,
      path: yamlPath,
      pruneEmptyParents: typeof opts?.pruneEmptyParents === "boolean" ? opts.pruneEmptyParents : true
    }),
    ensureMap: (opts) => ({
      kind: "ensure_map" as const,
      path: yamlPath,
      createMissing: typeof opts?.createMissing === "boolean" ? opts.createMissing : true
    }),
    ensureSeq: (opts) => ({
      kind: "ensure_seq" as const,
      path: yamlPath,
      createMissing: typeof opts?.createMissing === "boolean" ? opts.createMissing : true
    }),
    insertSeqItem: (index, value, opts) => ({
      kind: "insert" as const,
      path: yamlPath,
      index,
      valueKind: opts?.valueKind || "string",
      value
    }),
    removeSeqItem: (index) => ({
      kind: "remove" as const,
      path: yamlPath,
      index
    }),
    moveSeqItem: (from, to) => ({
      kind: "move" as const,
      path: yamlPath,
      from,
      to
    })
  };
};

const buildUnionOptions = (rootSchema: JsonSchemaNode, unionNode: JsonSchemaNode): UnionOption[] => {
  const branches = Array.isArray((unionNode as any).oneOf) ? (unionNode as any).oneOf : (unionNode as any).anyOf;
  if (!Array.isArray(branches)) return [];

  const options: UnionOption[] = [];
  for (let i = 0; i < branches.length; i += 1) {
    const raw = branches[i];
    const info = schemaNodeInfo(rootSchema, raw);
    const title = schemaTitle(info.expandedNodes, "Option " + String(i + 1));

    let discriminator: UnionOption["discriminator"] = null;
    const props = schemaProperties(info.expandedNodes);
    for (const [k, propSchema] of Object.entries(props)) {
      const propInfo = schemaNodeInfo(rootSchema, propSchema);
      const c = schemaConst(propInfo.expandedNodes);
      if (c !== undefined) {
        discriminator = { kind: "const", path: [String(k)], value: c };
        break;
      }
    }

    if (!discriminator) {
      const req = schemaRequiredKeys(info.expandedNodes);
      if (req.size) discriminator = { kind: "required_keys", keys: Array.from(req).sort() };
    }

    options.push({
      id: String(i),
      title,
      schemaNode: info,
      discriminator
    });
  }
  return options;
};

const inferUnionOptionId = (options: UnionOption[], yamlData: any): string | null => {
  const constMatches: string[] = [];
  for (const opt of options) {
    if (!opt.discriminator || opt.discriminator.kind !== "const") continue;
    const v = getYamlValueAtPath(yamlData, opt.discriminator.path);
    if (v === opt.discriminator.value) constMatches.push(opt.id);
  }
  if (constMatches.length === 1) return constMatches[0] as string;

  const reqMatches: string[] = [];
  for (const opt of options) {
    if (!opt.discriminator || opt.discriminator.kind !== "required_keys") continue;
    if (!isPlainObject(yamlData)) continue;
    let ok = true;
    for (const k of opt.discriminator.keys) {
      if (!Object.prototype.hasOwnProperty.call(yamlData, k)) {
        ok = false;
        break;
      }
    }
    if (ok) reqMatches.push(opt.id);
  }
  if (reqMatches.length === 1) return reqMatches[0] as string;

  return null;
};

const classifyKind = (info: SchemaNodeInfo): EditableBlock["kind"] => {
  const expanded = info.expandedNodes;

  if (Array.isArray((info.expanded as any).oneOf) || Array.isArray((info.expanded as any).anyOf)) return "union";

  const enumValues = schemaEnum(expanded);
  const constValue = schemaConst(expanded);
  if (enumValues.length || constValue !== undefined) return "enum";

  const t = schemaType(expanded);
  if (t === "array" || schemaItems(expanded) != null) return "array";

  const props = schemaProperties(expanded);
  const hasProps = Object.keys(props).length > 0;
  const hasPattern = isPlainObject((info.expanded as any).patternProperties);
  const hasAdditional = isPlainObject((info.expanded as any).additionalProperties);
  if ((hasPattern || hasAdditional) && !hasProps) return "map";

  if (t === "object" || hasProps) return "object";

  return "scalar";
};

const buildBlockForNode = (args: {
  rootSchema: JsonSchemaNode;
  rawSchemaNode: any;
  yamlPath: YamlPath;
  yamlData: any;
  yamlLocations?: YamlLocationIndex;
  overrides?: OverrideRegistry;
  required: boolean | null;
  titleFallback: string;
}): EditableBlock => {
  const info = schemaNodeInfo(args.rootSchema, args.rawSchemaNode);
  const title = schemaTitle(info.expandedNodes, args.titleFallback);
  const description = schemaDescription(info.expandedNodes);
  const present = isPresentAtPath(args.yamlPath, args.yamlLocations);
  const value = getYamlValueAtPath(args.yamlData, args.yamlPath);
  const id = yamlPathToId(args.yamlPath);
  const actions = baseActionsForPath(args.yamlPath);

  const buildChildren = (): EditableBlock[] => {
    const kind = classifyKind(info);
    if (kind === "object") {
      return buildBlocks({
        rootSchema: args.rootSchema,
        schemaNode: info.expanded,
        yamlPath: args.yamlPath,
        yamlData: args.yamlData,
        yamlLocations: args.yamlLocations,
        overrides: args.overrides
      });
    }
    if (kind === "map") {
      const nodeVal = getYamlValueAtPath(args.yamlData, args.yamlPath);
      const keys = isPlainObject(nodeVal) ? Object.keys(nodeVal).sort() : [];
      const children: EditableBlock[] = [];
      for (const k of keys) {
        const childSchema = schemaForObjectKey(args.rootSchema, info.expanded, k);
        if (!childSchema) continue;
        children.push(
          buildBlockForNode({
            rootSchema: args.rootSchema,
            rawSchemaNode: childSchema,
            yamlPath: args.yamlPath.concat([k]),
            yamlData: args.yamlData,
            yamlLocations: args.yamlLocations,
            overrides: args.overrides,
            required: null,
            titleFallback: k
          })
        );
      }
      return children;
    }
    if (kind === "array") {
      const itemsRaw = schemaItems(info.expandedNodes);
      const nodeVal = getYamlValueAtPath(args.yamlData, args.yamlPath);
      const n = Array.isArray(nodeVal) ? nodeVal.length : 0;
      const children: EditableBlock[] = [];
      for (let i = 0; i < n; i += 1) {
        const itemPath = args.yamlPath.concat([String(i)]);
        const itemTitle = "[" + String(i) + "]";
        const itemSchema = itemsRaw;
        if (!itemSchema) {
          children.push({
            id: yamlPathToId(itemPath),
            yamlPath: itemPath,
            kind: "unsupported",
            title: itemTitle,
            description: "Missing items schema",
            required: null,
            present: isPresentAtPath(itemPath, args.yamlLocations),
            schemaNode: schemaNodeInfo(args.rootSchema, {}),
            actions: baseActionsForPath(itemPath),
            children: [],
            unsupported: { reason: "Missing items schema", rawYamlPath: itemPath }
          });
          continue;
        }
        children.push(
          buildBlockForNode({
            rootSchema: args.rootSchema,
            rawSchemaNode: itemSchema,
            yamlPath: itemPath,
            yamlData: args.yamlData,
            yamlLocations: args.yamlLocations,
            overrides: args.overrides,
            required: null,
            titleFallback: itemTitle
          })
        );
      }
      return children;
    }

    if (kind === "union") {
      const unionNode = info.expanded;
      const options = buildUnionOptions(args.rootSchema, unionNode);
      const nodeVal = getYamlValueAtPath(args.yamlData, args.yamlPath);
      const inferredId = inferUnionOptionId(options, nodeVal);
      const inferred = options.find((o) => o.id === inferredId) || null;
      if (!inferred) return [];

      const inferredKind = classifyKind(inferred.schemaNode);
      if (inferredKind === "object") {
        return buildBlocks({
          rootSchema: args.rootSchema,
          schemaNode: inferred.schemaNode.expanded,
          yamlPath: args.yamlPath,
          yamlData: args.yamlData,
          yamlLocations: args.yamlLocations,
          overrides: args.overrides
        });
      }
      if (inferredKind === "array") {
        const itemsRaw = schemaItems(inferred.schemaNode.expandedNodes);
        const nodeVal2 = getYamlValueAtPath(args.yamlData, args.yamlPath);
        const n2 = Array.isArray(nodeVal2) ? nodeVal2.length : 0;
        const children2: EditableBlock[] = [];
        for (let i = 0; i < n2; i += 1) {
          const itemPath = args.yamlPath.concat([String(i)]);
          children2.push(
            buildBlockForNode({
              rootSchema: args.rootSchema,
              rawSchemaNode: itemsRaw || {},
              yamlPath: itemPath,
              yamlData: args.yamlData,
              yamlLocations: args.yamlLocations,
              overrides: args.overrides,
              required: null,
              titleFallback: "[" + String(i) + "]"
            })
          );
        }
        return children2;
      }
    }

    return [];
  };

  const override = args.overrides?.match(args.yamlPath) || null;
  if (override) {
    return override.build({
      rootSchema: args.rootSchema,
      schemaNode: info.expanded,
      schemaNodeInfo: info,
      yamlPath: args.yamlPath,
      yamlData: args.yamlData,
      yamlLocations: args.yamlLocations,
      required: args.required,
      present,
      actions,
      buildChildren
    });
  }

  const kind = classifyKind(info);

  if (kind === "enum") {
    const values = schemaEnum(info.expandedNodes);
    const c = schemaConst(info.expandedNodes);
    const enumValues = values.length ? values : c !== undefined ? [c as ScalarValue] : [];
    const current = value as ScalarValue | undefined;
    return {
      id,
      yamlPath: args.yamlPath,
      kind: "enum",
      title,
      description,
      required: args.required,
      present,
      schemaNode: info,
      actions: {
        setScalar: actions.setScalar,
        deletePath: actions.deletePath
      },
      children: [],
      enum: { values: enumValues, value: current }
    };
  }

  if (kind === "object") {
    return {
      id,
      yamlPath: args.yamlPath,
      kind: "object",
      title,
      description,
      required: args.required,
      present,
      schemaNode: info,
      actions: {
        ensureMap: actions.ensureMap,
        deletePath: actions.deletePath
      },
      children: buildChildren()
    };
  }

  if (kind === "map") {
    const nodeVal = value;
    const keys = isPlainObject(nodeVal) ? Object.keys(nodeVal).sort() : [];
    const valueSchemaNode = schemaForObjectKey(args.rootSchema, info.expanded, keys[0] || "") || null;
    return {
      id,
      yamlPath: args.yamlPath,
      kind: "map",
      title,
      description,
      required: args.required,
      present,
      schemaNode: info,
      actions: {
        ensureMap: actions.ensureMap,
        deletePath: actions.deletePath,
        setScalar: actions.setScalar
      },
      children: buildChildren(),
      map: { keys, valueSchema: valueSchemaNode ? schemaNodeInfo(args.rootSchema, valueSchemaNode) : null }
    };
  }

  if (kind === "array") {
    const nodeVal = value;
    const n = Array.isArray(nodeVal) ? nodeVal.length : null;
    const itemsRaw = schemaItems(info.expandedNodes);
    return {
      id,
      yamlPath: args.yamlPath,
      kind: "array",
      title,
      description,
      required: args.required,
      present,
      schemaNode: info,
      actions: {
        ensureSeq: actions.ensureSeq,
        deletePath: actions.deletePath,
        insertSeqItem: actions.insertSeqItem,
        removeSeqItem: actions.removeSeqItem,
        moveSeqItem: actions.moveSeqItem
      },
      children: buildChildren(),
      array: { length: n, itemsSchema: itemsRaw ? schemaNodeInfo(args.rootSchema, itemsRaw) : null }
    };
  }

  if (kind === "union") {
    const unionNode = info.expanded;
    const options = buildUnionOptions(args.rootSchema, unionNode);
    const nodeVal = value;
    const inferredId = inferUnionOptionId(options, nodeVal);

    if (!inferredId) {
      return {
        id,
        yamlPath: args.yamlPath,
        kind: "unsupported",
        title,
        description,
        required: args.required,
        present,
        schemaNode: info,
        actions: {
          deletePath: actions.deletePath
        },
        children: [],
        unsupported: {
          reason: "union branch is not inferable",
          rawYamlPath: args.yamlPath
        }
      };
    }

    return {
      id,
      yamlPath: args.yamlPath,
      kind: "union",
      title,
      description,
      required: args.required,
      present,
      schemaNode: info,
      actions: {
        deletePath: actions.deletePath
      },
      children: buildChildren(),
      union: { options, inferredOptionId: inferredId }
    };
  }

  const scalarType = scalarTypeFor(info.expandedNodes);
  const scalarValue = value as ScalarValue | undefined;
  return {
    id,
    yamlPath: args.yamlPath,
    kind: "scalar",
    title,
    description,
    required: args.required,
    present,
    schemaNode: info,
    actions: {
      setScalar: actions.setScalar,
      deletePath: actions.deletePath
    },
    children: [],
    scalar: { value: scalarValue, type: scalarType }
  };
};

export const buildBlocks = (args: {
  rootSchema: JsonSchemaNode;
  schemaNode: JsonSchemaNode;
  yamlPath?: YamlPath;
  yamlData: any;
  yamlLocations?: YamlLocationIndex;
  overrides?: OverrideRegistry;
}): EditableBlock[] => {
  const yamlPath = args.yamlPath || [];
  const expandedNodes = expandAllOf(args.rootSchema, args.schemaNode);
  const required = schemaRequiredKeys(expandedNodes);
  const props = schemaProperties(expandedNodes);
  const keys = Object.keys(props);

  const requiredKeys: string[] = [];
  const optionalKeys: string[] = [];
  for (const k of keys) {
    if (required.has(k)) requiredKeys.push(k);
    else optionalKeys.push(k);
  }
  requiredKeys.sort();
  optionalKeys.sort();

  const ordered = requiredKeys.concat(optionalKeys);
  const blocks: EditableBlock[] = [];

  for (const key of ordered) {
    const propSchema = props[key];
    const childPath = yamlPath.concat([key]);
    blocks.push(
      buildBlockForNode({
        rootSchema: args.rootSchema,
        rawSchemaNode: propSchema,
        yamlPath: childPath,
        yamlData: args.yamlData,
        yamlLocations: args.yamlLocations,
        overrides: args.overrides,
        required: required.has(key),
        titleFallback: key
      })
    );
  }

  return blocks;
};
