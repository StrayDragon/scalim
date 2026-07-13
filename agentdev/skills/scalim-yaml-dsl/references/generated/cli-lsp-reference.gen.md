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
- `uv run scalim-cli yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`
- `uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`
- `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema show`
- `uv run scalim-cli yaml-dsl schema path`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

### External
- `uvx scalim-cli yaml-dsl validate <file.yaml>`
- `uvx scalim-cli yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`
- `uvx scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- `uvx scalim-cli yaml-dsl schema validate <file.yaml>`
- `uvx scalim-cli yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`
- `uvx scalim-cli yaml-dsl schema show`
- `uvx scalim-cli yaml-dsl schema path`
- `uvx scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uvx scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

## Validate Layering
- `yaml-dsl validate --type demand`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.
- `yaml-dsl validate --workflow <workflow.yaml>`: 仅对 demand 生效;注入 workflow.resources.{books,files} 作为 outputs 绑定校验上下文.
- `yaml-dsl validate --type workflow`: 静态/编译期 workflow 校验,递归校验 workflow 引用的 demands,并检查 outputs/books 绑定一致性.
- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式传 `--type workflow`.
- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.
- `yaml-dsl schema validate --workflow <workflow.yaml>`: 仅对 demand 生效;注入 workflow.resources.{books,files} 作为 outputs 绑定校验上下文.

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

## llmanspec Requirement Map
### `yaml-dsl-cli-validation`
- Source: `llmanspec/specs/yaml-dsl-cli-validation/spec.toon`
- Purpose: 定义 CLI 校验工具的行为契约，包括校验分层、诊断输出格式与错误定位，确保 CLI 结果可用于 IDE 跳转、CI 报告与脚本化消费。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
- Requirements:
  - CLI 与 runtime core 职责分离
  - 校验契约 SSOT
  - CLI validate 职责边界
  - 校验覆盖 fail-late 情况
  - JSON 输出格式
  - 源码位置定位
  - Linter 风格输出
  - Schema 发现与查看
  - LSP comment 管理
  - Lint 命令
  - Format 命令
  - demand `schema validate` MUST support `--workflow` context for outputs→resources
  - demand `validate` MUST support the same `--workflow` context behavior as `schema

## Command Details
### `yaml-dsl validate`
- Help: Validate YAML DSL via internal validator
- Usage: `scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--type {auto,demand,workflow}]
                                    [--workflow WORKFLOW] [--path-alias PATH_ALIASES]
                                    [--allowed-yaml-root ALLOWED_YAML_ROOTS] [--json] [--verbose]
                                    yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--type {auto,demand,workflow}]
                                    [--workflow WORKFLOW] [--path-alias PATH_ALIASES]
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
  --workflow WORKFLOW       仅 demand validate: workflow YAML 上下文(用于 outputs→resources 绑定校验)
  --path-alias PATH_ALIASES
                            仅 workflow validate: 需求路径别名,格式 <alias>=<path> (可重复)
  --allowed-yaml-root ALLOWED_YAML_ROOTS
                            允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录
  --json                    输出 JSON 结果
  --verbose, -v             显示详细错误信息
```

### `yaml-dsl schema validate`
- Help: Validate YAML DSL via JSON Schema
- Usage: `scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--workflow WORKFLOW] [--json]
                                           [--verbose]
                                           yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--workflow WORKFLOW] [--json]
                                           [--verbose]
                                           yaml_file

positional arguments:
  yaml_file                 YAML 文件路径

options:
  -h, --help                show this help message and exit
  --schema SCHEMA, -s SCHEMA
                            JSON Schema 文件路径
  --workflow WORKFLOW       仅 demand schema validate: workflow YAML 上下文(用于 outputs→resources 绑定校验)
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
