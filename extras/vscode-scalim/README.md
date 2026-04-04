# Scalim YAML DSL (VSCode Extension)

MVP goals:

- Manage a pinned `scalim-yaml-dsl-lsp[server]==...` installation inside an isolated venv under VSCode `globalStorageUri`
- Start the YAML DSL LSP server via stdio (`scalim-yaml-dsl-lsp serve`)
- Cooperate with `redhat.vscode-yaml` by updating workspace `yaml.schemas` (idempotent merge)
- Provide diagnosable logs via the `Scalim YAML DSL` output channel

## Requirements

- Python >= 3.10 (used for provisioning the venv)
- `redhat.vscode-yaml` (optional but recommended for schema support)

## Settings

- `scalim.yamlDsl.pythonPath`: override python executable path (leave empty to auto-detect)
- `scalim.yamlDsl.pinnedServerSpec`: pinned pip requirement for the LSP server
- `scalim.yamlDsl.autoSchemaBinding`: auto-update workspace `yaml.schemas`

## Development / Manual verification

1. Press `F5` to start an Extension Host window
2. Open folder `extras/vscode-scalim/fixtures/`
3. Open `demand/demo.yaml` and `workflow/demo.yaml`
4. Check:
   - Output channel `Scalim YAML DSL` contains provisioning + server logs
   - Command palette has:
     - `Scalim YAML DSL: Restart server`
     - `Scalim YAML DSL: Reinstall server (rebuild venv)`
     - `Scalim YAML DSL: Show diagnostics`
     - `Scalim YAML DSL: Open logs`
     - `Scalim YAML DSL: Show discovery summary`
     - `Scalim YAML DSL: Open/Create scalim.yaml`
