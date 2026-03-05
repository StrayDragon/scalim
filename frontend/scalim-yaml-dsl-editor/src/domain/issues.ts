export type IssueSeverity = "error" | "warning";

export type IssueSource = "schema" | "unknown_fields" | "semantic";

export type Issue = {
  severity: IssueSeverity;
  message: string;
  path?: string;
  line?: number;
  column?: number;
  suggestions?: string[];
  source: IssueSource;
};

