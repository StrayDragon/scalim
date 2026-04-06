<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `src/scalim/cli/yaml_dsl.py`
- `packages/scalim-misc/src/scalim_misc/cli_docs.py`
- `packages/scalim-misc/src/scalim_misc/yaml_dsl_cli_reference_md.py`
-->
# Scalim YAML DSL CLI and LSP Reference

此文档由 `just gen-docs` 自动生成.

## Canonical Sources
- CLI implementation: `src/scalim/cli/yaml_dsl.py`
- Project identity constants: `src/scalim/_project_constants.py`
- Demand schema file: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Workflow schema file: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- Canonical example: `artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`

## Command Variants
### Repo
- `uv run scalim-cli yaml-dsl validate <file.yaml>`
- `uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uv run scalim-cli yaml-dsl run <demand.yaml> --allowed-module myapp.loaders`
- `uv run scalim-cli yaml-dsl workflow run <workflow.yaml> --allowed-module myapp.loaders`
- `uv run scalim-cli yaml-dsl schema validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema show`
- `uv run scalim-cli yaml-dsl schema path`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

### External
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl validate <file.yaml>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl run <demand.yaml> --allowed-module myapp.loaders`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl workflow run <workflow.yaml> --allowed-module myapp.loaders`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema show`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

## Validate Layering
- `yaml-dsl validate --type demand`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.
- `yaml-dsl validate --type workflow`: 静态/编译期 workflow 校验,递归校验 workflow 引用的 demands,并检查 outputs/books 绑定一致性.
- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式传 `--type workflow`.
- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.

## LSP / Schema Header
- Repo schema path: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Workflow schema path: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- Canonical example: 故意不写 schema 头(`# $schema: ...`),避免把本机路径固化进共享 YAML.
- 批量写入/更新头部(默认同时写 Red Hat + JetBrains modeline; 可用 `--comment-style` 控制): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- Workflow modeline: `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`
- Repo query: `uv run scalim-cli yaml-dsl schema path`
- External query: `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path`
- Python fallback: `python -c "import os, scalim; print(os.path.join(os.path.dirname(scalim.__file__), 'dsl/by_yaml/schema/demand.gen.json'))"`
- 本地编辑时再把上面命令输出写入头部; 不要把 `.venv/...` 或其它机器相关路径提交到共享示例.
```yaml
# yaml-language-server: $schema=.../demand.gen.json
# $schema: .../demand.gen.json
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json
```

## Command Details
### `yaml-dsl run`
- Help: Run a demand YAML
- Usage: `scalim-cli yaml-dsl run [-h] [--init-vars-json INIT_VARS_JSON]
                               [--template-vars-json TEMPLATE_VARS_JSON]
                               [--allowed-module ALLOWED_MODULES]
                               [--allowed-function ALLOWED_FUNCTIONS]
                               [--allowed-yaml-root ALLOWED_YAML_ROOTS]
                               [--template-sandbox {safe,legacy}] [--parallel-mode {seq,adaptive}]
                               [--max-workers MAX_WORKERS]
                               yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl run [-h] [--init-vars-json INIT_VARS_JSON]
                               [--template-vars-json TEMPLATE_VARS_JSON]
                               [--allowed-module ALLOWED_MODULES]
                               [--allowed-function ALLOWED_FUNCTIONS]
                               [--allowed-yaml-root ALLOWED_YAML_ROOTS]
                               [--template-sandbox {safe,legacy}] [--parallel-mode {seq,adaptive}]
                               [--max-workers MAX_WORKERS]
                               yaml_file

positional arguments:
  yaml_file                 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --init-vars-json INIT_VARS_JSON
                            可选: init_vars JSON 文件路径(JSON object mapping)
  --template-vars-json TEMPLATE_VARS_JSON
                            可选: template_vars JSON 文件路径(JSON object mapping)
  --allowed-module ALLOWED_MODULES
                            允许导入/引用的模块白名单(可重复)
  --allowed-function ALLOWED_FUNCTIONS
                            允许导入/引用的函数白名单(可重复,格式 pkg.mod:fn 或 pkg.mod.fn)
  --allowed-yaml-root ALLOWED_YAML_ROOTS
                            允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录
  --template-sandbox {safe,legacy}
                            可选:模板 sandbox 模式(默认 safe)
  --parallel-mode {seq,adaptive}
                            可选:并行模式(默认 seq)
  --max-workers MAX_WORKERS
                            可选:最大并发工作数(默认 0 自动)
```

### `yaml-dsl workflow run`
- Help: Run a workflow YAML
- Usage: `scalim-cli yaml-dsl workflow run [-h] [--init-vars-json INIT_VARS_JSON]
                                        [--template-vars-json TEMPLATE_VARS_JSON]
                                        [--allowed-module ALLOWED_MODULES]
                                        [--allowed-function ALLOWED_FUNCTIONS]
                                        [--allowed-yaml-root ALLOWED_YAML_ROOTS]
                                        [--template-sandbox {safe,legacy}]
                                        [--parallel-mode {seq,adaptive}] [--max-workers MAX_WORKERS]
                                        [--path-alias PATH_ALIASES]
                                        yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl workflow run [-h] [--init-vars-json INIT_VARS_JSON]
                                        [--template-vars-json TEMPLATE_VARS_JSON]
                                        [--allowed-module ALLOWED_MODULES]
                                        [--allowed-function ALLOWED_FUNCTIONS]
                                        [--allowed-yaml-root ALLOWED_YAML_ROOTS]
                                        [--template-sandbox {safe,legacy}]
                                        [--parallel-mode {seq,adaptive}] [--max-workers MAX_WORKERS]
                                        [--path-alias PATH_ALIASES]
                                        yaml_file

positional arguments:
  yaml_file                 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --init-vars-json INIT_VARS_JSON
                            可选: init_vars JSON 文件路径(JSON object mapping)
  --template-vars-json TEMPLATE_VARS_JSON
                            可选: template_vars JSON 文件路径(JSON object mapping)
  --allowed-module ALLOWED_MODULES
                            允许导入/引用的模块白名单(可重复)
  --allowed-function ALLOWED_FUNCTIONS
                            允许导入/引用的函数白名单(可重复,格式 pkg.mod:fn 或 pkg.mod.fn)
  --allowed-yaml-root ALLOWED_YAML_ROOTS
                            允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录
  --template-sandbox {safe,legacy}
                            可选:模板 sandbox 模式(默认 safe)
  --parallel-mode {seq,adaptive}
                            可选:并行模式(默认 seq)
  --max-workers MAX_WORKERS
                            可选:最大并发工作数(默认 0 自动)
  --path-alias PATH_ALIASES
                            可选:workflow demand 路径别名,格式 <alias>=<path> (可重复)
```

### `yaml-dsl validate`
- Help: Validate YAML DSL via internal validator
- Usage: `scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--type {auto,demand,workflow}]
                                    [--path-alias PATH_ALIASES]
                                    [--allowed-yaml-root ALLOWED_YAML_ROOTS] [--json] [--verbose]
                                    yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--type {auto,demand,workflow}]
                                    [--path-alias PATH_ALIASES]
                                    [--allowed-yaml-root ALLOWED_YAML_ROOTS] [--json] [--verbose]
                                    yaml_file

positional arguments:
  yaml_file                 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --schema SCHEMA, -s SCHEMA
                            JSON Schema 文件路径
  --type {auto,demand,workflow}
                            校验类型: auto/demand/workflow
  --path-alias PATH_ALIASES
                            仅 workflow validate: 需求路径别名,格式 <alias>=<path> (可重复)
  --allowed-yaml-root ALLOWED_YAML_ROOTS
                            允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录
  --json                    输出 JSON 结果
  --verbose, -v             显示详细错误信息
```

### `yaml-dsl schema validate`
- Help: Validate YAML DSL via JSON Schema
- Usage: `scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--json] [--verbose] yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--json] [--verbose] yaml_file

positional arguments:
  yaml_file                 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --schema SCHEMA, -s SCHEMA
                            JSON Schema 文件路径
  --json                    输出 JSON 结果
  --verbose, -v             显示详细错误信息
```

### `yaml-dsl schema show`
- Help: Print JSON Schema
- Usage: `scalim-cli yaml-dsl schema show [-h] [--type SCHEMA_TYPE]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema show [-h] [--type SCHEMA_TYPE]

options:
  -h, --help          show this help message and exit
  --type SCHEMA_TYPE  Schema 类型(例如 demand/workflow/scalim_yaml)
```

### `yaml-dsl schema path`
- Help: Print JSON Schema path
- Usage: `scalim-cli yaml-dsl schema path [-h] [--type SCHEMA_TYPE]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema path [-h] [--type SCHEMA_TYPE]

options:
  -h, --help          show this help message and exit
  --type SCHEMA_TYPE  Schema 类型(例如 demand/workflow/scalim_yaml)
```

### `yaml-dsl upsert-lsp-comment`
- Help: Upsert YAML $schema modeline comment (JetBrains/RedHat)
- Usage: `scalim-cli yaml-dsl upsert-lsp-comment [-h] [--type SCHEMA_TYPE] [--schema-path SCHEMA_PATH]
                                              [--comment-style {all,jetbrains,redhat}]
                                              paths [paths ...]`
- Full help:
```text
usage: scalim-cli yaml-dsl upsert-lsp-comment [-h] [--type SCHEMA_TYPE] [--schema-path SCHEMA_PATH]
                                              [--comment-style {all,jetbrains,redhat}]
                                              paths [paths ...]

positional arguments:
  paths                     一个或多个 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --type SCHEMA_TYPE        Schema 类型(例如 demand/workflow)
  --schema-path SCHEMA_PATH
                            Schema base URL/dir 或完整 .json URL/path(默认使用内置 schema 目录)
  --comment-style {all,jetbrains,redhat}
                            Schema modeline 风格: all/jetbrains/redhat
```
