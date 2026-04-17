## Context

Scalim runtime 的 YAML 解析链路已明确支持 YAML merge key (`<<`)（ruamel flatten + “显式键重复检测”策略），并在 imports 相关诊断中推荐用户使用 `<<` 做 in-file reuse；但当前生成的 YAML DSL `JSON Schema` 在多个 mapping 节点使用 `propertyNames` 正则约束（例如 `^[a-zA-Z_][a-zA-Z0-9_]*$`），未将 `<<` 纳入允许集合，导致 `yaml-language-server`（Red Hat `vscode-yaml` 同款）在编辑器侧对 `<<` 报“key 不匹配 pattern”的假阳性。

我们已用本地构建的 `yaml-language-server`（`node out/server/src/server.js --stdio`）验证其行为：服务端会在 object 校验时特殊处理 merge key 以展开 `seenKeys`（用于 required/additionalProperties 等），但 `propertyNames` 校验是对原始 AST key 逐个验证，因此 `<<` 会触发 `propertyNames.pattern` 失败。

## Goals / Non-Goals

**Goals:**
- 对齐 schema 与 runtime：`demand.gen.json` / `workflow.gen.json` / `scalim_yaml.gen.json` 中所有使用 `propertyNames` 的 map-like object 节点都允许 `<<`，消除编辑器假阳性。
- 不放宽既有命名规则：除 `<<` 外，原 `propertyNames` 约束保持不变。
- 通过生成期/测试门禁避免回归（防止未来新增 `propertyNames` 节点再次遗漏）。
- 明确文档/生成边界：只改 SSOT/生成器，禁止手改 `*.gen.json`。

**Non-Goals:**
- 不改变 runtime 的 YAML merge 语义（运行时仍是最终裁决与错误来源）。
- 不修改 `yaml-language-server` / VS Code 扩展本身的行为。
- 不尝试让 schema 表达“merge 后的语义等价”（例如把 merge 展开后的类型约束做静态推导）；仅消除 key-level 假阳性。

## Decisions

### Decision: 在 schema 生成器中统一注入 `propertyNames` 的 merge key 允许项

选择在 `packages/scalim-misc` 的 schema 生成管线里做递归 post-process：
- **输入**：生成器产出的完整 schema dict（包含 demand/workflow/scalim_yaml）。
- **策略**：遍历所有节点，遇到 `propertyNames` 时：
  - 若 `propertyNames` 已显式允许 `<<`（`const/enum/anyOf` 等），保持不变；
  - 否则将其改写为：
    - `{"anyOf": [{"const": "<<"}, <原 propertyNames schema>]}`。

理由：
- 不依赖“列举所有位置”的手工维护，避免未来新增 schema 节点遗漏。
- 可一次覆盖三份 schema（demand/workflow/scalim_yaml），与本变更目标一致。
- 变更局部且可逆：仅包一层 `anyOf`，不改变原约束。

### Decision: 不为 `<<` 增加专用 `properties["<<"]` schema

`yaml-language-server` 在 object 校验里会跳过 merge key 的 additionalProperties/required 校验路径（merge 会被展开为 seenKeys），当前核心问题仅来自 `propertyNames`。因此仅修正 `propertyNames` 即可达成目标，避免把 `<<` 作为“普通业务字段”暴露在 schema 中带来误导。

### Decision: 增加回归门禁（schema-only）

新增/扩展治理测试：读取生成后的 `*.gen.json`，遍历所有 `propertyNames`，断言均允许 `<<`。目标是把“编辑器体验契约”固化为 gate，防止未来 drift 回归。

## Risks / Trade-offs

- **[风险]** `propertyNames` 注入过宽（某些 object 节点理论上不希望出现 merge） → **缓解**：注入只发生在已经使用 `propertyNames` 的节点；并保持其它 key 约束不变，且 runtime validator 仍会对语义错误 fail-fast。
- **[权衡]** 编辑器补全可能把 `<<` 作为可用 key 暴露 → **接受**：这是合法 YAML 语法；对 authoring 体验总体收益更大。
- **[风险]** 生成器递归改写逻辑误伤非 schema 节点（例如某些 docs payload） → **缓解**：仅对 schema dict 内出现的 `propertyNames` 键做结构化改写，并为该函数增加单测覆盖典型/边界输入。

