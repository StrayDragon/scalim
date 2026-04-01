## Why

在金融报表与对账类场景中,`float` 的二进制浮点语义会引入不可接受的精度风险(例如 `0.1 + 0.2 != 0.3`),并且这种误差往往发生在“看起来很简单”的派生字段计算与阈值判断里,导致线上结果难以解释与复现。

Scalim 已经支持在源字段上通过 `value_cast: decimal` 将 `float` 安全转换为 `Decimal(str(float))` 来避免二进制展开,但 YAML DSL 的派生字段 `fields.*.compute/call_by` 在运行时仍会拒绝 `Decimal` 作为返回值,迫使用户回退到 `float/str` 口径,从而无法端到端保持十进制精度。与此同时,即使允许用户手写 `Decimal(...)`,也存在 `Decimal(0.1)` 的二进制展开陷阱与 `Decimal + float` 的混用错误,需要一个更安全、显式且可控的入口。

## What Changes

- 放宽 YAML 派生字段类型边界: `fields.*.(compute|call_by)` 允许返回 `decimal.Decimal`(与框架 `FieldValue` 值域对齐),并在框架内部继续以 `Decimal` 传递。
- 在 compute 安全表达式引擎中新增 builtin `dec(x)` 作为“安全十进制转换”入口:
  - 目标: 将 `float` 统一按 `Decimal(str(x))` 转换,避免 `Decimal(float)` 的二进制精确展开。
  - 覆盖类型: `None/bool/int/float/str/Decimal`。
  - 对非有限 `float`(`NaN/Inf`)与非法字符串,行为为 fail-fast(抛出 `ValueError`),避免静默吞错导致财务结果不可追溯。
- 多级表达式位置一致可用: 由于 `dec` 作为 `SecureComputeEngine` 的 builtin,它将自动出现在所有使用该引擎的 YAML 表达式位置,包括但不限于:
  - demand 派生字段 `fields.*.compute`
  - outputs 的 `where` 过滤条件(若使用 compute 引擎)
  - outputs.aggregate 的派生字段 `compute`(聚合后派生字段)
- 规范与文档同步: 以 `openspec/specs/field-compute/spec.md` 为 SSOT 增量更新 `dec()` 的语义、示例与派生字段 `Decimal` 返回值行为;不涉及任何 `*.gen.*` 生成物或 AUTOGEN 注入区块。

### Expected Behavior (Contract)

- `dec(0.1)` MUST 产生 `Decimal("0.1")`(而非 `Decimal("0.100000000000000005...")`)。
- 当 `fields.*.compute` 返回 `Decimal` 时,系统 MUST 接受该值并写入运行时上下文,下游计算/输出可继续消费该 `Decimal`。
- 当 `fields.*.call_by` 返回 `Decimal` 时,系统 MUST 接受该值并写入运行时上下文。
- `dec(x)` SHOULD 被视为显式 opt-in: 框架不会在 compute 中隐式把所有 `float` 自动替换为 `Decimal`(避免语义突变与潜在性能回退)。

### Before / After Examples

Before (现状: float 误差或 Decimal 被拒绝):

```yaml
main_source:
  source_id: orders
  loader: myapp.loaders:load_orders
  fields:
    amount: {extract: amount}  # DB 读出来可能是 float
    tax: {extract: tax}

fields:
  total:
    compute: "amount + tax"
```

问题:
- 若 `amount=0.1` 且 `tax=0.2`,`total` 可能得到 `0.30000000000000004`。
- 若用户尝试 `compute: "Decimal(str(amount)) + Decimal(str(tax))"`,当前实现会在运行时拒绝 `Decimal` 返回值。

After (提案目标: 显式十进制口径 + 可传递 Decimal):

```yaml
main_source:
  source_id: orders
  loader: myapp.loaders:load_orders
  fields:
    amount: {extract: amount, value_cast: decimal}
    tax: {extract: tax, value_cast: decimal}

fields:
  total:
    compute: "dec(amount) + dec(tax)"
```

预期:
- `amount/tax` 可被 `value_cast: decimal` 预先安全十进制化。
- 即便上游仍返回 `float`,`dec(...)` 也能在 compute 内安全转换,得到稳定可解释的十进制结果 `Decimal("0.3")`。

### Validation / Verification

- 单元测试:
  - `dec(None/bool/int/Decimal)` 的恒等/按约定转换行为。
  - `dec(float)` 对有限值使用 `Decimal(str(x))` 的精确性。
  - `dec(NaN/Inf)` 与 `dec("not-a-number")` 的 fail-fast 行为。
- 集成测试(YAML):
  - `fields.*.compute` 返回 `Decimal` 时,整条执行链路不报错且输出中保留 `Decimal`。
  - `fields.*.call_by` 返回 `Decimal` 时同上。
  - 覆盖“派生字段作为 relation join key”的 pre-ref 约束不变(该提案不改变关系规划语义)。
- 回归验证:
  - 不使用 `dec`/不返回 `Decimal` 的既有 YAML 行为保持不变。
  - 确认常见 sinks(内存 rows/CSV/pandas)在出现 `Decimal` 值时行为可接受(例如 pandas 可能退化为 object dtype,需在文档中明确)。

### Alternatives (Pros/Cons)

- 方案 1: 维持现状,要求用户手写 `Decimal("0.1")` 或在 loader 侧自行处理
  - 优点: 框架零改动
  - 缺点: 当前 YAML 派生字段返回 `Decimal` 会被拒绝;且 `Decimal(0.1)` 等写法是高频陷阱,难以在团队规模上治理
- 方案 2: 本提案(推荐): 放宽派生字段允许 `Decimal` + 提供显式 `dec()` helper
  - 优点: blast radius 小,语义显式可控,与现有 `value_cast: decimal` 策略一致;能端到端保留十进制精度
  - 缺点: 需要用户显式采用 `dec(...)`(不会自动修正所有 float);`Decimal` 在 pandas 等下游可能产生 dtype/性能影响,需要文档明确
- 方案 3: compute AST 自动重写(将 float literal 或 float 入参隐式替换为 Decimal)
  - 优点: 用户最省心
  - 缺点: 隐式语义变化难以预测,可能带来兼容性与排障成本;易出现“同一表达式在不同数据形态下类型不同”的惊讶效应
- 方案 4: 框架入口全局 float->Decimal(在 loader 结果进入框架时统一转换)
  - 优点: 从源头杜绝 float 传播
  - 缺点: blast radius 极大,会影响所有数值语义/性能/缓存与外部集成;不符合“低优先级可延期”的推进方式

## Capabilities

### New Capabilities

- (none): 本变更通过扩展既有能力实现,不引入新的 capability 目录

### Modified Capabilities

- `field-compute`: 派生字段 `compute/call_by` 的返回值允许 `Decimal`,并新增 compute builtin `dec(x)` 的规范语义与示例。

## Impact

- 受影响代码(高层级):
  - YAML DSL compute 安全引擎(`SecureComputeEngine`)的 builtin functions 集合
  - YAML runtime 派生字段结果类型 gate(允许 `Decimal`)
- 输出与生态影响:
  - `Decimal` 将成为 YAML 派生字段可选的稳定输出类型;部分下游(例如 pandas)可能以 object dtype 承载,需要在文档/示例中明确推荐做法(例如保持 Decimal 到最终输出,或在最后一步显式格式化为字符串)。
- 依赖与兼容性:
  - 不引入新三方依赖(`decimal` 为标准库)。
  - 核心运行时仍需兼容 Python 3.6。
