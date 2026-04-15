## Context

当前 YAML DSL 的 runtime 校验链路（`src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py`）会尝试可选导入 `jsonschema` 并在启用 schema 校验时执行 JSONSchema 校验；当运行环境未安装或依赖不兼容时，会输出 warning：

- `[scalim] schema: jsonschema 不可用, 已跳过 schema 校验 ...`
- 真实用户环境中常见的失败原因包括第三方依赖版本不匹配（例如 `attrs` 过旧导致 `attrib(..., converter=...)` 抛 `TypeError`）。

由于 runtime core 需要兼容 Python 3.6 且主包不应被工具链可选依赖拖入版本地狱，上述行为在真实环境中往往变成**高频噪音**，并导致校验结果在不同环境下不一致（是否安装/是否兼容 `jsonschema` 会改变诊断强度）。

与此同时，仓库已存在明确的 schema-only 工具链路径：

- CLI：`scalim-cli yaml-dsl schema validate`（依赖 `jsonschema`）
- 编辑器/LSP：基于 JSON Schema 的补全/hover/choices（以及可选的 schema-only 诊断）

本变更选择把 JSONSchema 校验从 runtime 主线彻底移除，让 runtime 的 parse/validate 仅依赖自研语义校验与 unknown-fields。

**文档/生成边界与漂移治理**
- SSOT（规范真相）：`openspec/specs/*/spec.md`
- 本变更的增量规范：`openspec/changes/c0-drop-runtime-jsonschema/specs/**/spec.md`
- 本变更不直接编辑任何 `*.gen.*` 生成物；如后续需要更新文档站点注入块或生成页面，应通过 SSOT 改动并运行 `just gen-docs`。
- 共享/发布前需要通过 `just openspec-check` 兜底（sanitize + OpenSpec 结构校验）。

## Goals / Non-Goals

**Goals:**
- runtime core（`src/scalim/`）在 YAML parse/validate/compile/run 路径中不再导入/使用 `jsonschema`。
- runtime 不再输出 “jsonschema 不可用/已跳过 schema 校验” 的 warning（消除用户日志噪音）。
- runtime 校验口径在不同环境下保持一致：只依赖语义校验 + unknown-fields + parser fail-fast。
- CLI/LSP 的 schema-only 能力保留：JSONSchema 校验由工具链承担，且依赖由工具链发行物显式声明。
- “CLI 的依赖声明”与“命令职责边界”在 README/帮助中写清楚（尤其是 `schema validate` 依赖 `jsonschema`）。

**Non-Goals:**
- 不尝试修复或约束用户环境的 `jsonschema/attrs` 版本组合（工具链依赖由发行物治理）。
- 不改变 YAML DSL 的 authoring 语义主线（除去 runtime 中的 JSONSchema 校验副作用）。
- 不重写/替换 JSON Schema 生成体系（`demand.gen.json`/`workflow.gen.json` 仍作为工具链与 unknown-fields 的输入）。

## Decisions

1) **runtime 不再执行 JSONSchema 校验**
- 移除 runtime `ConfigValidator` 内的 `jsonschema` 可选导入与校验分支；所有 runtime 入口只执行语义校验与 unknown-fields。
- 预期收益：
  - 行为稳定（不再依赖可选依赖状态）
  - 消除日志噪音
  - 缩小 Python 3.6 兼容面的风险敞口

2) **JSONSchema 校验仅保留在工具链的 schema-only 路径**
- `scalim-cli yaml-dsl schema validate` 与 LSP 继续承担结构/类型层面的 schema-only 校验。
- 若希望保留“validate 给出 schema-only 诊断”的体验，也应在 CLI 层显式实现（而不是 runtime core 隐式可选）。

3) **删除兼容/钩子优先，统一升级为单主线**
- 既有 `enable_jsonschema_validation`/`HAS_JSONSCHEMA`/`jsonschema_validate_fn` 等 runtime 分支会被移除或收敛，避免留下隐式可选路径。
- 所有调用方（loader / validation_service / compiler_frontend 等）同步升级到新口径。

4) **保障覆盖面：把 JSONSchema 曾经兜底的风险点补到语义/parse 校验**
- 对历史上依赖 JSONSchema 才能捕获的结构/类型问题，明确分类：
  - 若属于运行时必须的语义约束：补到语义 validator 或 parser fail-fast（SSOT）
  - 若属于编辑器友好/结构提示：留给 schema-only（CLI/LSP）

## Risks / Trade-offs

- **[风险] validate 诊断信息变少（不再包含 JSONSchema 的结构/类型错误）**
  - → **缓解**：强调 `schema validate` 的使用场景；并在 CLI 文档中明确两者职责边界与选择建议。

- **[风险] 过去依赖 JSONSchema 兜底的非法输入可能在 validate 路径中漏掉**
  - → **缓解**：对比 `validate` 与 `schema validate` 的回归用例集，确认“运行时必需约束”均由语义/parse 层覆盖；必要时补充 SSOT 校验与测试。

- **[风险] 相关 OpenSpec 规范当前声明了 “jsonschema 不可用时输出 warning”**
  - → **缓解**：本变更提供 delta specs 调整对应 REQUIREMENTS（见 `framework-logging` 与 `yaml-dsl-cli-validation`）。

