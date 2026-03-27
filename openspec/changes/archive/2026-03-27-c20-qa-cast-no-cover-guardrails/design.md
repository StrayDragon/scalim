## Context

`dynattr` 提案已经证明,这类“语言逃逸点”如果没有独立清点工具和显式 allow 约束,最终会演变成 review 无法收口、重构无法信任的长期维护债.
`cast(...)` 与 `# pragma: no cover` 现在处于相同状态:

- `cast` 往往掩盖了缺失的运行时契约、过宽的返回类型或跨层不清晰的接口边界.
- `# pragma: no cover` 在少数兼容性和抽象基类场景是合理的,但一旦无门槛扩散,会直接削弱 `100%` 覆盖门禁.
- 仓库运行时代码仍需兼容 `Python 3.6`,因此任何治理方案都不能依赖仅在高版本 typing 里可用的新特性;兼容类必须继续走 vendor shim.

## Goals / Non-Goals

**Goals:**
- 为 `cast` 与 `# pragma: no cover` 建立独立、可重复运行的基线报告工具.
- 让所有例外都变成局部、显式、带理由的审阅对象.
- 在 `justfile` 中提供稳定入口,为后续接入 `quick-check-only-py` / `just qa` 做准备.
- 通过收口过程反向暴露“应补类型契约/应补测试”的真实热点,而不是继续堆 `cast`.

**Non-Goals:**
- 本提案不试图一次性消灭所有现有 `cast` 或 `# pragma: no cover`.
- 本提案不直接解决全部循环导入或模块分层问题;局部导入仍作为现阶段的最小侵入修复手段.
- 本提案不引入通用“万能质量扫描框架”;优先保持脚本独立、简单、可 review.

## Decisions

- **工具形态**: 采用两个独立脚本而不是一个“全能大检查器”:
  - `scripts/check-cast-usage.py`
  - `scripts/check-no-cover.py`
  这样更容易 review、调试和按主题渐进接入 `justfile`.
- **扫描策略**:
  - `cast` 检查需要识别 `typing.cast`、`typing_extensions.cast`、直接导入的 `cast` 以及常见别名.
  - `no cover` 检查以词法/注释为主,识别所有 `# pragma: no cover` 位置,并要求同时具备配套的治理标记与理由.
- **例外机制**: 与 `dynattr` 对齐,采用局部 pragma 治理,例如:
  - `# pragma: allow-cast <reason>`
  - `# pragma: allow-no-cover <reason>`
  - 必要时允许文件级 `allow-*-file`,但仅限整文件都承担兼容/框架职责的模块.
- **SSOT 命令**:
  - `just report-cast-usage`
  - `just report-no-cover`
  - `just check-cast-usage`
  - `just check-no-cover`
  后续再组合成更高层的 QA 入口.
- **兼容边界**: `src/scalim/` 中若实现需要 `Protocol`、`runtime_checkable` 等兼容 typing 语义,必须使用 vendor shim,避免在 `Python 3.6` 边界上引入新的运行时/类型检查失败.
- **渐进接入**: 先报告、再收敛、最后 gate;避免像历史 `dynattr` 一样在基线未分类时直接把 `just qa` 打爆.

## Risks / Trade-offs

- **[风险] 规则过严导致噪声过大** → 先以报告模式建立基线,再逐步把“确属必要”的点标记为 allow.
- **[风险] `cast` 扫描误报导入别名或阴影变量** → 用 AST 解析导入来源与作用域,避免只做字符串匹配.
- **[风险] `no cover` 扫描与 coverage 口径不一致** → 只做“是否存在 pragma 与是否有理由”的治理检查,不重新实现 coverage 语义.
- **[风险] 继续出现局部导入、`cast`、兼容 shim 三者混杂** → 在 rollout 阶段优先消除“仅为偷懒存在的 `cast`”,把真正的模块结构问题单独暴露出来.

## Migration Plan

1. 先生成 `cast` 与 `no cover` 的全量报告.
2. 分类为“应静态化/应补测试”与“必须保留并 allow”.
3. 增加 `just` 入口,先提供 report/check 命令.
4. 基线收敛后再将 `check-*` 命令接入 `quick-check-only-py` / `just qa`.

## Open Questions

- `cast` 是否需要进一步区分“测试代码”和“运行时代码”的严格级别.
- `# pragma: no cover` 是否允许通过“同一行带理由”满足治理,还是必须引入单独 allow pragma.
- 是否需要在后续第二阶段把“局部导入”也纳入同类治理,作为模块图健康度的补充信号.
