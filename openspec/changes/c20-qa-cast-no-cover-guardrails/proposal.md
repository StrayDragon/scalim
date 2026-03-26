## Why

当前仓库里 `cast(...)` 与 `# pragma: no cover` 的使用已经超出“局部例外”范围,开始系统性削弱类型系统与覆盖率门禁的可信度.
这会带来三个直接问题:

- 审阅者很难区分“类型系统确实表达不了”与“用 `cast` 快速绕过约束”的场景.
- `# pragma: no cover` 可能把真实可测试分支静默排除,导致 `100%` 覆盖门禁失去约束力.
- 当前缺少统一的脚本、`just` 入口与显式例外约定,无法像 `dynattr` 一样先建立基线、再逐步并入 `just qa`.

现在补齐这套门禁,可以把“类型逃逸”和“覆盖逃逸”收敛为显式、可审阅、可渐进收口的治理流程.

## What Changes

- 新增针对 `cast(...)` 的独立扫描与报告入口,清点 `src/scalim/` / `tests/` 中的 `cast` 使用.
- 新增针对 `# pragma: no cover` 的独立扫描与报告入口,要求所有例外都带显式理由并可审阅.
- 为两类逃逸点定义与 `dynattr` 对齐的局部 allow 约定,默认高严格、例外必须显式说明原因.
- 在 `justfile` 中增加对应的 SSOT 命令入口,先用于报告/收口,再准备接入 `quick-check-only-py` / `just qa`.
- 明确运行时兼容边界: `src/scalim/` 中涉及 `Protocol` 等兼容类型时,必须继续使用 `src/scalim/vendor/compact/typing_extensionsx.py` 提供的兼容入口,避免破坏 `Python 3.6` + 低版本 `typing_extensions` 约束.

## Capabilities

### Modified Capabilities
- `testing-quality`: 质量门禁将新增对 `cast` 与 `# pragma: no cover` 的显式盘点、理由约束与渐进式 QA 接入能力

## Impact

- 受影响代码主要位于 `scripts/`、`justfile`、`tests/` 与少量需要先行静态化的 `src/scalim/` 模块.
- 本变更的 SSOT 以 `scripts/` 中的检查脚本和 `justfile` 命令为准;若后续补充文档,应通过既有文档生成入口维护,避免手工复制规则描述.
- 第一阶段以“报告 + 分类 + 局部收敛”为主,不立即强行阻断所有现有命中.
