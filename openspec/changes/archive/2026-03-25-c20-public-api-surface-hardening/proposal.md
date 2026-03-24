## Why

当前仓库已经逐步形成一批“看起来能导入/能调用”的 YAML DSL 与库级入口，但哪些是稳定公共表面、哪些只是内部实现路径，边界仍不够硬。结果是下游和仓库内示例容易误依赖内部模块；一旦后续继续重构，就会把实现细节误升级成长期兼容负担。

同时，公开入口中仍保留 `template_sandbox=legacy` 这类显式不安全能力。它虽然已有 warning，但仍把“可放宽执行边界”的决策暴露在默认官方 API 上，不符合这轮“严格约束、严格内聚、避免迭代破坏”的目标。

## What Changes

- 新增一套“公共表面治理”规范，明确哪些模块/符号属于稳定公开入口，哪些路径仅是内部实现细节，不得在文档、skills、examples 和回归测试里作为官方用法继续扩散。
- 收敛 YAML DSL 与库侧公开入口的承诺面：以显式白名单方式定义稳定入口集合，并把 `__all__` / import smoke / examples gate 作为回归门禁的一部分。
- **BREAKING** 从官方公开入口移除 `template_sandbox=legacy` 能力；公共 API 仅保留 safe sandbox。任何不安全放宽能力若仍需存在，后续必须转入显式 `unsafe` 语义的内部或专用入口，而不是继续挂在默认 facade 上。
- 保持当前 `run/compile` 对 `sink`、`components`、`output_composition` 等受控扩展点的支持，不把这次 change 扩大为执行能力删减；本轮重点是“公开承诺面收敛”和“unsafe 默认面收紧”。
- 假设更高优先级 change 会先合并，并以其结果为前提编写本提案：
  - `framework-metadata` 已先提供最小顶层 metadata 入口；
  - `workflow-layering-refactor` 已先固定 workflow 稳定入口与内部 runtime 边界；
  - 本 change 不重复定义上述能力，只在其基础上补公共表面治理与门禁。

## Capabilities

### New Capabilities
- `public-api-surface-governance`: 定义稳定公开入口、内部实现路径、文档/examples/skills 的引用约束，以及 public-surface 回归门禁。

### Modified Capabilities
- `module-organization`: 将“显式模块路径而非顶层杂货铺”进一步细化为“稳定公开路径白名单 + 内部路径非契约”治理规则。
- `dsl-runtime-structure`: 收紧 YAML DSL 官方 facade 的公开承诺面，并将 `template_sandbox=legacy` 从官方运行入口移除。
- `yaml-template-vars-sandbox`: 将 legacy sandbox 从公共 opt-in 调整为非公共能力；官方入口只允许 safe sandbox。
- `yaml-dsl-workflow`: 在 `workflow-layering-refactor` 已合并的前提下，补充 workflow 公开入口与内部实现路径的使用约束。
- `marimo-example-public-api-suite`: 扩展公开 API suite，使其覆盖稳定入口导入与非官方路径禁用回归。

## Impact

- 未来实现将主要影响 `src/scalim/__init__.py`、`src/scalim/dsl/by_yaml/**`、示例/skills/docs 中的导入示例，以及 public API gate 测试。
- SSOT 在 OpenSpec 主规范：`openspec/specs/**/spec.md`；本 change 只创建 `openspec/changes/c20-public-api-surface-hardening/**` 工件，不直接实现代码逻辑。
- 文档与 examples 若引用了内部实现路径，需要在后续实现阶段统一升级到稳定入口；`.gen.*` 文件与 `AUTOGEN` 注入区块仍不得手改。
- 由于本 change 含 BREAKING public API 收紧，仓库内测试、示例与技能文档会在实现阶段一次性升级，不做兼容 shim。
