<script lang="ts">
  import { onMount, tick } from "svelte";
  import Button from "$components/ui/button.svelte";
  import Badge from "$components/ui/badge.svelte";
  import { state as appState, issueCounts } from "$domain/state.svelte";
  import { MINIMAL_TEMPLATE } from "$services/templates";
  import { downloadText, readTextFile } from "$services/files";
  import { undoLast } from "$services/patch_apply";

  let schemaConfigOpen = $state(false);
  let schemaPathDraft = $state("");
  let semanticConfigOpen = $state(false);
  let pyodideEnabledDraft = $state(false);
  let fileInput = $state(null as HTMLInputElement | null);
  let schemaConfigButton = $state(null as HTMLButtonElement | null);
  let schemaConfigPanel = $state(null as HTMLDivElement | null);
  let schemaPathInput = $state(null as HTMLInputElement | null);
  let semanticConfigButton = $state(null as HTMLDivElement | null);
  let semanticConfigPanel = $state(null as HTMLDivElement | null);

  const counts = $derived(() => issueCounts());
  const canUndo = $derived(() => appState.undoStack.length > 0);

  const SCHEMA_PATH_STORAGE_KEY = "scalim_yaml_dsl_editor_schema_header_path";
  const DEFAULT_SCHEMA_PATH = "../schema/demand.gen.json";
  const WORKFLOW_SCHEMA_PATH = "../schema/workflow.gen.json";

  const SEMANTIC_MODE_STORAGE_KEY = "scalim_yaml_dsl_editor_semantic_mode";

  const onNewMinimal = () => {
    appState.schemaHeaderPath = DEFAULT_SCHEMA_PATH;
    persistSchemaPath();
    appState.yamlText = MINIMAL_TEMPLATE;
  };

  const onLoadOrderReport = async () => {
    const isWorkflow = String(appState.schemaHeaderPath || "").toLowerCase().includes("workflow.gen.json");
    const url = isWorkflow ? "/examples/workflow_minimal.yaml" : "/examples/order_report.yaml";
    appState.schemaHeaderPath = isWorkflow ? WORKFLOW_SCHEMA_PATH : DEFAULT_SCHEMA_PATH;
    persistSchemaPath();
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) return;
    appState.yamlText = await res.text();
    ensureSchemaHeader();
  };

  const onLoadSnippets = async () => {
    appState.schemaHeaderPath = DEFAULT_SCHEMA_PATH;
    persistSchemaPath();
    const res = await fetch("/examples/imports_normalize.yaml", { cache: "no-cache" });
    if (!res.ok) return;
    appState.yamlText = await res.text();
    ensureSchemaHeader();
  };

  const ensureSchemaHeader = () => {
    const rawPath = (appState.schemaHeaderPath || DEFAULT_SCHEMA_PATH).trim();
    const path = rawPath || DEFAULT_SCHEMA_PATH;
    const header = "# yaml-language-server: $schema=" + path;
    const lines = appState.yamlText.split(/\r?\n/);
    for (let i = 0; i < Math.min(lines.length, 10); i += 1) {
      if (lines[i].startsWith("# yaml-language-server:")) {
        if (lines[i] !== header) {
          lines[i] = header;
          appState.yamlText = lines.join("\n");
        }
        return;
      }
      if (lines[i].trim() && !lines[i].startsWith("#")) break;
    }
    appState.yamlText = header + "\n\n" + appState.yamlText.replace(/^\s+/, "");
  };

  const loadSchemaPath = () => {
    try {
      const raw = window.localStorage.getItem(SCHEMA_PATH_STORAGE_KEY);
      if (!raw) return;
      appState.schemaHeaderPath = raw;
    } catch {
      // ignore
    }
  };

  const persistSchemaPath = () => {
    try {
      window.localStorage.setItem(SCHEMA_PATH_STORAGE_KEY, appState.schemaHeaderPath);
    } catch {
      // ignore
    }
  };

  const loadSemanticMode = () => {
    try {
      const raw = window.localStorage.getItem(SEMANTIC_MODE_STORAGE_KEY);
      if (raw === "pyodide" || raw === "local") appState.semanticMode = raw;
    } catch {
      // ignore
    }
  };

  const persistSemanticMode = () => {
    try {
      window.localStorage.setItem(SEMANTIC_MODE_STORAGE_KEY, appState.semanticMode);
    } catch {
      // ignore
    }
  };

  const openSchemaConfig = async () => {
    schemaPathDraft = appState.schemaHeaderPath || DEFAULT_SCHEMA_PATH;
    schemaConfigOpen = true;
    await tick();
    schemaPathInput?.focus();
    schemaPathInput?.select();
  };

  const closeSchemaConfig = () => {
    schemaConfigOpen = false;
  };

  const saveSchemaPath = () => {
    const next = schemaPathDraft.trim() || DEFAULT_SCHEMA_PATH;
    appState.schemaHeaderPath = next;
    persistSchemaPath();
    ensureSchemaHeader();
    closeSchemaConfig();
  };

  const resetSchemaPath = () => {
    schemaPathDraft = DEFAULT_SCHEMA_PATH;
  };

  const openSemanticConfig = async () => {
    pyodideEnabledDraft = appState.semanticMode === "pyodide";
    semanticConfigOpen = true;
    await tick();
  };

  const closeSemanticConfig = () => {
    semanticConfigOpen = false;
  };

  const saveSemanticMode = () => {
    appState.semanticMode = pyodideEnabledDraft ? "pyodide" : "local";
    if (appState.semanticMode === "local") {
      appState.pyodideStatus = "disabled";
      appState.pyodideLastError = "";
    }
    persistSemanticMode();
    closeSemanticConfig();
  };

  const onPickFile = () => {
    fileInput?.click();
  };

  const onFileChange = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    appState.yamlText = await readTextFile(file);
    input.value = "";
  };

  const onSave = () => {
    const isWorkflow = String(appState.schemaHeaderPath || "").toLowerCase().includes("workflow.gen.json");
    downloadText(isWorkflow ? "workflow.yaml" : "demand.yaml", appState.yamlText, "text/yaml;charset=utf-8");
  };

  const onCopy = async () => {
    await navigator.clipboard.writeText(appState.yamlText);
  };

  onMount(() => {
    loadSchemaPath();
    loadSemanticMode();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (schemaConfigOpen) closeSchemaConfig();
      if (semanticConfigOpen) closeSemanticConfig();
    };

    const onPointerDown = (event: PointerEvent) => {
      if (!schemaConfigOpen && !semanticConfigOpen) return;
      const target = event.target as Node | null;
      if (!target) return;
      if (schemaConfigOpen) {
        if (schemaConfigPanel && schemaConfigPanel.contains(target)) return;
        if (schemaConfigButton && schemaConfigButton.contains(target)) return;
      }
      if (semanticConfigOpen) {
        if (semanticConfigPanel && semanticConfigPanel.contains(target)) return;
        if (semanticConfigButton && semanticConfigButton.contains(target)) return;
      }

      if (schemaConfigOpen) closeSchemaConfig();
      if (semanticConfigOpen) closeSemanticConfig();
    };

    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown, true);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown, true);
    };
  });
</script>

<div class="flex items-center justify-between gap-3 border-b bg-white px-3 py-2">
  <div class="flex items-center gap-2">
    <div class="text-sm font-semibold text-slate-800">Scalim YAML DSL Editor</div>
    {#if counts().errors > 0}
      <Badge variant="destructive">{counts().errors} errors</Badge>
    {:else}
      <Badge variant="success">0 errors</Badge>
    {/if}
    {#if counts().warnings > 0}
      <Badge variant="warning">{counts().warnings} warnings</Badge>
    {/if}
  </div>

  <div class="flex items-center gap-2">
    <Button variant="secondary" on:click={onNewMinimal}>新建最小模板</Button>
    <Button variant="secondary" on:click={onLoadOrderReport}>载入示例</Button>
    <Button variant="secondary" on:click={onLoadSnippets}>载入片段</Button>
    <div class="relative inline-flex items-center gap-1">
      <Button
        variant="outline"
        on:click={ensureSchemaHeader}
        title={"插入/更新: # yaml-language-server: $schema=" + (appState.schemaHeaderPath || DEFAULT_SCHEMA_PATH)}
      >
        插入 $schema
      </Button>
      <button
        bind:this={schemaConfigButton}
        type="button"
        class="inline-flex h-8 w-8 items-center justify-center rounded-md border border-input bg-background text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ring-offset-background"
        onclick={openSchemaConfig}
        aria-label="configure $schema path"
        title="配置 $schema 路径"
      >
        ⋯
      </button>

      {#if schemaConfigOpen}
        <div
          bind:this={schemaConfigPanel}
          class="absolute right-0 top-full z-[9000] mt-2 w-[380px] max-w-[90vw] rounded-xl border bg-white p-3 text-xs shadow-lg"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[11px] font-semibold text-slate-700">$schema 路径</div>
              <div class="mt-1 text-[11px] text-slate-500">用于导出的 YAML(VS Code / yaml-language-server)</div>
            </div>
            <Button variant="ghost" size="sm" on:click={closeSchemaConfig}>关闭</Button>
          </div>

          <div class="mt-2">
            <input
              bind:this={schemaPathInput}
              class="sx-input-sm w-full text-slate-700"
              name="schema_path"
              placeholder="../schema/demand.gen.json 或 https://..."
              bind:value={schemaPathDraft}
              onkeydown={(e) => {
                if ((e as KeyboardEvent).key === "Enter") saveSchemaPath();
              }}
            />
            <div class="mt-2 rounded-lg border bg-slate-50 px-2 py-1 font-mono text-[10px] text-slate-600">
              # yaml-language-server: $schema={schemaPathDraft.trim() || DEFAULT_SCHEMA_PATH}
            </div>
          </div>

          <div class="mt-2 flex items-center gap-2">
            <Button variant="outline" size="sm" on:click={() => (schemaPathDraft = DEFAULT_SCHEMA_PATH)}>demand</Button>
            <Button variant="outline" size="sm" on:click={() => (schemaPathDraft = WORKFLOW_SCHEMA_PATH)}>workflow</Button>
            <div class="text-[11px] text-slate-500">保存后会同步更新 YAML 头部</div>
          </div>

          <div class="mt-3 flex items-center justify-between gap-2">
            <Button variant="outline" size="sm" on:click={resetSchemaPath}>默认</Button>
            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" on:click={closeSchemaConfig}>取消</Button>
              <Button variant="secondary" size="sm" on:click={saveSchemaPath}>保存</Button>
            </div>
          </div>
        </div>
      {/if}
    </div>
    <Button variant="outline" on:click={onPickFile}>导入 YAML</Button>
    <Button variant="outline" on:click={onSave}>导出</Button>
    <Button variant="outline" on:click={onCopy}>复制</Button>

      <Button variant="outline" disabled={!canUndo()} on:click={undoLast} title="撤销上一次结构化修改(Undo)">
        撤销
      </Button>

	      <div class="relative inline-flex items-center gap-1" bind:this={semanticConfigButton}>
	        <Button
	          variant={
	            appState.semanticMode === "pyodide"
	              ? appState.pyodideStatus === "ok"
	                ? "secondary"
	                : "outline"
	              : "outline"
	          }
	          on:click={openSemanticConfig}
	          title="配置语义校验(local vs exact: pyodide)"
	        >
	          semantic: {appState.semanticMode === "pyodide" ? "exact" : "local"}
	        </Button>
	        {#if semanticConfigOpen}
	          <div
	            bind:this={semanticConfigPanel}
	            class="absolute right-0 top-full z-[9000] mt-2 w-[420px] max-w-[90vw] rounded-xl border bg-white p-3 text-xs shadow-lg"
	          >
	            <div class="flex items-start justify-between gap-3">
	              <div class="min-w-0">
	                <div class="text-[11px] font-semibold text-slate-700">精确语义校验(Pyodide,可选)</div>
	                <div class="mt-1 text-[11px] text-slate-500">在浏览器内运行 `scalim` 校验逻辑,对齐 `scalim-cli yaml-dsl validate`.</div>
	              </div>
	              <Button variant="ghost" size="sm" on:click={closeSemanticConfig}>关闭</Button>
	            </div>
	
	            <div class="mt-3 grid grid-cols-12 gap-2">
	              <label class="col-span-12 flex items-center gap-2 text-[11px] text-slate-600">
	                <input
	                  type="checkbox"
	                  class="h-4 w-4"
	                  checked={pyodideEnabledDraft}
	                  onchange={(e) => (pyodideEnabledDraft = (e.target as HTMLInputElement).checked)}
	                />
	                启用 exact(启用后 semantic 优先走 pyodide;失败自动降级到内置规则)
	              </label>
	
	              <div class="col-span-12">
	                <div class="text-[11px] text-slate-500">
	                  status: {appState.pyodideStatus}
	                  {#if appState.pyodideLastError}
	                    <span class="text-red-600"> · {appState.pyodideLastError}</span>
	                  {/if}
	                </div>
	                <div class="mt-1 text-[11px] text-slate-500">
	                  需要静态资源:`/pyodide/*` 以及 `/wheels/scalim-*.whl`(见 README).
	                </div>
	              </div>
	
	              <div class="col-span-12 flex items-center justify-end gap-2">
	                <Button variant="secondary" size="sm" on:click={saveSemanticMode}>保存</Button>
	              </div>
	            </div>
	          </div>
	        {/if}
	      </div>

      <Button variant={appState.strict ? "default" : "outline"} on:click={() => (appState.strict = !appState.strict)}>
        strict: {appState.strict ? "on" : "off"}
      </Button>
    </div>

  <input
    class="hidden"
    type="file"
    accept=".yaml,.yml"
    name="yaml_file"
    aria-label="Import YAML file"
    bind:this={fileInput}
    onchange={onFileChange}
  />
</div>
