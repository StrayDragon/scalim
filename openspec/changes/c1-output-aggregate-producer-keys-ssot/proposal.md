## Why

当前 by_yaml 的“输出聚合（aggregate）能力”存在多处枚举常量重复定义，导致跨层逻辑漂移风险：

- 解析/语义校验层：`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS/...`）
- 运行时装配层：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`）
- 工具/自省层：`src/scalim/dsl/by_yaml/runtime/introspection.py`（`_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`）
- 结构校验/编辑器层（JSON schema + editor bundle）：
  - schema 源码：`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`（producer keys 的 anyOf/required/enum）
  - canonical schema 生成物：`src/scalim/dsl/by_yaml/schema/demand.gen.json`
  - editor schema bundle：`frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json`、`frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`

一旦新增/调整某个 producer key（例如新增一种 rank 或 metric），很容易出现“校验允许但运行时不识别”或“运行时支持但 introspection 默认字段缺失”的不一致问题，导致线上行为不可预测、回归难定位。

## As-Is 调研（重复点与漂移样例）

### 1) producer keys 在多个层重复维护（且粒度不一致）

- parser：`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
  - `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS`（包含 `compute` 等 post keys）
- runtime：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
  - `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`（post keys 分散为硬编码字符串判断）
- introspection：`src/scalim/dsl/by_yaml/runtime/introspection.py`
  - `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS` + post keys 以 `("score_by_rank", "call_by")` 硬编码（当前遗漏 `compute`）
- schema/editor：
  - schema SSOT 源码：`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`（aggregate.fields 的 oneOf/required/description 分支显式枚举 `compute/score_by_rank/call_by/...`）
  - 生成物与 bundle：`src/scalim/dsl/by_yaml/schema/demand.gen.json` + `frontend/.../schema/demand.gen.json`

这意味着“新增/调整一个 key”会穿越至少 4 个层次的维护点，且其中两处（runtime/introspection）还存在“category 粒度不同/部分硬编码”的隐形漂移面。

### 2) 可复现漂移：introspection 默认 output_fields 与 runtime 默认输出列不一致

当前 `aggregate` + 未显式指定 `outputs.*.fields` 时：

- runtime 默认输出列包含 `compute`（聚合后派生字段会参与 DAG 并被写出）
- introspection 的 `_default_output_fields_from_primary_output()` 默认 `post_ids` 未包含 `compute`

最小复现思路：

1. 写一个包含 aggregate 且 fields 中存在 `compute` producer key 的 demand YAML。
2. 调用 `src/scalim/dsl/by_yaml/runtime/introspection.py::load_output_config()`，观察返回的 `output_fields`（缺 `compute`）。
3. 用同一 YAML 走 runtime compile/run，观察实际写出的列（包含 `compute`）。

该差异会直接影响“工具/编辑器默认预览字段列表”与“实际输出列”的一致性，属于真实的跨层漂移。

## What Changes

- 引入聚合相关枚举常量的 SSOT（单一事实来源）
  - 将 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS/...` 收敛到一个明确的公共模块（位置待 design 决定，建议在 `schema_dsl`/`execution` 边界处，且保持 Python 3.6 兼容）
  - 解析层/运行时/自省层统一从该 SSOT 导入，禁止再各自维护副本
  - schema 生成层（`schema_dsl/models/outputs.py`）也必须基于 SSOT 组装 producer key 列表，并在生成时强校验“schema 覆盖全集”（避免 schema/editor 漏支持或多支持）
- 增加防漂移护栏
  - 添加单元测试：确保 parser/runtime/introspection 使用同一份枚举常量（例如通过导入同一对象或对比集合一致性）
  - schema drift 护栏：通过既有生成流程同步 `demand.gen.json` 到 editor bundle，并在 CI 中阻止未同步（见 `just schema-drift-check`）
  - 可选：在新增 producer key 时要求同时更新 SSOT + 对应 spec/测试（避免“改一处忘两处”）

## Known Drift / Bug Fix (Intentional)

当前存在一个可复现的跨层漂移：

- runtime 默认 aggregate 输出列包含 `compute`（当 `outputs.*.fields` 未显式指定时）
- introspection 的 `load_output_config()` 默认 `output_fields` 不包含 `compute`

这会导致 “工具/编辑器默认预览字段列表” 与 “实际 `run()` 写出的输出列” 不一致。

本变更采用 **方案 A**：将 introspection 的默认 `output_fields` 对齐到 runtime 的默认输出列（包含 `compute`），并以测试固化该一致性。

## Capabilities

### New Capabilities
- `output-aggregate-producer-keys-ssot`: 定义聚合 producer keys 的 SSOT 位置与使用约束（哪些模块必须引用该 SSOT、如何添加新 key、以及最小回归测试要求）。

### Modified Capabilities
（无；本变更不改变对外语义，仅做内部 SSOT 收敛与护栏）

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
  - `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
  - `src/scalim/dsl/by_yaml/runtime/introspection.py`
  - `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`（producer keys schema 组装/强校验）
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`（生成物）
  - `frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json`（生成物）
  - `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`（生成物）
  -（新增）SSOT 枚举模块（路径在 design 中确定）
- 风险与收益：
  - 行为变更（bug fix）：`load_output_config()` 在 aggregate 且未显式指定 `outputs.*.fields` 时，默认 `output_fields` 将包含 `compute`（与 runtime 默认输出列对齐）
  - 其余部分预期无行为变更（重构）；若当前已存在漂移，统一后会暴露并修复不一致点（这属于“修复不确定性”）
  - 显著降低未来扩展 aggregate producer keys 时的维护成本与回归风险
