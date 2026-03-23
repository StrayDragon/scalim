## Why

当前 by_yaml 的“输出聚合（aggregate）能力”存在多处枚举常量重复定义，导致跨层逻辑漂移风险：

- 解析/语义校验层：`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS/...`）
- 运行时装配层：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`）
- 工具/自省层：`src/scalim/dsl/by_yaml/runtime/introspection.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`）

一旦新增/调整某个 producer key（例如新增一种 rank 或 metric），很容易出现“校验允许但运行时不识别”或“运行时支持但 introspection 默认字段缺失”的不一致问题，导致线上行为不可预测、回归难定位。

## What Changes

- 引入聚合相关枚举常量的 SSOT（单一事实来源）
  - 将 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS/...` 收敛到一个明确的公共模块（位置待 design 决定，建议在 `schema_dsl`/`execution` 边界处，且保持 Python 3.6 兼容）
  - 解析层/运行时/自省层统一从该 SSOT 导入，禁止再各自维护副本
- 增加防漂移护栏
  - 添加单元测试：确保 parser/runtime/introspection 使用同一份枚举常量（例如通过导入同一对象或对比集合一致性）
  - 可选：在新增 producer key 时要求同时更新 SSOT + 对应 spec/测试（避免“改一处忘两处”）

## Capabilities

### New Capabilities
- `output-aggregate-enums-ssot`: 定义聚合 producer keys 的 SSOT 位置与使用约束（哪些模块必须引用该 SSOT、如何添加新 key、以及最小回归测试要求）。

### Modified Capabilities
（无；本变更不改变对外语义，仅做内部 SSOT 收敛与护栏）

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
  - `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
  - `src/scalim/dsl/by_yaml/runtime/introspection.py`
  -（新增）SSOT 枚举模块（路径在 design 中确定）
- 风险与收益：
  - 预期无行为变更（纯重构）；若当前已存在漂移，统一后会暴露并修复不一致点（这属于“修复不确定性”）
  - 显著降低未来扩展 aggregate producer keys 时的维护成本与回归风险
