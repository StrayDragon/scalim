## Why

当前仓库中 `getattr` / `setattr` / `hasattr` 的使用已经扩散到多个核心目录,且缺少统一的显式门禁与例外机制.
这带来两个直接问题:

- 代码重构时,字段名/方法名变更无法被类型系统和静态检查覆盖,容易形成“改一处漏一处”的维护债.
- 审阅者无法快速区分“确属框架动态边界”与“本可静态化却沿用了动态写法”的调用点.

本变更先补齐一个独立、可运行、可审阅的 `dynattr` 扫描器,产出基线报告与 allow 机制,为后续接入 `just qa` 的强门禁提供可靠收口路径.

## What Changes

- 新增 `scripts/check-dynattr.py`,统一扫描 `src/scalim/` 中的 `getattr` / `setattr` / `hasattr`.
- 提供显式例外约定:
  - 行级 `# pragma: allow-dynattr <prefix>: <detail>`
  - 文件级 `# pragma: allow-dynattr-file <prefix>: <detail>`
- 报告必须输出位置、调用类型、属性表达式摘要与 allow/block 状态,便于分批重构.
- 先以“报告优先”方式建立基线,后续在基线收口后再接入 `just qa` 强门禁.

## Capabilities

### Modified Capabilities
- `testing-quality`: 质量门禁将具备对 `dynattr` 的显式盘点与逐步收紧能力

## Impact

- 受影响范围集中在 `src/scalim/` 和 `scripts/`.
- 第一阶段不改变运行时业务语义,主要新增治理工具与审阅基线.
- 第二阶段可在 allow/refactor 收口完成后将检查器并入 `quick-check-only-py` / `just qa`.
