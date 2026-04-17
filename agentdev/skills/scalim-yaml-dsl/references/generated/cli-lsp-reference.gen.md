# Scalim YAML DSL CLI and LSP Reference

此文档由 `scripts/gen-agent-skill.py` 自动生成.

## Canonical Sources
- CLI implementation: `packages/scalim-cli/src/scalim_cli/yaml_dsl.py`
- Project identity constants: `src/scalim/_project_constants.py`
- Demand schema file: `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
- Workflow schema file: `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`
- Canonical example: `references/generated/example-full/ecommerce_report.gen.yaml`

## Command Variants
### Repo
- `uv run scalim-cli yaml-dsl validate <file.yaml>`
- `uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema show`
- `uv run scalim-cli yaml-dsl schema path`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

### External
- `uvx scalim-cli yaml-dsl validate <file.yaml>`
- `uvx scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uvx scalim-cli yaml-dsl schema validate <file.yaml>`
- `uvx scalim-cli yaml-dsl schema show`
- `uvx scalim-cli yaml-dsl schema path`
- `uvx scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uvx scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

## Validate Layering
- `yaml-dsl validate --type demand`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.
- `yaml-dsl validate --type workflow`: 静态/编译期 workflow 校验,递归校验 workflow 引用的 demands,并检查 outputs/books 绑定一致性.
- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式传 `--type workflow`.
- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.

## LSP / Schema Header
- Repo schema path: `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
- Workflow schema path: `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`
- Canonical example: 故意不写 schema 头(`# $schema: ...`),避免把本机路径固化进共享 YAML.
- 批量写入/更新头部(默认同时写 Red Hat + JetBrains modeline; 可用 `--comment-style` 控制): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- Workflow modeline: `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`
- Repo query: `uv run scalim-cli yaml-dsl schema path`
- External query: `uvx scalim-cli yaml-dsl schema path`
- Python fallback: `python -c "import os, scalim; print(os.path.join(os.path.dirname(scalim.__file__), 'dsl/yaml_dsl/schema/demand.gen.json'))"`
- 本地编辑时再把上面命令输出写入头部; 不要把 `.venv/...` 或其它机器相关路径提交到共享示例.
```yaml
# yaml-language-server: $schema=.../demand.gen.json
# $schema: .../demand.gen.json
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json
```

## OpenSpec Requirement Map
### `yaml-dsl-cli-validation`
- Source: `openspec/specs/yaml-dsl-cli-validation/spec.md`
- Purpose: 定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.
- Requirements:
  - CLI implementation MAY live outside runtime core but MUST preserve validation contracts
  - CLI validation MUST reuse the unified YAML load facade
  - YAML validation contracts MUST be centralized as SSOT across entrypoints
  - CLI validate MUST delegate validation logic to a reusable service layer
  - CLI validate 与 schema validate 职责边界(避免重复诊断)
  - validate and schema validate MUST catch known fail-late cases consistently
  - CLI Schema-Only Validation
  - JSONSchema 错误收集(完整 + 稳定 + 去噪)
  - CLI Schema Discovery
  - 严格未知字段校验
  - 运行时 validator 错误列表包含 issue path
  - 校验命令输出与 schema 一致性
  - CLI 校验输出包含源码位置
  - `ValidationIssue.path` MUST 使用单一 canonical 口径以稳定映射到源码位置
  - Linter/编译器风格输出
  - validate 对 `outputs.*.fields` object 条目给出可行动诊断
  - CLI can upsert schema modeline in YAML files (IntelliJ compatible)
  - upsert-lsp-comment resolves schema reference from type + schema-path
  - CLI MUST provide a `PROJECT_CLI_NAME yaml-dsl lint` entrypoint for YAML DSL authoring linting
  - CLI MUST provide a `PROJECT_CLI_NAME yaml-dsl format` entrypoint for idempotent formatting

## Command Details
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
