## Why

当前 VSCode 编辑体验存在两类明显问题，直接影响 YAML DSL 的可维护性与“0 配置”上手体验：

1) **`$import` 无法跳转/悬浮**：用户在主 demand YAML 中使用 `$import` 复用 fragments 时，缺少 go-to-definition/hover，会导致读写成本高、片段来源难定位。

2) **YAML schema 误报（例如 Missing property `budget`）**：VSCode 的 YAML schema 校验不会展开 `$import`，因此在校验 `resources.books.*` 等 mapping 时看不到 fragment 中声明的 `kind`，触发 JSON schema `if/then` 的“kind 缺失误匹配”，造成错误红线。CLI (`scalim-cli yaml-dsl schema validate`) 会先做 imports expansion，所以能通过；编辑器却持续误报，导致信噪比下降。

## What Changes

- LSP：为 `$import` / `imports` 引用新增导航能力：
  - go-to-definition：从 `$import: <alias>.<path>` 跳转到对应 fragment YAML 文件中的目标 mapping（尽可能定位到 key 行）。
  - hover：展示 `$import` 解析后的来源（alias -> 文件路径）与目标 logical path（若可解析）。
- Schema：修复 `$import` 场景下的 JSON schema 误报：
  - 对所有以 `kind` 进行分支的 `if/then` 约束，要求 `if` 同时包含 `required: ["kind"]`，避免在 `kind` 缺失但 `$import` 存在时误触发。
  - 至少覆盖 `definitions.book`（修复 `xlsx_memory` 分支错误要求 `budget` 的场景），并扩展到其它同类模式（若存在）。
- 测试与文档：
  - 增加最小回归测试：覆盖 `$import` 的 LSP 跳转/hover 与 schema 误报修复。
  - 更新 VSCode/LSP 集成文档：说明 `$import` 导航能力与 schema 行为差异（编辑器不展开，但 schema 仍应对 `$import` 友好）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-lsp-server`: 增强 `$import`/`imports` 的 definition/hover 能力，以支持 fragments 导航。
- `yaml-dsl-schema`: 修复 `$import` 场景下 `if/then` 分支误触发，消除 VSCode schema 误报（例如 `budget` 缺失）。

## Impact

- 受影响代码：
  - `packages/scalim-yaml-dsl-lsp/`（definition/hover 光标抽取与解析逻辑）
  - YAML DSL schema 生成 SSOT（影响 `demand.gen.json` 等生成物；禁止手改 `*.gen.*`）
- 风险/约束：
  - VSCode 的 YAML extension 不展开 `$import` 是既定事实；修复策略应以“schema 在 `$import` 形态下不误报”为目标，而不是尝试让 YAML extension 支持 imports expansion。

