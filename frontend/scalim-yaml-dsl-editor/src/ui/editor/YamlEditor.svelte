<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import type { editor } from "monaco-editor";
  import type * as Monaco from "monaco-editor";
  import { configureMonacoYaml, type MonacoYaml } from "monaco-yaml";
  import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
  import YamlWorker from "./yaml_lsp.worker?worker";
  import { parse as parseYaml } from "yaml";
  import { state } from "$domain/state.svelte";
  import type { Issue } from "$domain/issues";
  import { loadDemandSchema, loadWorkflowSchema } from "$services/schema";
  import { pyodideValidate } from "$services/pyodide_client";
  import { validateSemantic } from "$services/semantic_validate";
  import { findUnknownFields } from "$services/unknown_fields";
  import { getYamlLocationExact, indexYamlText } from "$services/yaml_doc";

  let container: HTMLDivElement | null = null;
  let monaco: typeof Monaco | null = null;
  let editorInstance: editor.IStandaloneCodeEditor | null = null;
  let model: editor.ITextModel | null = null;
  let debounceTimerDerived: number | null = null;
  let debounceTimerMarkers: number | null = null;
  let demandSchema: any | null = null;
  let workflowSchema: any | null = null;
  let yamlLsp: MonacoYaml | null = null;
  let applyingExternalText = false;
  let semanticRunId = 0;

  const schemaKind = (): "demand" | "workflow" => {
    const raw = String(state.schemaHeaderPath || "").toLowerCase();
    return raw.includes("workflow.gen.json") ? "workflow" : "demand";
  };

  const activeSchema = () => {
    return schemaKind() === "workflow" ? workflowSchema : demandSchema;
  };

  const ensureDebounceDerived = (fn: () => void, ms: number) => {
    if (debounceTimerDerived) window.clearTimeout(debounceTimerDerived);
    debounceTimerDerived = window.setTimeout(fn, ms);
  };

  const ensureDebounceMarkers = (fn: () => void, ms: number) => {
    if (debounceTimerMarkers) window.clearTimeout(debounceTimerMarkers);
    debounceTimerMarkers = window.setTimeout(fn, ms);
  };

  const mapMarkerSeverity = (sev: number): "error" | "warning" => {
    const M = (monaco as any)?.MarkerSeverity;
    if (M && sev === M.Error) return "error";
    return "warning";
  };

  const syncSchemaMarkers = () => {
    if (!monaco || !model) return;
    const markers = monaco.editor.getModelMarkers({ resource: model.uri });
    const issues: Issue[] = markers.map((m) => ({
      severity: mapMarkerSeverity(m.severity),
      source: "schema",
      message: m.message,
      line: m.startLineNumber,
      column: m.startColumn
    }));
    state.schemaIssues = issues;
  };

  const syncUnknownFields = async () => {
    const schema = activeSchema();
    if (!state.schemaLoaded || !schema) return;
    let raw: unknown;
    try {
      raw = parseYaml(state.yamlText);
    } catch {
      state.unknownFieldIssues = [];
      return;
    }
    if (!raw || typeof raw !== "object") {
      state.unknownFieldIssues = [];
      return;
    }
    try {
      const unknowns = findUnknownFields(raw, schema);
      const issues: Issue[] = unknowns.map((u) => ({
        severity: state.strict ? "error" : "warning",
        source: "unknown_fields",
        message: "Unknown field '" + u.field + "'",
        path: u.path,
        suggestions: u.suggestions,
        line: getYamlLocationExact(u.path, state.yamlLocations)?.line,
        column: getYamlLocationExact(u.path, state.yamlLocations)?.column
      }));
      state.unknownFieldIssues = issues;
    } catch {
      state.unknownFieldIssues = [];
    }
  };

  const syncSemanticIssues = async () => {
    const runId = ++semanticRunId;

    if (state.semanticMode === "pyodide") {
      state.pyodideStatus = "loading";
      const out = await pyodideValidate(state.yamlText, {
        strict: state.strict,
        timeoutMs: 30000,
        schemaPath: state.schemaHeaderPath
      });
      if (runId !== semanticRunId) return;
      if (out.ok) {
        state.pyodideStatus = "ok";
        state.pyodideLastError = "";
        state.semanticIssues = out.issues;
        return;
      }
      state.pyodideStatus = "error";
      state.pyodideLastError = out.error;
      // degrade gracefully to built-in semantic checks
    } else {
      state.pyodideStatus = "disabled";
      state.pyodideLastError = "";
    }

    if (schemaKind() === "workflow") {
      state.semanticIssues = [];
      return;
    }

    let raw: unknown;
    try {
      raw = parseYaml(state.yamlText);
    } catch {
      state.semanticIssues = [];
      return;
    }
    if (!raw || typeof raw !== "object") {
      state.semanticIssues = [];
      return;
    }
    try {
      state.semanticIssues = validateSemantic(raw, { strict: state.strict, locations: state.yamlLocations });
    } catch {
      state.semanticIssues = [];
    }
  };

  const bindEditorApi = () => {
    state.editorApi = {
      reveal: (line: number, column?: number) => {
        if (!editorInstance) return;
        editorInstance.revealLineInCenter(line);
        editorInstance.setPosition({ lineNumber: line, column: column || 1 });
      },
      focus: () => editorInstance?.focus()
    };
  };

  const syncYamlIndex = () => {
    const out = indexYamlText(state.yamlText);
    state.yamlLocations = out.locations;
    state.outlineTargets = out.outline;
  };

  onMount(async () => {
    if (!container) return;

    (self as any).MonacoEnvironment = {
      getWorker(_moduleId: string, label: string) {
        if (label === "yaml") return new (YamlWorker as any)();
        return new (EditorWorker as any)();
      }
    };

    monaco = await import("monaco-editor");
    // monaco-yaml@5.x expects the legacy `monaco.editor.createWebWorker({ moduleId, label, createData })` API.
    // monaco-editor@0.55+ exposes that legacy helper as a *top-level* export `createWebWorker`, while
    // `monaco.editor.createWebWorker` now expects `{ worker: Worker }`.
    //
    // Shim for compatibility so hover/completion/validation work.
    try {
      const m = monaco as any;
      const legacyCreateWebWorker = m?.createWebWorker;
      const modernCreateWebWorker = m?.editor?.createWebWorker;
      if (typeof legacyCreateWebWorker === "function" && typeof modernCreateWebWorker === "function") {
        m.editor.createWebWorker = (opts: any) => {
          // Modern signature: `{ worker: Worker | Promise<Worker>, host?, keepIdleModels? }`
          if (opts && typeof opts === "object" && "worker" in opts) return modernCreateWebWorker(opts);
          return legacyCreateWebWorker(opts);
        };
      }
    } catch {
      // best-effort shim; schema/patching still works without LSP features.
    }

    const docUri = (() => {
      try {
        const origin = window.location.origin;
        if (origin && origin !== "null") return origin.replace(/\/+$/, "") + "/demand.yaml";
      } catch {
        // ignore
      }
      return "file:///demand.yaml";
    })();

    try {
      demandSchema = await loadDemandSchema();
      workflowSchema = await loadWorkflowSchema();
      yamlLsp = configureMonacoYaml(monaco as any, {
        validate: true,
        // Enable schema requests so the yaml-language-server `$schema` header works.
        // Our YAML worker intercepts same-origin requests for the bundled demand schema to avoid noisy 404/fetch failures.
        enableSchemaRequest: true,
        format: true,
        hover: true,
        completion: true,
        schemas: []
      });
      state.schemaLoaded = true;
      state.schemaLoadError = "";
    } catch (err: any) {
      demandSchema = null;
      workflowSchema = null;
      yamlLsp?.dispose?.();
      yamlLsp = null;
      state.schemaLoaded = false;
      state.schemaLoadError = String(err?.message || err || "schema load failed");
    }

    if (!state.yamlText) {
      const res = await fetch("/examples/minimal.yaml", { cache: "no-cache" });
      state.yamlText = res.ok ? await res.text() : "";
    }

    model = monaco.editor.createModel(state.yamlText, "yaml", monaco.Uri.parse(docUri));
    editorInstance = monaco.editor.create(container, {
      model,
      minimap: { enabled: false },
      automaticLayout: true,
      fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      fontSize: 12,
      tabSize: 2,
      scrollBeyondLastLine: false
    });

    if (import.meta.env.DEV) {
      (window as any).__scalimYamlDslEditor = {
        monaco,
        editor: editorInstance,
        model,
        yamlLsp,
        getMarkers: () => monaco?.editor.getModelMarkers({ resource: model?.uri }),
        getYamlText: () => model?.getValue() || "",
        setYamlText: (text: string) => model?.setValue(String(text || ""))
      };
    }

    bindEditorApi();
    syncYamlIndex();

    model.onDidChangeContent(() => {
      if (applyingExternalText) return;
      state.yamlText = model?.getValue() || "";
      ensureDebounceDerived(() => {
        syncSchemaMarkers();
        syncYamlIndex();
        syncUnknownFields();
        syncSemanticIssues();
      }, 120);
    });

    (monaco.editor as any).onDidChangeMarkers(() => {
      ensureDebounceMarkers(syncSchemaMarkers, 80);
    });

    syncSchemaMarkers();
    syncYamlIndex();
    syncUnknownFields();
    syncSemanticIssues();
  });

  $effect(() => {
    const nextText = state.yamlText;
    if (!model || !editorInstance) return;
    const current = model.getValue();
    if (nextText === current) return;
    const viewState = editorInstance.saveViewState();
    const wasFocused = editorInstance.hasTextFocus();
    applyingExternalText = true;
    model.setValue(nextText);
    applyingExternalText = false;
    if (viewState) editorInstance.restoreViewState(viewState);
    if (wasFocused) editorInstance.focus();
    ensureDebounceDerived(() => {
      syncSchemaMarkers();
      syncYamlIndex();
      syncUnknownFields();
      syncSemanticIssues();
    }, 0);
  });

  $effect(() => {
    // strict toggles impact unknown-field severity; keep issues consistent even without YAML edits.
    state.strict;
    ensureDebounceDerived(() => {
      syncUnknownFields();
      syncSemanticIssues();
    }, 0);
  });

  $effect(() => {
    state.semanticMode;
    ensureDebounceDerived(() => {
      syncSemanticIssues();
    }, 0);
  });

  $effect(() => {
    const pending = state.pendingReveal;
    if (!pending) return;
    if (!state.editorApi) return;
    state.editorApi.reveal(pending.line, pending.column || 1);
    state.editorApi.focus();
    state.pendingReveal = null;
  });

  onDestroy(() => {
    if (debounceTimerDerived) window.clearTimeout(debounceTimerDerived);
    if (debounceTimerMarkers) window.clearTimeout(debounceTimerMarkers);
    yamlLsp?.dispose?.();
    editorInstance?.dispose();
    model?.dispose();
    state.editorApi = null;
    if (import.meta.env.DEV) {
      try {
        delete (window as any).__scalimYamlDslEditor;
      } catch {
        // ignore
      }
    }
  });
</script>

<div class="flex h-full flex-col">
  <div class="flex items-center justify-between border-b bg-slate-50 px-3 py-2 text-xs">
    <div class="flex items-center gap-2">
      <span class="font-semibold text-slate-800">YAML</span>
      {#if !state.schemaLoaded}
        <span class="text-red-600">schema: {state.schemaLoadError || "unavailable"}</span>
      {:else}
        <span class="text-emerald-700">schema: loaded</span>
      {/if}
    </div>
    <div class="text-[11px] text-slate-500">Monaco + YAML schema</div>
  </div>

  <div class="min-h-0 flex-1" bind:this={container}></div>
</div>
