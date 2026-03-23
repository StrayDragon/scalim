## Why

仓库内存在多处“去重保序”的重复实现（`_ordered_unique`），且返回类型/输入归一化策略不一致，存在逻辑漂移风险：

- `src/scalim/execution/derived_outputs.py`：输入 `Sequence[str]`，`str()` 归一化后返回 `Tuple[str, ...]`
- `src/scalim/execution/output_composition.py`：用于 required fields 计算（同名 helper，细节可能不同）
- `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`：输入 `List[str]` 返回 `List[str]`（不做 `str()` 归一化）

当未来某处需要调整行为（例如统一 `str()` 归一化、或对 `None` 的处理、或返回类型约束）时，很容易出现“改一处漏两处”的漂移，最终导致执行计划/输出字段集合等关键逻辑出现不一致。

## What Changes

- 引入一个公共的 SSOT helper（建议放在 `src/scalim/utils/` 下）
  - 明确语义：对输入序列做 `str()` 归一化、去重保序、输出类型（推荐输出 `Tuple[str, ...]` 作为不可变结果）
  - 若调用方需要 `List[str]`，在调用点显式 `list(...)` 转换，避免 SSOT helper 同时承担两种返回类型
- 用 SSOT helper 替换现有重复实现，并删除本地 `_ordered_unique`
- 增加最小回归测试
  - 覆盖 `["a", "a", "b"]`、混合类型（例如 `["1", 1]`）的归一化行为是否符合预期

## Capabilities

### New Capabilities
- `ordered-unique-ssot`: 定义“去重保序”工具函数的 SSOT、语义与推荐返回类型，避免跨模块逻辑漂移。

### Modified Capabilities
（无；纯重构，不改变对外语义）

## Impact

- 受影响代码：
  - `src/scalim/execution/derived_outputs.py`
  - `src/scalim/execution/output_composition.py`
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
  -（新增）`src/scalim/utils/...` 的 SSOT helper
- 预期行为不变（若当前三处存在细微不一致，将在 refactor 时显式对齐并通过测试固化）
