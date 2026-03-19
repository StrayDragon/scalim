# Scalim YAML DSL CLI and LSP Reference

此文档由 `scripts/gen-agent-skill.py` 自动生成.

## Canonical Sources
- CLI implementation: `src/scalim/cli/yaml_dsl.py`
- Project identity constants: `src/scalim/_project_constants.py`
- Demand schema file: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Workflow schema file: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- Canonical example: `references/generated/example-full/ecommerce_report.gen.yaml`

## Command Variants
### Repo
- `uv run scalim-cli yaml-dsl validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`
- `uv run scalim-cli yaml-dsl schema show`
- `uv run scalim-cli yaml-dsl schema path`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

### External
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl validate <file.yaml>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema show`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- `uvx --from "scalim[cli]" scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

## Validate Layering
- `yaml-dsl validate`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.
- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.
- workflow YAML: 仅支持 `yaml-dsl schema validate --schema .../workflow.gen.json`(不得对 workflow YAML 运行 `yaml-dsl validate`).

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

## OpenSpec Requirement Map
### `yaml-dsl-cli-validation`
- Source: `openspec/specs/yaml-dsl-cli-validation/spec.md`
- Purpose: 定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.
- Requirements:
  - CLI validate 与 schema validate 职责边界(避免重复诊断)
  - CLI Schema-Only Validation
  - JSONSchema 错误收集(完整 + 稳定 + 去噪)
  - CLI Schema Discovery
  - 严格未知字段校验
  - 运行时 validator 错误列表包含 issue path
  - 校验命令输出与 schema 一致性
  - CLI 校验输出包含源码位置
  - Linter/编译器风格输出
  - validate 对 `outputs.*.fields` object 条目给出可行动诊断
  - CLI can upsert schema modeline in YAML files (IntelliJ compatible)
  - upsert-lsp-comment resolves schema reference from type + schema-path
### `yaml-dsl-editor-core`
- Source: `openspec/specs/yaml-dsl-editor-core/spec.md`
- Purpose: 定义 YAML DSL 编辑器的核心能力:文本优先编辑、Visual 双向同步、统一校验模型、roundtrip 稳定性与可选 exact(Pyodide)语义校验.
- Requirements:
  - 作为纯前端应用运行
  - 文本编辑为主路径(Text-first)
  - 可视化与 YAML 双向编辑(Split)
  - 使用 canonical JSON Schema 提供补全与 hover
  - 编辑器对相对模块引用提供一致提示
  - 编辑器暴露与 canonical schema 语义一致的 `extract`
  - 导入/导出与模板新建
  - Outline 与快速导航
  - 可选多 schema 选择(demand vs workflow)
  - 可视化辅助视图(关系与依赖)
  - 统一 issue 数据模型与定位能力
  - 默认提供 schema-only 校验并支持 strict
  - 支持 local semantic 与 exact semantic 并合并展示
  - exact semantic 基于 Worker + Pyodide 且默认关闭
  - exact 初始化失败自动降级
  - exact 依赖最小化
  - roundtrip 优先补丁并尽量保留格式
  - 重写前必须 diff 预览并显式确认
  - alias 编辑提供共享与拆分策略
  - 可视化编辑块必须提供稳定可发现的新增入口
  - 同一编辑器中的可操作项必须采用一致的交互视觉体系
  - 关键操作的可见性不得依赖 hover-only
  - 编辑器暴露源代码级 `normalize` 并提供与 canonical schema 一致的指引

## Command Details
### `yaml-dsl validate`
- Help: Validate YAML DSL via internal validator
- Usage: `scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--json]
                                    [--verbose]
                                    yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--json]
                                    [--verbose]
                                    yaml_file

positional arguments:
  yaml_file             YAML 文件路径

options:
  -h, --help            show this help message and exit
  --schema SCHEMA, -s SCHEMA
                        JSON Schema 文件路径
  --json                输出 JSON 结果
  --verbose, -v         显示详细错误信息
```

### `yaml-dsl schema validate`
- Help: Validate YAML DSL via JSON Schema
- Usage: `scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--json]
                                           [--verbose]
                                           yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--json]
                                           [--verbose]
                                           yaml_file

positional arguments:
  yaml_file             YAML 文件路径

options:
  -h, --help            show this help message and exit
  --schema SCHEMA, -s SCHEMA
                        JSON Schema 文件路径
  --json                输出 JSON 结果
  --verbose, -v         显示详细错误信息
```

### `yaml-dsl schema show`
- Help: Print JSON Schema
- Usage: `scalim-cli yaml-dsl schema show [-h]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema show [-h]

options:
  -h, --help  show this help message and exit
```

### `yaml-dsl schema path`
- Help: Print JSON Schema path
- Usage: `scalim-cli yaml-dsl schema path [-h]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema path [-h]

options:
  -h, --help  show this help message and exit
```
