## Why

在金融报表与对账类场景中,`float` 的二进制浮点语义会引入不可接受的精度风险(例如 `0.1 + 0.2 != 0.3`),并且这种误差往往发生在“看起来很简单”的派生字段计算与阈值判断里,导致线上结果难以解释与复现。

Scalim 已经支持在源字段上通过 `value_cast: decimal` 将 `float` 安全转换为 `Decimal(str(float))` 来避免二进制展开,但 YAML DSL 的顶层派生字段 `fields.*.compute/call_by` 在运行时仍会拒绝 `Decimal` 作为返回值,迫使用户回退到 `float/str` 口径,从而无法在 YAML 计算链路里端到端保持十进制精度。与此同时,即使允许用户手写 `Decimal(...)`,也存在 `Decimal(0.1)` 的二进制展开陷阱与 `Decimal + float` 的混用错误,需要一个更安全、显式且可控的入口。

## What Changes

- 放宽 YAML 派生字段类型边界: `fields.*.(compute|call_by)` 允许返回 `decimal.Decimal`(与框架 `FieldValue` 值域对齐),并在框架内部继续以 `Decimal` 传递。
- 在 compute 安全表达式引擎中新增 builtin `dec(x)` 作为“安全十进制转换”入口:
  - 对 `float` 使用 `Decimal(str(x))`,避免 `Decimal(float)` 的二进制精确展开。
  - 覆盖类型: `None/bool/int/float/str/Decimal`。
  - 对非有限 `float`(`NaN/Inf`)与非法字符串,行为为 fail-fast(抛出 `ValueError`)。
- 明确 `dec(x)` 作为 `SecureComputeEngine` builtin 的可见范围:
  - 顶层派生字段 `fields.*.compute`
  - 任何其它复用同一 compute 安全引擎的 YAML 表达式位置(例如 `outputs.where` 与 aggregate post-compute)
- 明确本 change 的职责边界:
  - 本 change 负责“`Decimal` 如何在 YAML compute/call_by 中被安全地产生并被 runtime 接受”
  - 不负责 `xlsx_memory` workflow internal path 的 typed preservation；该能力由独立的 `xlsx-memory-type-preservation` change 约束

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `field-compute`: 放宽顶层派生字段 `compute/call_by` 的返回值边界以接受 `Decimal`,并为 compute 安全引擎新增 `dec(x)` 语义。

## Impact

- 受影响代码主要包括 `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`, `src/scalim/dsl/by_yaml/_internal/config_parsing/security.py`, `src/scalim/dsl/by_yaml/runtime/_internal/conversion_lookup.py`, 以及相关 YAML runtime/安全引擎测试。
- 受影响规范主要为 `openspec/specs/field-compute/spec.md`。
- 不引入新三方依赖(`decimal` 为标准库),核心运行时仍需兼容 Python 3.6。
- 若 docs/spec indexes 或 injected blocks 需要刷新,应运行 `just gen-docs`,而不是手改生成物；共享前需运行 `just openspec-check`。
