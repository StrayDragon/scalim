import type { YamlLocationIndex } from "../../services/yaml_doc.ts";
import type { BlockActions, EditableBlock, JsonSchemaNode, SchemaNodeInfo, YamlPath } from "./types.ts";

export type OverrideMatchKind = "exact" | "glob";

export type OverrideBuildContext = {
  rootSchema: JsonSchemaNode;
  schemaNode: JsonSchemaNode;
  schemaNodeInfo: SchemaNodeInfo;
  yamlPath: YamlPath;
  yamlData: any;
  yamlLocations?: YamlLocationIndex;
  required: boolean | null;
  present: boolean;
  actions: BlockActions;
  buildChildren: () => EditableBlock[];
};

export type SchemaBlocksOverride = {
  id: string;
  matchKind: OverrideMatchKind;
  pattern: string;
  priority: number;
  build: (ctx: OverrideBuildContext) => EditableBlock;
};

const splitPattern = (pattern: string): string[] => {
  return String(pattern || "")
    .split(".")
    .map((p) => p.trim())
    .filter(Boolean);
};

const globSpecificity = (pattern: string): number => {
  const parts = splitPattern(pattern);
  let score = 0;
  for (const p of parts) {
    if (p !== "*") score += 1;
  }
  return score;
};

const globMatch = (pattern: string, yamlPath: YamlPath): boolean => {
  const pat = splitPattern(pattern);
  if (pat.length !== yamlPath.length) return false;
  for (let i = 0; i < pat.length; i += 1) {
    const seg = pat[i] as string;
    if (seg === "*") continue;
    if (seg !== yamlPath[i]) return false;
  }
  return true;
};

export class OverrideRegistry {
  private overrides: SchemaBlocksOverride[] = [];

  registerExact(path: YamlPath, override: Omit<SchemaBlocksOverride, "matchKind" | "pattern"> & { id: string }): void {
    const pattern = path.join(".");
    this.overrides.push({ ...override, matchKind: "exact", pattern });
  }

  registerGlob(pattern: string, override: Omit<SchemaBlocksOverride, "matchKind" | "pattern"> & { id: string }): void {
    const cleaned = String(pattern || "").trim();
    if (!cleaned) return;
    this.overrides.push({ ...override, matchKind: "glob", pattern: cleaned });
  }

  match(yamlPath: YamlPath): SchemaBlocksOverride | null {
    const key = yamlPath.join(".");

    const exactMatches = this.overrides.filter((o) => o.matchKind === "exact" && o.pattern === key);
    if (exactMatches.length) {
      exactMatches.sort((a, b) => {
        if (a.priority !== b.priority) return b.priority - a.priority;
        return this.overrides.indexOf(b) - this.overrides.indexOf(a);
      });
      return exactMatches[0] || null;
    }

    const globMatches = this.overrides.filter((o) => o.matchKind === "glob" && globMatch(o.pattern, yamlPath));
    if (!globMatches.length) return null;

    globMatches.sort((a, b) => {
      if (a.priority !== b.priority) return b.priority - a.priority;
      const sa = globSpecificity(a.pattern);
      const sb = globSpecificity(b.pattern);
      if (sa !== sb) return sb - sa;
      return this.overrides.indexOf(b) - this.overrides.indexOf(a);
    });
    return globMatches[0] || null;
  }
}
