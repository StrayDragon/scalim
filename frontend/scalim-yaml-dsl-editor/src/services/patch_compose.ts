import type { PatchPlan, PatchResult } from "$services/yaml_patch";

type ComposeStep = (yamlText: string) => PatchResult;

export const composePatchResults = (yamlText: string, steps: ComposeStep[]): PatchResult => {
  let text = String(yamlText || "");
  let kind: PatchPlan["kind"] = "safe";
  const reasons: string[] = [];

  for (const step of steps) {
    const out = step(text);
    if (!out.ok) return out;
    if (out.decision) return out;
    text = out.text;
    if (out.plan?.kind === "rewrite") kind = "rewrite";
    if (out.plan?.reason) reasons.push(String(out.plan.reason));
  }

  return {
    ok: true,
    text,
    plan: {
      kind,
      reason: reasons.length ? reasons.slice(0, 4).join("; ") : undefined
    }
  };
};
