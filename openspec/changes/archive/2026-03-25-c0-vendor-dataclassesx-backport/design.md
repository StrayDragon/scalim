## Context

`scalim` 运行时需要兼容 Python 3.6,而核心代码目前直接依赖 `dataclasses`（PyPI backport）来提供 `@dataclass` 等能力。该依赖在本仓库通过 `pyproject.toml` 的条件依赖引入,但当我们把 `src/scalim/` 镜像同步到下游旧工程的 `vendors/libs/scalim/` 时,下游环境往往并不具备同等的依赖安装/锁定能力,从而出现:

- 同步产物不自包含,运行时仍需要额外同步/安装 `dataclasses` backport；
- 在“同步第三方依赖代码”这个环节上容易发生人工改动与漂移,导致排查困难。

本变更希望把 `dataclasses` backport 作为 `scalim` 的内部 vendored 运行时代码,并统一由 `scalim` 自身引用,从而提升 vendors 同步场景的可重复性与可审计性。

约束:
- `src/scalim/` 运行时边界需要保持 Python 3.6 兼容。
- `src/scalim/` 内部在引用自身模块时必须使用相对导入,避免 `from scalim...` 绝对导入在 vendors 化场景下混入“另一份 scalim”。
- `src/scalim/*` 模块命名不得与标准库/常用库同名,避免 import 语义混淆与 shadowing 风险。
- docs/specs 需要保持可验证与可归档,不引入生成物手改风险。

## Goals / Non-Goals

**Goals:**
- 引入 `src/scalim/vendor/dataclassesx/` 作为内部 dataclasses backport 的唯一来源,并在 `src/scalim/` 内部统一引用该实现。
- 明确 vendoring 的来源版本与升级策略,保证后续可审计与可重复同步。
-（可选）评估并决定是否移除 `dataclasses;python_version<'3.7'` 这一运行时依赖,以避免把 backport 当作间接依赖暴露给调用方。

**Non-Goals:**
- 不在本变更中推进“所有第三方依赖的 vendoring/shim”。
- 不对外新增或推广新的公共 API（`dataclassesx` 作为内部实现边界,不作为用户功能宣传点）。
- 不改变 `legacy-vendors-sync` 的同步语义与脚本边界（同步仍只镜像本仓库的 `src/scalim/` 等资产）。

## Decisions

1. **以 `scalim.vendor.dataclassesx` 作为内部唯一 dataclasses 来源**
   - 方案: 在 `src/scalim/vendor/dataclassesx/` 放置 backport 实现,并将 `src/scalim/` 内所有 `from dataclasses import ...` 迁移为对 `vendor/dataclassesx` 的相对导入（例如 `from ..vendor.dataclassesx import ...`）。
   - 理由: 保证 vendors 同步产物自包含,并把 dataclasses 行为收敛为可控的内部实现边界。

2. **vendor 目录结构与导出面最小化**
   - 方案: `dataclassesx` 仅暴露 `dataclass`/`field`/`replace`/`asdict`/`fields`/`is_dataclass` 等当前 `scalim` 使用到的符号（可直接 re-export,但不额外包装）。
   - 理由: 降低未来升级/差异比对成本,避免引入不必要的兼容层与行为分叉。

3. **许可证与来源可审计**
   - 方案: 在 `src/scalim/vendor/dataclassesx/` 附带来源说明文件(如 `SOURCE.md`)记录:
     - 上游来源（PyPI `dataclasses` backport 或 CPython 对应版本文件）
     - 采用的上游版本号/commit
     - 本地改动点（若有）
   - 理由: vendoring 需要可追溯,否则后续升级与合规风险不可控。

4. **依赖策略（待实现时落地）**
   - 默认倾向: 移除 `pyproject.toml` 中 `dataclasses;python_version<'3.7'` 的运行时依赖,以避免间接依赖泄漏。
   - 若发现生态兼容性风险（调用方依赖 `scalim` 间接提供 `dataclasses`）,则在本变更中明确记录为 BREAKING 并给出迁移说明。

## Risks / Trade-offs

- [风险] vendored backport 与 stdlib dataclasses 在边界行为上存在差异 → [缓解] 以 `scalim` 现有使用面为验收基准,补充/强化相关单测并在 Python 3.6 环境跑通。
- [风险] vendoring 引入许可证/来源不清 → [缓解] 在 `dataclassesx` 目录内记录来源与版本,并在 QA 门禁中纳入 OpenSpec 校验与代码审阅检查点。
- [风险] 大范围 import 路径迁移带来循环依赖或 import-time 成本变化 → [缓解] 迁移时优先保持“同级/相对导入 + 最小化 re-export”,并逐步在受影响模块运行基础测试套件验证。
