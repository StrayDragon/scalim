## Context

by_yaml 的 Python 引用 resolver 用于解析 `call_by` / loader 引用 / retry `should_retry` 等“Python 可调用对象引用”。当前实现存在多处“误配置即失效”的脚枪：

- allowlist 通配符 `"*"` 是隐式语法糖：`allowed_modules={"*"}` / `allowed_functions={"*"}` 会把约束直接放宽成“全放开”，仅靠日志 warning 提醒（很容易被忽略）。
- `allowed_functions={"*"}` 会旁路模块约束：`ResolverPolicy.check()` 对函数侧先短路返回，导致即使提供了 `allowed_modules={"myapp"}` 也会变成“允许任意模块/函数”。
- `ConfigToIRConverter(allow_unsafe_resolver=True)` 在缺失 allowlist 时会直接落到 `SecurePythonReferenceResolver()`（denylist-only），属于高危 escape hatch，且当前缺少“二次确认”硬门槛。

约束：

- `src/scalim/` 运行时需兼容 Python 3.6。
- 对外入口主要为 `scalim.dsl.by_yaml.run/compile`（`RunOptions.allowed_modules/allowed_functions`）。
- 本变更属于安全语义收敛：允许 BREAKING（默认 fail-fast），但必须给出可操作迁移提示与强告警策略。

## Goals / Non-Goals

**Goals:**

- 默认拒绝 `"*"` 通配符：除非显式启用 trusted-mode，否则 `"*"` 一律 fail-fast，并输出可复制的迁移建议。
- 引入显式 trusted-mode（或等价开关）：让“全放开/可信输入”场景仍然可用，但必须 loud warning（日志/诊断）。
- 消除 `allowed_functions={"*"}` 旁路模块 allowlist 的脚枪：禁止该配置组合，并提供等价替代方案。
- 将 denylist-only（不安全）模式改为“显式 + 二次确认”：避免无意开启并把风险显式化。

**Non-Goals:**

- 不在本变更中实现模板 sandbox、YAML 路径 allow-roots 等其它安全议题（它们有独立 changes）。
- 不改变引用语法（class-style/dotted-style）、也不调整 `SecurePythonReferenceResolver` 的危险模块 denylist 内容。
- 不引入新的第三方 sandbox 依赖。

## Decisions

### 1) 用单一枚举表达 resolver 安全模式（SSOT：避免散落 bool）

**决策：**

- 为 `RunOptions` 与 `scalim.dsl.by_yaml.run/compile` 增加显式的 enum 选项（命名：`resolver_trusted_mode`），用于表达 resolver 的安全模式，而不是用多个 bool/字符串拼接语义。
- `resolver_trusted_mode` 取值（最终以实现为准，但必须是枚举而不是自由文本）：
  - `strict_allowlist`（默认）：必须提供 allowlist 且禁止 `"*"`。
  - `trusted_allow_all_modules`：允许放宽到“允许任意模块”（仍保持引用语法与 denylist 检查），必须强告警。
  - （可选/后置）`denylist_only`：若未来仍要保留 denylist-only，必须是单独的 unsafe entrypoint（本变更倾向直接移除现有逃逸口子，见决策 4）。
- 任何非默认模式 MUST 强告警（稳定前缀 + `k=v` 字段），并在错误/告警中明确说明“哪些约束已被放宽/关闭”。

**备选：**

- 继续把 `"*"` 当作语法糖，仅靠日志 warning：无法防止误用，且在默认无日志/被过滤时不可见。
- 在更低层 resolver 内部偷偷“修正”配置：会让调用方难以理解真实安全边界。

### 2) `"*"` 的处理语义：默认拒绝；仅在 trusted mode 下允许（并限制组合）

**决策：**

- 当 `resolver_trusted_mode=strict_allowlist` 时：
  - `allowed_modules` 或 `allowed_functions` 中出现 `"*"` → MUST fail-fast（错误信息包含：为什么危险、如何迁移）。
- 当 `resolver_trusted_mode=trusted_allow_all_modules` 时：
  - 允许 `allowed_modules={"*"}`（或等价“全放开模块”的表达），并输出强 warning（至少 warning 日志；可选诊断事件）。
  - `allowed_functions` 在该模式下必须为 `None`；若给出任何值则 fail-fast（避免“部分约束仍生效”的错觉）。

**关键可用性说明（避免过度限制用户）：**

- 若用户想“允许某些模块内任意函数”，推荐只配置 `allowed_modules={"myapp.loaders"}`，并 **不设置** `allowed_functions`（这本就是现有语义，且比 wildcard 更安全、更清晰）。

### 3) 禁止 `allowed_functions={"*"}`（以及其与 `allowed_modules` 的混用）

**决策：**

- `allowed_functions` 出现 `"*"` 一律拒绝（即使同时设置了 `allowed_modules`）。
- 错误信息必须包含替代方案：
  - “想做模块约束”→ 移除 `allowed_functions={"*"}`，仅使用 `allowed_modules`
  - “想全放开”→ 使用 trusted-mode（而不是混合配置）

**理由：**

`allowed_functions={"*"}` 当前的真实含义是“允许任意函数”，并且会旁路模块约束；它不提供任何“比仅设置 allowed_modules 更细粒度但仍安全”的价值，且误用概率极高。

### 4) denylist-only（不安全）模式：倾向移除 escape hatch（严格失败 + 友好提示）

**决策：**

- 倾向直接移除 `ConfigToIRConverter(allow_unsafe_resolver=...)` 逃逸口子，并统一为：
  - 缺少 allowlist 一律严格失败（fail-fast）
  - 错误信息提供可复制迁移建议（例如“如何构造 allowlist”“如何在可信场景使用 trusted mode”）
- 若未来确有内部/测试需要 denylist-only：
  - 必须以 **单独的 unsafe entrypoint** 提供（命名明确包含 `unsafe`）
  - MUST NOT 通过环境变量隐式改变框架行为（避免“外部环境注入改变安全语义”的不可控面）
  - MUST 与 allowlist/trusted-mode 互斥并 fail-fast（避免“看起来安全其实不安全”的错觉）

### 5) 强告警与可诊断错误（默认 fail-fast + 可复制迁移指引）

**决策：**

- 任何进入 trusted-mode/denylist-only 的路径必须产生强告警：
  - 至少 warning 日志（带稳定前缀/label，便于 grep/过滤）
  - 可选：通过 observability hub 发出一次 `diagnostic_warning`（但不得依赖其可见性作为唯一告警通道）
- fail-fast 的错误消息必须包含：
  - 触发的配置点（哪个参数/哪种组合）
  - 为什么危险（脚枪语义解释）
  - 如何修复（推荐替代方案的最小示例）

## Risks / Trade-offs

- [BREAKING] 既有依赖 `"*"` 的调用方会直接报错 → 缓解：错误信息给出明确迁移路径（trusted-mode 或显式 allowlist），并在文档/CLI help 中同步强调。
- [可用性] 移除 denylist-only 会增加测试/演示成本 → 缓解：提供更清晰的 allowlist 示例与错误提示；可信场景通过 trusted mode 显式放宽。
- [误解] trusted-mode 的含义可能被理解为“信任 YAML 输入”而非“信任 resolver 放宽” → 缓解：命名倾向 `resolver_trusted_mode`；并在 warning 文案中明确说明“resolver allowlist 放宽/全放开”。

## Migration Plan

1. 在实现中先补齐 fail-fast 校验（wildcard 禁用、互斥规则、trusted-mode 组合约束）。
2. 更新高层入口（`RunOptions` + `scalim.dsl.by_yaml.run/compile`）暴露 `resolver_trusted_mode`（enum），并更新错误/告警文案与示例。
3. 增加回归测试：
  - wildcard 默认拒绝
  - trusted-mode + wildcard 允许且强告警
  - `allowed_functions={"*"}` 必须 fail-fast
4. 运行 `just openspec-check` 与 `just qa` 作为最终门禁。

## Open Questions

- resolver 安全模式的命名与形态：`trusted_mode` vs `resolver_trusted_mode` vs `resolver_security_mode`？  
> 统一为 `resolver_trusted_mode`，并且用一个 enum 表达各个处理，并且有合理的安全的默认值（`strict_allowlist`）。
- denylist-only（不安全）是否仍要保留？如果保留，如何 gate？  
> 不建议有任何环境变量注入修改框架处理行为和能力；倾向直接严格失败并给出友好提示。若未来确需保留，必须是显式参数/显式入口且强标注 `unsafe`。
