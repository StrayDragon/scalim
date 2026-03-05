import type { Issue } from "$domain/issues";
import type { OutlineTarget, YamlLocationIndex } from "$services/yaml_doc";
import type { PatchDecision } from "$services/yaml_patch";

export const state = $state({
  yamlText: "",
  splitRatio: 0.55,
  strict: false,
  schemaHeaderPath: "../schema/demand.gen.json",
  schemaLoaded: false,
  schemaLoadError: "",

  semanticMode: "local" as "local" | "pyodide",
  pyodideStatus: "disabled" as "disabled" | "loading" | "ok" | "error",
  pyodideLastError: "",

  schemaIssues: [] as Issue[],
  unknownFieldIssues: [] as Issue[],
  semanticIssues: [] as Issue[],

  yamlLocations: {} as YamlLocationIndex,

  undoStack: [] as string[],
  pendingPatch: null as null | {
    title: string;
    planKind: "safe" | "rewrite";
    planReason?: string;
    beforeText: string;
    afterText: string;
  },
  pendingDecision: null as null | {
    title: string;
    beforeText: string;
    decision: PatchDecision;
  },

  outlineTargets: [] as OutlineTarget[],

  activePath: null as null | string,

  editorApi: null as null | {
    reveal: (line: number, column?: number) => void;
    focus: () => void;
  },
  pendingReveal: null as null | { line: number; column: number }
});

export const revealInYaml = (line: number, column?: number) => {
  const col = column || 1;
  state.pendingReveal = { line, column: col };
  state.editorApi?.reveal(line, col);
  state.editorApi?.focus();
};

export const allIssues = () => {
  return [...state.schemaIssues, ...state.unknownFieldIssues, ...state.semanticIssues];
};

export const issueCounts = () => {
  const issues = allIssues();
  let errors = 0;
  let warnings = 0;
  for (const issue of issues) {
    if (issue.severity === "error") errors += 1;
    else warnings += 1;
  }
  return { errors, warnings };
};
