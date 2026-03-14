import type { Issue } from "$domain/issues";
import type { YamlLocationIndex } from "$services/yaml_doc";
import { lookupYamlLocation } from "$services/yaml_doc";

const isRecord = (value: unknown): value is Record<string, any> => {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
};

const isIdentifier = (value: string): boolean => {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
};

const isValidLoaderRef = (loaderRefRaw: unknown): boolean => {
  const loaderRef = String(loaderRefRaw || "").trim();
  if (!loaderRef) return false;

  if (loaderRef.includes(":")) {
    const parts = loaderRef.split(":");
    if (parts.length !== 2) return false;
    const modulePath = (parts[0] || "").trim();
    const attrPath = (parts[1] || "").trim();
    if (!modulePath || !attrPath) return false;

    const moduleParts = modulePath.split(".").filter(Boolean);
    const attrParts = attrPath.split(".").filter(Boolean);
    if (moduleParts.length < 1 || attrParts.length < 1) return false;
    if (!moduleParts.every(isIdentifier)) return false;
    return attrParts.every(isIdentifier);
  }

  const parts = loaderRef.split(".").filter(Boolean);
  if (parts.length < 2) return false;
  return parts.every(isIdentifier);
};

const hasBindParam = (bindRaw: unknown): boolean => {
  if (!isRecord(bindRaw)) return false;
  const useRows = bindRaw.use_rows;
  const useKeys = bindRaw.use_keys;
  const rowsParam = isRecord(useRows) ? String(useRows.param || "").trim() : "";
  const keysParam = isRecord(useKeys) ? String(useKeys.param || "").trim() : "";
  return Boolean(rowsParam || keysParam);
};

const parseSourceFieldExpr = (expr: unknown): { sourceId: string; fieldId: string } | null => {
  if (typeof expr !== "string") return null;
  const raw = expr.trim();
  if (!raw) return null;
  const idx = raw.indexOf(".");
  if (idx <= 0 || idx >= raw.length - 1) return null;
  const sourceId = raw.slice(0, idx).trim();
  const fieldId = raw.slice(idx + 1).trim();
  if (!sourceId || !fieldId) return null;
  return { sourceId, fieldId };
};

const parseSourceFieldGroup = (value: unknown): { sourceId: string; fieldIds: string[] } | null => {
  if (typeof value === "string") {
    const parsed = parseSourceFieldExpr(value);
    if (!parsed) return null;
    return { sourceId: parsed.sourceId, fieldIds: [parsed.fieldId] };
  }
  if (Array.isArray(value) && value.length) {
    let sourceId = "";
    const fieldIds: string[] = [];
    for (const item of value) {
      const parsed = parseSourceFieldExpr(item);
      if (!parsed) return null;
      if (!sourceId) sourceId = parsed.sourceId;
      if (sourceId !== parsed.sourceId) return null;
      fieldIds.push(parsed.fieldId);
    }
    if (!sourceId) return null;
    return { sourceId, fieldIds };
  }
  return null;
};

export type SemanticValidateOptions = {
  strict?: boolean;
  locations?: YamlLocationIndex;
};

export const validateSemantic = (config: unknown, opts?: SemanticValidateOptions): Issue[] => {
  const issues: Issue[] = [];
  const locations = opts?.locations;

  const addIssue = (severity: "error" | "warning", message: string, path?: string, suggestions?: string[]) => {
    const loc = locations ? lookupYamlLocation(path, locations) : null;
    issues.push({
      severity,
      source: "semantic",
      message,
      path,
      suggestions,
      line: loc?.line,
      column: loc?.column
    });
  };

  if (!isRecord(config)) return issues;

  if (!Object.prototype.hasOwnProperty.call(config, "name")) addIssue("error", "Missing required field: 'name'", "name");
  if (!Object.prototype.hasOwnProperty.call(config, "main_source"))
    addIssue("error", "Missing required field: 'main_source'", "main_source");

  const mainSourceRaw = config.main_source;
  const mainSource = isRecord(mainSourceRaw) ? mainSourceRaw : null;
  const mainSourceId = mainSource && typeof mainSource.source_id === "string" ? mainSource.source_id.trim() : "";
  const mainLoader = mainSource && typeof mainSource.loader === "string" ? mainSource.loader.trim() : "";

  if (mainSourceRaw != null && !mainSource) addIssue("error", "'main_source' must be a mapping", "main_source");
  if (mainSource && !mainSourceId) addIssue("error", "Main source missing required field 'source_id'", "main_source.source_id");
  if (mainSource && !mainLoader) addIssue("error", "Main source missing required field 'loader'", "main_source.loader");
  if (mainSource && mainLoader && !isValidLoaderRef(mainLoader)) {
    addIssue(
      "error",
      "Main source has invalid loader reference '" +
        mainLoader +
        "'. Expected: 'module.path:ClassName' or 'module.path.function'.",
      "main_source.loader"
    );
  }

  const sourcesRaw = config.sources;
  const sources = isRecord(sourcesRaw) ? sourcesRaw : null;
  if (sourcesRaw != null && !sources) addIssue("error", "'sources' must be a mapping", "sources");

  if (mainSourceId && sources && Object.prototype.hasOwnProperty.call(sources, mainSourceId)) {
    addIssue("error", "Main source '" + mainSourceId + "' must not appear in 'sources'", "main_source.source_id");
  }

  const allowedFieldsBySource: Record<string, Set<string>> = {};
  if (mainSourceId) {
    const fields = mainSource && isRecord(mainSource.fields) ? mainSource.fields : null;
    allowedFieldsBySource[mainSourceId] = new Set(fields ? Object.keys(fields) : []);
  }

  const sourcesInfo: Record<string, { bind: boolean; preload: boolean }> = {};
  if (sources) {
    for (const [sourceId, sourceDataRaw] of Object.entries(sources)) {
      if (sourceId === "$import") continue;
      const basePath = "sources." + sourceId;
      if (!isRecord(sourceDataRaw)) {
        addIssue("error", "Source '" + sourceId + "' must be a mapping", basePath);
        allowedFieldsBySource[sourceId] = new Set();
        sourcesInfo[sourceId] = { bind: false, preload: false };
        continue;
      }

      const sourceData = sourceDataRaw;
      const loader = typeof sourceData.loader === "string" ? sourceData.loader.trim() : "";
      const keyPresent = Object.prototype.hasOwnProperty.call(sourceData, "key");

      if (!loader) addIssue("error", "Source '" + sourceId + "' missing required field 'loader'", basePath + ".loader");
      if (!keyPresent) addIssue("error", "Source '" + sourceId + "' missing required field 'key'", basePath + ".key");
      if (loader && !isValidLoaderRef(loader)) {
        addIssue(
          "error",
          "Source '" + sourceId + "' has invalid loader reference '" + loader + "'. Expected: 'module.path:ClassName' or 'module.path.function'.",
          basePath + ".loader"
        );
      }

      const declaredFields = isRecord(sourceData.fields) ? Object.keys(sourceData.fields) : [];
      const keyFields: string[] = [];
      if (Array.isArray(sourceData.key)) {
        for (const item of sourceData.key) {
          const v = String(item || "").trim();
          if (v) keyFields.push(v);
        }
      } else if (typeof sourceData.key === "string") {
        const v = sourceData.key.trim();
        if (v) keyFields.push(v);
      }

      const allowed = new Set<string>();
      for (const f of declaredFields) allowed.add(f);
      for (const f of keyFields) allowed.add(f);
      allowedFieldsBySource[sourceId] = allowed;

      const cacheMode = String(sourceData.cache_mode || "").trim();
      const preload = cacheMode === "preload_forever";
      const bind = hasBindParam(sourceData.bind);
      sourcesInfo[sourceId] = { bind, preload };
    }
  }

  if (mainSource && Array.isArray(mainSource.order_by)) {
    const mainFields = allowedFieldsBySource[mainSourceId] || new Set<string>();
    for (let idx = 0; idx < mainSource.order_by.length; idx += 1) {
      const item = mainSource.order_by[idx];
      const path = "main_source.order_by." + String(idx);
      if (typeof item !== "string") {
        addIssue("error", path + " must be a string", path);
        continue;
      }
      const raw = item.trim();
      if (!raw || raw === "-") {
        addIssue("error", path + " must be a non-empty string", path);
        continue;
      }
      const fieldId = raw.startsWith("-") ? raw.slice(1) : raw;
      if (fieldId && !mainFields.has(fieldId)) {
        addIssue("error", "main_source.order_by field '" + fieldId + "' not found in main_source.fields", path);
      }
    }
  }

  const relationsRaw = config.relations;
  const relations = isRecord(relationsRaw) ? relationsRaw : null;
  if (relationsRaw != null && !relations) addIssue("error", "'relations' must be a mapping", "relations");

  const sourcesSet = new Set<string>(Object.keys(sourcesInfo));
  if (mainSourceId) sourcesSet.add(mainSourceId);

  if (relations) {
    for (const [relId, relDataRaw] of Object.entries(relations)) {
      if (relId === "$import") continue;
      const basePath = "relations." + relId;
      if (!isRecord(relDataRaw)) {
        addIssue("error", "Relation '" + relId + "' must be a mapping", basePath);
        continue;
      }

      const relData = relDataRaw;
      const stepsRaw = relData.steps;
      if (!Array.isArray(stepsRaw)) {
        addIssue("error", basePath + " steps must be a list", basePath + ".steps");
        continue;
      }
      if (!stepsRaw.length) {
        addIssue("error", basePath + " steps must not be empty", basePath + ".steps");
        continue;
      }

      let prevTo: string | null = null;
      for (let idx = 0; idx < stepsRaw.length; idx += 1) {
        const stepPath = basePath + ".steps." + String(idx);
        const stepRaw = stepsRaw[idx];
        if (!isRecord(stepRaw)) {
          addIssue("error", basePath + " steps[" + String(idx) + "] must be a mapping", stepPath);
          continue;
        }

        if (!Object.prototype.hasOwnProperty.call(stepRaw, "from") || !Object.prototype.hasOwnProperty.call(stepRaw, "to")) {
          addIssue("error", basePath + " steps[" + String(idx) + "] missing 'from' or 'to'", stepPath);
          continue;
        }

        const fromInfo = parseSourceFieldGroup(stepRaw.from);
        const toInfo = parseSourceFieldGroup(stepRaw.to);
        if (!fromInfo || !toInfo) {
          addIssue("error", basePath + " steps[" + String(idx) + "] from/to must be 'source.field' or list", stepPath);
          continue;
        }

        const fromSource = fromInfo.sourceId;
        const toSource = toInfo.sourceId;

        if (!sourcesSet.has(fromSource)) addIssue("error", basePath + " steps[" + String(idx) + "] references unknown source '" + fromSource + "'", stepPath);
        if (!sourcesSet.has(toSource)) addIssue("error", basePath + " steps[" + String(idx) + "] references unknown source '" + toSource + "'", stepPath);

        const fromAllowed = allowedFieldsBySource[fromSource];
        if (fromAllowed) {
          for (const f of fromInfo.fieldIds) {
            if (!fromAllowed.has(f)) {
              addIssue(
                "error",
                basePath +
                  " steps[" +
                  String(idx) +
                  "] references unknown field '" +
                  fromSource +
                  "." +
                  f +
                  "'; relation steps must use field_id (YAML key), not loader data_key",
                stepPath + ".from"
              );
            }
          }
        }

        const toAllowed = allowedFieldsBySource[toSource];
        if (toAllowed) {
          for (const f of toInfo.fieldIds) {
            if (!toAllowed.has(f)) {
              addIssue(
                "error",
                basePath +
                  " steps[" +
                  String(idx) +
                  "] references unknown field '" +
                  toSource +
                  "." +
                  f +
                  "'; relation steps must use field_id (YAML key), not loader data_key",
                stepPath + ".to"
              );
            }
          }
        }

        if (fromInfo.fieldIds.length !== toInfo.fieldIds.length) {
          addIssue("error", basePath + " steps[" + String(idx) + "] from/to field length mismatch", stepPath);
        }

        if (prevTo && fromSource !== prevTo) {
          addIssue("error", basePath + " steps[" + String(idx) + "] breaks chain: expected from source '" + prevTo + "'", stepPath);
        }

        prevTo = toSource;

        const toBindPresent = hasBindParam(stepRaw.to_bind);
        const toSourceInfo = sourcesInfo[toSource];
        if (toSourceInfo && !toSourceInfo.preload && !(toBindPresent || toSourceInfo.bind)) {
          addIssue("error", "Relation '" + relId + "' step to '" + toSource + "' requires to_bind or sources." + toSource + ".bind", basePath + ".steps");
        }
      }
    }
  }

  // Placeholder strict hook for future semantic checks parity.
  void opts?.strict;

  return issues;
};
