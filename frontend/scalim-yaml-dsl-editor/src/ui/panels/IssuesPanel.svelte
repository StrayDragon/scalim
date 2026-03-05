<script lang="ts">
  import Badge from "$components/ui/badge.svelte";
  import Button from "$components/ui/button.svelte";
  import { allIssues, revealInYaml, state as appState } from "$domain/state.svelte";
  import type { Issue } from "$domain/issues";
  import { lookupYamlLocation } from "$services/yaml_doc";

  let filter = $state<"all" | "error" | "warning">("all");
  let source = $state<"all" | "schema" | "unknown_fields" | "semantic">("all");
  let query = $state<string>("");

  const filtered = $derived(() => {
    const q = query.trim().toLowerCase();
    return allIssues().filter((issue) => {
      if (filter !== "all" && issue.severity !== filter) return false;
      if (source !== "all" && issue.source !== source) return false;
      if (!q) return true;
      const text = (issue.message + " " + (issue.path || "")).toLowerCase();
      return text.includes(q);
    });
  });

  const badgeFor = (issue: Issue) => {
    if (issue.severity === "error") return "destructive";
    return issue.source === "semantic" ? "warning" : "outline";
  };

  const onJump = (issue: Issue) => {
    const loc = lookupYamlLocation(issue.path, appState.yamlLocations);
    const line = issue.line || loc?.line;
    const column = issue.column || loc?.column || 1;
    if (!line) return;
    revealInYaml(line, column);
  };
</script>

<div class="flex h-full flex-col">
  <div class="border-b bg-slate-50 px-3 py-2 text-xs">
    <div class="flex items-center justify-between">
      <div class="font-semibold text-slate-800">Issues</div>
      <div class="text-[11px] text-slate-500">{filtered().length}</div>
    </div>
    <div class="mt-2 flex items-center gap-2">
      <select
        class="sx-select"
        name="issues_severity"
        bind:value={filter}
        aria-label="severity filter"
      >
        <option value="all">all</option>
        <option value="error">error</option>
        <option value="warning">warning</option>
      </select>
      <select
        class="sx-select"
        name="issues_source"
        bind:value={source}
        aria-label="source filter"
      >
        <option value="all">all sources</option>
        <option value="schema">schema</option>
        <option value="unknown_fields">unknown</option>
        <option value="semantic">semantic</option>
      </select>
      <input
        class="sx-input-sm flex-1 text-slate-700"
        name="issues_query"
        placeholder="search message/path"
        bind:value={query}
      />
    </div>
  </div>

  <div class="min-h-0 flex-1 overflow-auto p-2">
    {#if filtered().length === 0}
      <div class="px-2 py-3 text-xs text-slate-500">暂无问题</div>
    {:else}
      <div class="flex flex-col gap-2">
        {#each filtered() as issue, idx (idx)}
          <div class="rounded-lg border bg-white px-3 py-2 text-xs">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <Badge variant={badgeFor(issue)}>{issue.severity}</Badge>
                  <Badge variant="outline">{issue.source}</Badge>
                  {#if issue.line}
                    <span class="text-[11px] text-slate-500">L{issue.line}{issue.column ? ":" + issue.column : ""}</span>
                  {/if}
                </div>
                <div class="mt-1 break-words text-slate-800">{issue.message}</div>
                {#if issue.path}
                  <div class="mt-1 font-mono text-[11px] text-slate-500">{issue.path}</div>
                {/if}
                {#if issue.suggestions && issue.suggestions.length}
                  <div class="mt-1 text-[11px] text-slate-600">suggest: {issue.suggestions.join(", ")}</div>
                {/if}
              </div>

              {#if issue.line || issue.path}
                <Button variant="outline" size="sm" on:click={() => onJump(issue)}>跳转</Button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
