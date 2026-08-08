import type { RunSource } from "$domain/types";

import { VIZ_DIR_NAME } from "../generated/project_constants";

export { VIZ_DIR_NAME };

export const readFile = async (file: File): Promise<string> => {
  return await file.text();
};

export const readFileTail = async (file: File, maxBytes: number): Promise<string> => {
  const size = file.size ?? 0;
  if (!Number.isFinite(maxBytes) || maxBytes <= 0) {
    return "";
  }
  if (size <= maxBytes) {
    return await file.text();
  }
  const start = Math.max(0, size - maxBytes);
  const text = await file.slice(start).text();
  if (start <= 0) {
    return text;
  }
  const firstNewline = text.indexOf("\n");
  if (firstNewline < 0) {
    return "";
  }
  return text.slice(firstNewline + 1);
};

export const buildRunsFromFiles = (files: File[]) => {
  const runs = new Map<string, RunSource>();
  let rootLabel = "";

  for (const file of files) {
    const rel = (file as any).webkitRelativePath || file.name;
    const parts = String(rel).split("/").filter(Boolean);
    const filename = parts[parts.length - 1];
    if (
      filename !== "viz_snapshot.json" &&
      filename !== "viz_events.jsonl" &&
      filename !== "viz_trace.jsonl" &&
      filename !== "viz_schedule_plan.json" &&
      filename !== "run_stats.json"
    ) {
      continue;
    }

    const folderParts = parts.slice(0, -1);
    if (folderParts.length && !rootLabel) {
      rootLabel = folderParts[0];
    }

    const vizIndex = folderParts.lastIndexOf(VIZ_DIR_NAME);
    let runId = "";
    if (vizIndex >= 0) {
      if (vizIndex + 1 < folderParts.length) {
        runId = folderParts[vizIndex + 1];
      } else if (vizIndex > 0) {
        runId = folderParts[vizIndex - 1];
      } else {
        runId = folderParts[vizIndex];
      }
    } else if (folderParts.length >= 2) {
      runId = folderParts[1];
    } else if (folderParts.length === 1) {
      runId = folderParts[0];
    }

    const key = runId || "root";
    const entry = runs.get(key) || { id: key, label: key };

    if (filename === "viz_snapshot.json") {
      entry.snapshotFile = file;
    } else if (filename === "viz_events.jsonl") {
      entry.eventsFile = file;
    } else if (filename === "viz_trace.jsonl") {
      entry.traceFile = file;
    } else if (filename === "viz_schedule_plan.json") {
      entry.schedulePlanFile = file;
    } else if (filename === "run_stats.json") {
      entry.runStatsFile = file;
    }

    entry.lastModified = Math.max(entry.lastModified ?? 0, file.lastModified ?? 0);
    runs.set(key, entry);
  }

  return { directoryLabel: rootLabel || "本地目录", runs: Array.from(runs.values()) };
};

export const pickLatestRun = (sources: RunSource[]): RunSource | null => {
  if (!sources.length) return null;
  let latest = sources[0];
  for (const item of sources) {
    if ((item.lastModified ?? 0) > (latest.lastModified ?? 0)) {
      latest = item;
    }
  }
  return latest;
};
