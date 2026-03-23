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

### 1) 在高层入口引入 explicit trusted-mode（而不是继续依赖 `"*"`）

**决策：**

- 为 `RunOptions` 与 `scalim.dsl.by_yaml.run/compile` 增加显式开关（命名建议：`trusted_mode: bool = False` 或 `resolver_trusted_mode: bool = False`）。
- trusted-mode 的作用是“允许放宽 resolver 约束”，并成为 `"*"` 能否使用的唯一 gate。

**备选：**

- 继续把 `"*"` 当作语法糖，仅靠日志 warning：无法防止误用，且在默认无日志/被过滤时不可见。
- 在更低层 resolver 内部偷偷“修正”配置：会让调用方难以理解真实安全边界。

### 2) `"*"` 的处理语义：默认拒绝；trusted-mode 下允许（但仍强约束组合）

**决策：**

- 当 `trusted_mode=false` 时：
  - `allowed_modules` 或 `allowed_functions` 中出现 `"*"` → MUST fail-fast（错误信息包含：为什么危险、如何迁移）。
- 当 `trusted_mode=true` 时：
  - 允许 `allowed_modules={"*"}`（或等价“全放开模块”的表达），并输出强 warning（至少 warning 日志；可选诊断事件）。
  - `allowed_functions` 在 trusted-mode 下必须为 `None`（或空集合）；若给出任何值则 fail-fast（避免“部分约束仍生效”的错觉）。

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

### 4) denylist-only（不安全）模式：重命名 + 双确认 gate + 禁止与 allowlist/trusted-mode 混用

**决策：**

- 将 `allow_unsafe_resolver` 改为更难误解的命名（建议：`unsafe_denylist_only_resolver` / `denylist_only_resolver`，最终命名以实现时为准）。
- 启用该模式必须同时满足：
  - 参数显式为 `True`
  - 且存在额外确认信号（推荐环境变量，例如 `SCALIM_UNSAFE_DENYLIST_ONLY=1`）
- 与其它安全配置互斥：
  - denylist-only 与 allowlist / trusted-mode 同时出现 → fail-fast（避免“我开了 allowlist 其实没生效”的错觉）

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
- [可用性] denylist-only 加“双确认”会增加测试/演示成本 → 缓解：环境变量方式对 CI/本地都容易配置，且能显式化风险边界。
- [误解] trusted-mode 的含义可能被理解为“信任 YAML 输入”而非“信任 resolver 放宽” → 缓解：命名倾向 `resolver_trusted_mode`；并在 warning 文案中明确说明“resolver allowlist 放宽/全放开”。

## Migration Plan

1. 在实现中先补齐 fail-fast 校验（wildcard 禁用、互斥规则、denylist-only 双确认）。
2. 更新高层入口（`RunOptions` + `scalim.dsl.by_yaml.run/compile`）暴露 trusted-mode，并更新 CLI/help 文案与示例。
3. 增加回归测试：
   - wildcard 默认拒绝
   - trusted-mode + wildcard 允许且强告警
   - denylist-only 缺确认信号必失败；具备确认信号才允许
4. 运行 `just openspec-check` 与 `just qa` 作为最终门禁。

## Open Questions

- trusted-mode 的最终命名选择：`trusted_mode` vs `resolver_trusted_mode`（倾向后者以避免歧义）。
- denylist-only 的环境变量命名与值约定（`SCALIM_UNSAFE_DENYLIST_ONLY=1` vs 更长的 `SCALIM_ENABLE_UNSAFE_DENYLIST_ONLY_RESOLVER=1`）。
