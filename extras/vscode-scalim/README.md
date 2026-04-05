# Scalim YAML DSL (VSCode Extension)

MVP goals:

- Provide a safe-by-default YAML DSL LSP experience:
  - Reuse an existing server install (workspace venv / PATH)
  - Never install dependencies without an explicit user action
- Best-effort **0-config** auto-start:
  - Activate on YAML, but only start the server when the file looks like Scalim YAML DSL
  - Avoid polluting unrelated YAML with scalim diagnostics/features
- Start the YAML DSL LSP server via stdio (`scalim-yaml-dsl-lsp serve`)
- Cooperate with `redhat.vscode-yaml` by updating workspace `yaml.schemas` (idempotent merge)
- Provide diagnosable logs via the `Scalim YAML DSL` output channel

## Requirements

- A working `scalim-yaml-dsl-lsp` installation (either in a workspace venv or on PATH)
- Python >= 3.10 (required by the server; also used only when `envMode=pinnedVenv` provisioning is enabled)
- `redhat.vscode-yaml` (optional but recommended for schema support)

## Settings

- `scalim.yamlDsl.envMode`: choose server environment mode:
  - `workspaceVenv`: reuse an existing workspace venv (recommended for scalim development)
  - `auto` (default): try `workspaceVenv` first (if valid), then try PATH (recommended for framework users who installed via `uv tool`)
  - `pinnedVenv`: manage an isolated pinned venv under `globalStorageUri` (install only happens after an explicit reinstall action)
- `scalim.yamlDsl.workspaceVenvPath`: workspace venv path (used when `envMode=workspaceVenv/auto`, default: `.venv`)
- `scalim.yamlDsl.pythonPath`: override python executable path (leave empty to auto-detect)
- `scalim.yamlDsl.pinnedServerSpec`: pinned pip requirement for the LSP server
- `scalim.yamlDsl.autoSchemaBinding`: auto-update workspace `yaml.schemas`

## Two primary workflows

### 1) Plugin development / testing (scalim repo)

Goal: run the LSP server from the repo `.venv` to validate changes quickly.

- Ensure the workspace venv contains the server: `uv sync --group dev`
- Use:
  - `scalim.yamlDsl.envMode=workspaceVenv`
  - `scalim.yamlDsl.workspaceVenvPath=.venv`
- Recommended: use the bundled workspace `extras/vscode-scalim/scalim-dev.code-workspace`

### 2) Framework users (no automatic installs)

Goal: start the server only if the user already installed it; otherwise prompt with an install command (no side effects).

- Install the server with `uv tool` (recommended):
  - `uv tool install "scalim-yaml-dsl-lsp[server]==0.7.5"`
- Keep the default `scalim.yamlDsl.envMode=auto`
- If the extension cannot find the server, it shows an error with:
  - an install command to copy
  - or a terminal action that inserts the command (without executing)

## 0-config auto-start rules (heuristic)

The extension activates on YAML, but only auto-starts the server when the active document contains one of:

- A schema modeline referencing scalim schemas (`demand.gen.json` / `workflow.gen.json`)
- `main_source:` (demand) or `workflow:` (workflow)
- `$import` / `$init_var` (YAML DSL-specific syntax)

If none match, the server will not start automatically (you can still use `Scalim YAML DSL: Restart server`).

## Manual verification

1. Press `F5` to start an Extension Host window
2. Open folder `extras/vscode-scalim/fixtures/`
3. Open `demand/demo.yaml` and `workflow/demo.yaml`
4. Check:
   - Output channel `Scalim YAML DSL` contains environment + server logs
   - Command palette has:
     - `Scalim YAML DSL: Restart server`
     - `Scalim YAML DSL: Reinstall server (rebuild venv)`
     - `Scalim YAML DSL: Show diagnostics`
     - `Scalim YAML DSL: Open logs`
     - `Scalim YAML DSL: Show discovery summary`
     - `Scalim YAML DSL: Open/Create scalim.yaml`

## Build VSIX (dev)

From the repo root:

```bash
cd extras/vscode-scalim
just package-vsix
```

Output: `extras/vscode-scalim/vscode-scalim.vsix`
