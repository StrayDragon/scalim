## Context

现状:

- demand YAML 已有两个 CLI 校验入口:
  - `scalim-cli yaml-dsl validate <demand.yaml>`: 语义校验(内部 `ConfigValidator` + imports 展开 + 可选 JSONSchema 补充)
  - `scalim-cli yaml-dsl schema validate <demand.yaml>`: JSONSchema 校验(需要 `jsonschema`)
- workflow YAML 目前只有:
  - schema-only 校验(依赖 `workflow.gen.json`)
  - 或直接 `run_workflow(...)` 在运行期 fail-fast

因此 workflow 编排层面的错误(例如 `writes[*].output` 引用不存在的 output,或某个 run 引用的 demand YAML 本身语义错误)只能在运行或很晚阶段发现,不利于 CI/预发布。

仓库内可复用的实现基础:

- workflow 语义解析/校验(含 duplicate key 检测、`depends_on` 合法性/cycle detection、`writes`/`resources` authoring surface):
  - `src/scalim/dsl/by_yaml/workflow.py`
- demand YAML 语义校验与定位:
  - `src/scalim/dsl/by_yaml/config_parsing/validator.py` (`ConfigValidator`, `build_yaml_location_index`, `attach_locations`)
  - `src/scalim/dsl/by_yaml/config_parsing/imports.py` (`expand_imports_inplace`)
- workflow run 级路径解析(支持相对路径,以及 `@/`/`alias:/...` 形式,通过 `path_aliases` 提供别名根):
  - `src/scalim/dsl/by_yaml/workflow.py::resolve_workflow_demand_path`
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py::run_workflow(..., path_aliases=...)`

约束:

- `src/scalim/` 代码须保持 Python 3.6 兼容
- 不引入新的强依赖;JSONSchema 仍为可选依赖
- 不手改 `.gen.*` 与 injected blocks;文档/索引类生成物只走 `just gen`/`just gen-docs`

## Goals / Non-Goals

**Goals:**

- 新增能力: `scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`(或默认自动推断为 workflow)
- 校验必须为“静态/编译期”: 不执行 workflow,不调用任何 loader
- 校验范围(满足 `openspec/changes/c12-yaml-dsl-workflow-validate-cli/specs/yaml-dsl-workflow-validate/spec.md`):
  - workflow YAML 自身结构与语义校验(解析、引用合法性、cycle detection 等)
  - 递归校验每个 `runs[*].demand` 引用的 demand YAML(允许 imports/$import;错误需包含可诊断的引用链路)
  - workflow ↔ demand 的交叉一致性校验: `writes[*].*.output` 必须存在于对应 demand 的 `outputs[*].name`
- 输出体验与现有 demand validate 对齐:
  - 支持 `--json` 与 linter 风格输出
  - 尽可能提供可定位的 line/column(通过 `build_yaml_location_index` + `attach_locations`)
- 与 workflow runtime 的路径解析口径一致:
  - 支持 `--path-alias <alias>=<path>`(可重复),用于校验 `@/` 与 `<alias>:/...` 的 demand 引用

**Non-Goals:**

- 不执行 workflow / 不构建 execution plan / 不编译 demand IR(避免 allowlist/loader 相关副作用)
- 不要求在 validate 阶段解析 `$ctx` 的实际值(仅校验结构/可见性属于后续增强点;本变更可先不做)
- 不引入 workflow JSONSchema 校验作为 workflow validate 的硬前置(结构/unknown-fields 由 LSP/schema validate 兜底)

## Decisions

1) CLI 命令布局

- 在现有 `yaml-dsl validate` 上扩展 `--type {auto,demand,workflow}`:
  - `--type demand`: 强制按 demand 校验
  - `--type workflow`: 强制按 workflow 校验(本变更交付)
  - `--type auto`(默认): 自动推断(例如检测 root 是否包含 `workflow` 键)
- 复用现有 `ValidationPayload`/`Issue` 输出风格;但 workflow validate 为多文件校验,JSON 输出需要一个可脚本消费的聚合结构。

2) JSON 输出协议(多文件聚合)

- 新增一个 workflow validate 专用 payload(建议命名 `WorkflowValidationPayload`),包含:
  - `mode="workflow-validate"`
  - `ok: bool`
  - `workflow_yaml_path`
  - `results: [ValidationPayload]`(第一个为 workflow 本身,其余为每个 run 对应 demand 的 validate 结果)
- 这样可以保持与 demand validate 的 `ValidationPayload`/issue 结构一致,同时在 workflow 入口层聚合。

3) workflow YAML 校验方式

- workflow 语义校验直接复用 `load_workflow_config(...)`:
  - 优点: 与 runtime authoring surface 同源,并包含 duplicate key 检测
  - 异常统一捕获为 `WorkflowConfigError`,转为 `Issue(path=exc.path, message=str(exc))`
- 为提供定位信息:
  - workflow YAML 文本上使用 `build_yaml_location_index` 构建 locations
  - 用 `attach_locations` 为 workflow issues 附加 line/column(找不到则回退为 `(1,1)`)

4) demand YAML 校验方式(递归)

- 复用 `yaml-dsl validate` 的实现链路(读取文本 → `yaml.safe_load` → `expand_imports_inplace` → `ConfigValidator.validate_report` → `attach_locations`)
- 为减少重复代码:
  - 将 demand validate 的“核心校验逻辑”抽出为内部函数(例如 `_validate_demand_yaml_text(...)`),供原 `validate` 与新 `workflow validate` 复用

5) `writes[*].output` ↔ demand `outputs` 交叉一致性

- 对每个 run 的 demand YAML(在 imports 展开后)提取 output id 集合:
  - `outputs` 为 list;每个 item mapping 的 `name` 作为 output id
- 对每个 workflow run 的 `writes[*]`:
  - 找到 write intent 的 output id
  - 若 output id 不在 demand outputs 集合中,产生 `Issue`:
    - `path`: 指向该 write intent 的 `...output` 字段(例如 `workflow.runs.1.writes.0.csv_append.output`)
    - `message`: 指出 output id 不存在,并给出可选 suggestions(例如列出已知 outputs)

## Risks / Trade-offs

- [多文件错误输出过长] → JSON 输出聚合 + linter 输出按文件分段,保持稳定顺序(按 workflow 声明顺序)
- [路径别名与 CI/容器目录差异] → 提供 `--path-alias` 显式注入,避免依赖 git root 或硬编码仓库结构
- [workflow 校验与 schema-only 的职责重叠] → workflow validate 聚焦“引用/一致性/跨文件语义”,unknown-fields 仍由 schema validate/LSP 兜底

## Migration Plan

- 扩展 `yaml-dsl validate` 的 `--type workflow` 不影响现有 demand validate;旧用户可逐步把 CI 从“只跑 schema validate”升级为“workflow validate + demand validate”
- 文档与生成物:
  - 若需要补充 CLI 文档/索引,只改 SSOT(如 `openspec/specs/yaml-dsl-cli-validation/spec.md` 或 docs SSOT),再运行 `just gen`/`just gen-docs`

## Open Questions

- JSON 输出是否需要提供 “per-run id” 的键(而不是仅文件路径)? 当前建议将 run_id 放入 `ValidationPayload` 的扩展字段或在 issue message 中体现。
- 是否要在本变更内增加 `$ctx` 的结构与可见性校验(不求解析值),以进一步贴合 workflow runtime 的 fail-fast 行为。
