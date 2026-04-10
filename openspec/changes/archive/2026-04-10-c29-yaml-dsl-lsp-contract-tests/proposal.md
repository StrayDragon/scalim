## Why

我们即将进行 `c30-yaml-dsl-compiler-frontend` 级别的大型重构（将 YAML DSL 的 editor semantics 收敛为主框架编译前端 SSOT，并显式拆分 runtime linking / execution）。

这类重构的主要风险不是“功能做不出来”，而是：

- **回归难以察觉**：LSP 行为受文本位置/范围、imports 展开、提示/降级策略影响很大，内部实现一换就可能出现细微但破坏体验的差异（例如 range 偏移、definition 多 location 排序、completion 候选排序/去重）。
- **缺少稳定基准**：如果没有“协议级的黑盒基准”，我们只能靠 notebooks/人工对拍或零散的 unit tests 来判断是否保持了用户侧行为，成本高且容易漏。

因此在推进 c30 之前，需要一个前置变更：为当前 `packages/scalim-yaml-dsl-lsp` 的“已存在能力”建立 **集成/契约测试**，把现有行为固化为新基准，便于后续大胆重构、快速迭代。

## What Changes

- 增加一套 **YAML DSL LSP contract tests（协议级集成测试）**：
  - 以 `scalim-yaml-dsl-lsp serve`（stdio）作为黑盒入口；
  - 用最小 JSON-RPC/LSP client 驱动 `initialize/didOpen/definition/hover/completion/codeAction/executeCommand`；
  - 对关键返回结果进行 **稳定化(normalize)** 并做 **golden snapshot** 对拍（或等价的结构化断言）。
- 将现有的 LSP 相关测试用例收敛为“场景化 suite”（减少重复 harness、减少 one-off 手写 offset），补齐未覆盖的关键路径，使其成为后续 refactor 的“红线”。
- 为后续重构提供“可执行验收口径”：
  - 当 c30 将语义实现迁移到编译前端 SSOT 后，这套 contract tests 不应大规模改写，只允许出现 **显式的行为变更**（并通过更新 golden + 变更说明审查）。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-lsp-server`: 为已有 completion/hover/definition/diagnostics/code actions 的行为建立协议级基线测试。
- `testing-quality`: 将 YAML DSL LSP 的测试重心从“内部实现细节”进一步迁移到“接口行为”。

## Impact

- 主要改动范围预计在 `tests/` 与 `tests/fixtures/`（增加/重构 LSP integration suite 与 fixtures）。
- 运行时/主框架行为不变（不改 `src/scalim/**` 的生产逻辑），但 CI 用时会略有增加：
  - 通过减少 debounce、复用 server 进程（按 suite 级别复用）等方式把增量控制在可接受范围。
- 风险：
  - 契约测试天然更“脆”，需要良好的 normalize/snapshot 策略与清晰的更新流程（见 design）。
