## Context

当前仓库在“十进制值如何进入 runtime”这条链路上存在不一致:

- `value_cast: decimal` 已经支持把源值安全转换为 `Decimal`
- `SecureComputeEngine` 已经允许 `Decimal("0.1")` 这类表达式
- 但顶层派生字段 `fields.*.compute/call_by` 的 runtime 类型 gate 仍拒绝 `Decimal`

结果是:

1. 用户在 YAML 派生字段里明明已经写出正确的十进制表达式,却会在 runtime 被“unsupported type”拦下
2. 用户被迫退回 `float` 或 `str` 口径,把本应在 YAML 内部收敛的精度语义外溢到 loader/Python 侧
3. 同一个仓库里已经存在 `Decimal` 相关能力,但对不同 YAML 表达式入口的接受规则不一致

同时,我们已经把 `xlsx_memory` 的 typed preservation 单独拆到了 `xlsx-memory-type-preservation` change 中。该 change 负责“值已经是 `FieldValue` 后如何在 workflow internal path 里不丢”,而不是“值如何在 YAML 计算里被产生”。因此本 design 必须把两者边界保持清楚,避免 scope 膨胀。

约束:

- Python 3.6 runtime 兼容
- 不引入全局 `float -> Decimal` 隐式重写
- 不改变未使用 `Decimal` / `dec(...)` 的既有 YAML 行为
- 不把 `.xlsx` 导出/round-trip 类型保真纳入本 change
- SSOT 为 `openspec/specs/field-compute/spec.md` 与本 change 下工件; 无需手改任何 `*.gen.*` 或 AUTOGEN 注入区块

## Goals / Non-Goals

**Goals:**
- 允许顶层派生字段 `fields.*.compute` 返回 `Decimal`
- 允许顶层派生字段 `fields.*.call_by` 返回 `Decimal`
- 提供安全、显式的 `dec(x)` helper,统一 `float -> Decimal(str(x))` 入口
- 让所有复用 `SecureComputeEngine` 的 YAML 表达式位置共享相同的 `dec(x)` builtin 语义
- 明确 `Decimal` 的“生产职责”归属本 change,而 `xlsx_memory` typed preservation 归属独立 change

**Non-Goals:**
- 不对所有 `float` 做全局隐式 `Decimal` 化
- 不自动改写用户表达式 AST
- 不负责 `xlsx_memory` / `sheetbook` / workflow-managed artifact 的 typed preservation
- 不承诺 `.xlsx` 文件格式的 Python 类型 round-trip
- 不改动 `pandas` 等下游对 `Decimal` 的承载策略,只要求行为可诊断

## Decisions

### 1. 顶层派生字段 runtime 类型 gate 直接扩展到 `Decimal`

顶层派生字段当前通过 `_ensure_field_value(...)` 对 `compute/call_by` 结果做类型 gate。这里应直接把允许值域扩展到 `FieldValue` 的完整口径,包括 `Decimal`。

选择这个方案的原因:

- 这是顶层派生字段与框架 `FieldValue` 契约重新对齐的最小闭环
- 与现有 `value_cast: decimal`、aggregate post-compute 的行为方向一致
- blast radius 明确,不会误伤无关运行时路径

备选方案是“只允许 `compute` 返回 `Decimal`,继续禁止 `call_by` 返回 `Decimal`”。这个方案会让两个派生字段入口继续语义不一致,没有长期价值,不采用。

### 2. `dec(x)` 作为显式 builtin,复用既有十进制转换语义

`dec(x)` 应作为 `SecureComputeEngine` 的 builtin 提供,语义与仓库现有十进制转换约定一致:

- `float` 使用 `Decimal(str(x))`
- `Decimal` 保持原样
- `None` 透传
- 空白字符串视为 `None`
- 非法字符串与非有限 `float` fail-fast

优先复用或对齐现有 `cast_decimal(...)` 语义,而不是再发明一套近似 helper。

原因:

- 可减少同一仓库里出现两套十进制转换语义的风险
- `value_cast: decimal` 与 `dec(...)` 的用户心智保持一致
- 便于测试与后续文档说明

### 3. `dec(x)` 的可见范围跟随 compute 引擎,而不是只绑定顶层字段

本 change 虽然主要动机来自顶层 `fields.*.compute`,但 `dec(x)` 一旦进入 `SecureComputeEngine`,它就应该在所有复用同一安全引擎的 YAML 表达式位置可见。

原因:

- 这是引擎级能力,不是某个单独 authoring surface 的特例
- 可以避免“顶层字段能用 `dec`, `outputs.where` 不能用”的新一轮不一致
- 实现更自然,测试边界也更清晰

这里仍保持 capability 只修改 `field-compute`,因为本次用户可见的核心契约变化是“compute 引擎的十进制语义被扩展”; 其余位置共享的是同一个引擎能力。

### 4. 不做隐式 `float -> Decimal` 自动修复

本 change 明确保持 opt-in:

- 用户可继续使用原有 `float` 口径
- 只有显式使用 `value_cast: decimal` 或 `dec(...)` 时,系统才进入十进制语义

原因:

- 隐式改写会带来兼容性与性能不确定性
- finance 场景要的是“可解释、可审计”,不是“框架替你猜”
- 与仓库“一步到位升级,但不偷偷改语义”的规则一致

### 5. 与 `xlsx-memory-type-preservation` 明确解耦

本 change 只负责让 `Decimal` 合法进入 runtime `FieldValue`。

一旦 `Decimal` 已经产生:

- 经过 workflow / `xlsx_memory` internal path 是否能继续保留
- workflow-managed artifacts 是否会把它字符串化
- `book_sheet_rows` 是否还能读回 `Decimal`

这些都由 `xlsx-memory-type-preservation` 负责。这里不重复定义,也不把 `.xlsx` 导出 round-trip 行为混入本 change。

## Risks / Trade-offs

- [不同 YAML 入口的现状不一致] → 通过把 `dec(x)` 定义在 compute 引擎层统一语义,并补顶层派生字段 gate 测试来收敛
- [`Decimal` 进入更多运行时路径后,下游 sink 可能出现 dtype/性能差异] → 在 proposal/spec 中明确这是允许行为,并把下游差异留给各自 capability 处理
- [用户误以为 `.xlsx` round-trip 也会保持 `Decimal`] → 在文档与 spec 中明确只承诺 runtime/internal path 语义,不承诺文件格式 round-trip
- [重复实现十进制转换 helper] → 优先复用/对齐既有 `cast_decimal(...)` 语义,避免双份规则

## Migration Plan

1. 在 `openspec/changes/c1-yaml-compute-decimal/` 下建立完整 proposal/design/specs/tasks 工件
2. 更新 `field-compute` delta spec,明确 `dec(x)` 与 `compute/call_by` 返回 `Decimal` 的契约
3. 实现 compute 引擎 builtin 与顶层派生字段 runtime 类型 gate 放宽
4. 增加 focused tests:
   - `dec(None/bool/int/float/str/Decimal)` 的行为
   - 顶层 `fields.*.compute` 返回 `Decimal`
   - 顶层 `fields.*.call_by` 返回 `Decimal`
   - 至少一个非顶层 compute-engine surface 可见 `dec(x)` 的回归
5. 运行 `just openspec-check` 与最小相关 pytest 子集

回滚策略:

- 若引擎级 `dec(x)` 扩散范围过大,可先保留顶层派生字段 `Decimal` 支持,再把其它 compute-engine surface 的可见性拆成后续小提交
- 不接受退回“顶层 compute 继续拒绝 `Decimal`”的状态,因为这会让十进制能力长期割裂

## Open Questions

- `dec(x)` 是直接委托到现有 `cast_decimal(...)`,还是抽一层 compute 专用包装以保留更明确的错误消息
- 对 `outputs.where` 这类非字段产出场景,是否需要额外增加用户文档示例来降低发现成本
