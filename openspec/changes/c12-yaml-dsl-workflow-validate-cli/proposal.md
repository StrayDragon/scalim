## Why

来自 cus_collect_infos 迁移实践反馈（基于 Scalim 0.3.2 实际使用；FR7）：workflow YAML 目前缺少一个“面向 CI/预发布”的 workflow-level full validate 入口。用户只能做：

- workflow 的 schema-only 校验（例如编辑器或 `yaml-dsl schema validate --schema workflow.gen.json`）
- 或者直接运行 workflow，在运行期依赖 fail-fast 报错

这会导致一类典型问题发现得太晚、诊断成本高：

- `workflow.runs[*].demand` 引用的 demand YAML 存在语义错误/引用缺失（imports/$import、allowlist、字段依赖等）
- `runs[*].writes[*]` 引用的 output id 在对应 demand 中不存在（直到写入阶段才报错）
- `depends_on`/`$ctx` 的引用越界或 key 错误（直到物化编译/执行时才报错）
- workflow 与 demand 间的“编排意图一致性”难以在 CI 阶段静态检查

仓库现状（as implemented）：

- demand 侧已有 CLI 校验：`src/scalim/cli/yaml_dsl.py`（`yaml-dsl validate` / `yaml-dsl schema validate`），规范见 `openspec/specs/yaml-dsl-cli-validation/spec.md`。
- workflow 侧已有解析/语义校验器：`src/scalim/dsl/by_yaml/workflow.py`（含 editor 兼容 JSON payload 的 `validate_workflow_yaml_text_json`），规范见 `openspec/specs/yaml-dsl-workflow/spec.md`。
- 但缺少一个“把 workflow 与其引用的 demands 一起校验”的 CLI 入口（并输出 linter 风格定位/JSON payload）。

## What Changes

- 新增 CLI 子命令（提案目标形态）：
  - `uv run scalim-cli yaml-dsl workflow validate <workflow.yaml>`
  - 支持 `--json/--verbose` 等与现有 demand validate 一致的输出风格（保持脚本化消费与 IDE 跳转体验）。
- 校验内容（v1 聚焦“静态/编译期可确定”的检查，不执行 workflow）：
  1) 校验 workflow YAML 自身结构与语义：
     - 解析（含 duplicate key 检测）
     - `depends_on` 引用有效性与 cycle detection
     - `resources`/`writes` authoring surface 的结构合法性（writes 是 SSOT；不引入/不兼容 `write_to`）
  2) 递归校验每个 `runs[*].demand`：
     - 基于文件路径入口加载 demand YAML（允许 imports/$import；对 fragments 的错误输出 import trace）
     - 复用现有 `ConfigValidator`（语义 validator + 可选 JSONSchema 补充），并保留来源文件的 line/column 诊断能力
  3) 做 workflow ↔ demand 的交叉一致性检查（尽可能在 validate 阶段 fail-fast）：
     - `writes[*].{workbook_sheet|workbook_append|csv_append|sheetbook_*}.output` 必须存在于对应 demand 的 `outputs[*].name`
     - `$ctx` 引用：
       - node 引用必须存在且在 deps 可见范围
       - key 必须为非空字符串；若 key 属于 workflow 默认 summary keys（`output_path/total_rows/duration_secs`），可做静态存在性校验
     - （可选，v1 可先做 warn）若 demand 输出路径为静态字面量，可做保守的冲突预检查（与 workflow shared resources 保留路径冲突、或 runs 间重复路径）
- Non-Goals（v1 明确不做）：
  - 不执行 workflow / 不调用任何 loader（只做静态/编译期校验）
  - 不要求在 validate 阶段解析出 `$ctx` 的实际值（只校验引用合法性与可见性）
  - 不引入新的 workflow YAML authoring surface（只新增 CLI 能力）

## Capabilities

### New Capabilities
- `yaml-dsl-workflow-validate`: 提供 workflow-level full validate CLI，递归校验引用 demands，并检查 workflow↔demand 的交叉一致性（writes/output id、depends_on/$ctx 可见性等）。

### Modified Capabilities
- `yaml-dsl-cli-validation`: CLI 增加 workflow validate 子命令，并复用现有 JSON/linter 输出与定位语义。
- `yaml-dsl-workflow`: workflow 校验分层需要在规范层明确（schema-only vs workflow validate 的职责边界）。

## Impact

- 受影响代码（示例）：
  - CLI：`src/scalim/cli/yaml_dsl.py`（新增子命令与输出协议）
  - workflow 解析与语义校验：`src/scalim/dsl/by_yaml/workflow.py`
  - demand 校验复用：`src/scalim/dsl/by_yaml/config_parsing/validator.py`、`src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - workflow 运行期 `$ctx` 指令形态（用于复用/对齐校验规则）：`src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
- Public surface：新增 CLI 命令（不影响现有运行入口）。
- 文档治理：
  - specs SSOT：`openspec/specs/**`
  - schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`（生成物 `src/scalim/dsl/by_yaml/schema/*.gen.json` 不手改）
  - docs 生成物（`.gen.`/AUTOGEN blocks）若后续需要更新，统一走 `just gen-docs`
