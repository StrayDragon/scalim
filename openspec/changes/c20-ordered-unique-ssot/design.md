## Context

仓库内存在多处“去重保序（ordered unique）”的重复实现 `_ordered_unique`，并且在细节上不一致：

- `src/scalim/execution/derived_outputs.py`：
  - 输入 `Sequence[str]`，但内部对每个 item 做 `str()` 归一化
  - 返回 `Tuple[str, ...]`
- `src/scalim/execution/output_composition.py`：
  - 输入 `Sequence[str]`，不做 `str()` 归一化（假设已是字符串）
  - 返回 `Tuple[str, ...]`
- `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`：
  - 输入 `List[str]`，不做 `str()` 归一化
  - 返回 `List[str]`

这些差异在短期内不一定暴露，但一旦某处需要调整语义（例如统一 `str()` 归一化、或统一输出不可变 tuple），很容易出现“改一处漏两处”的漂移，导致 required fields、aggregate DAG 依赖列表等关键逻辑产生不一致。

约束：

- `src/scalim/` 运行时需兼容 Python 3.6。
- 本变更为内部重构（SSOT 收敛），目标是不改变对外语义；如发现当前三处存在真实行为差异，必须在测试里显式捕获并说明。

## Goals / Non-Goals

**Goals:**

- 提供一个公共 SSOT helper，所有需要“去重保序”的路径复用该 helper。
- 明确 helper 的稳定语义：
  - 保序去重
  - 输出稳定、可预测
  - 返回类型固定（推荐 tuple，避免下游误修改）
- 通过最小单测固化语义与调用点一致性，避免未来漂移。

**Non-Goals:**

- 不在本变更内做更大范围的 outputs/aggregate 逻辑重构（那是独立 change）。
- 不引入新的第三方依赖。

## Decisions

### 1) SSOT helper 的位置与命名

**决策：**

- 在 `src/scalim/utils/` 下新增一个小模块（例如 `iterables.py` / `collectionsx.py`，最终以实现为准）。
- 提供单一函数作为 SSOT：例如 `ordered_unique_str(items: Sequence[object]) -> Tuple[str, ...]`。

**理由：**

- `utils` 已是跨 execution/by_yaml 共享的稳定依赖方向，能避免循环依赖。
- 命名显式包含 `_str`（或等价）能降低误用风险：该 helper 明确用于“字段 ID/producer keys 等字符串口径”的集合处理。

### 2) helper 的语义：`str()` 归一化 + tuple 输出

**决策：**

- 对每个 item 做 `key = str(item)` 归一化（与 `derived_outputs` 现状一致）。
- 以首次出现顺序去重。
- 返回 `Tuple[str, ...]`（不可变，且与 execution 层现状一致）。
- 调用点若确实需要 `List[str]`，在调用点显式 `list(...)` 转换。

**备选：**

- 不做 `str()` 归一化：会让三处实现继续保持分裂，且未来更容易踩到混合类型输入导致的隐性差异。
- helper 同时支持 list/tuple 两种返回类型：增加 API 模糊度，反而更容易漂移。

### 3) 迁移策略：替换重复实现并删除本地 `_ordered_unique`

**决策：**

- 用 SSOT helper 替换三处 `_ordered_unique`，并删除重复实现，避免未来继续被引用或再次复制。
- 在迁移过程中，如果发现某处行为确实依赖“不做 str()”或“返回 list”，必须：
  - 在该调用点做显式转换/适配
  - 并用测试说明理由（避免后续误改）

## Risks / Trade-offs

- [行为差异] `str()` 归一化可能改变极端输入（例如 `1` 与 `"1"`）的去重结果 → 缓解：该 helper 的用途应限定为“字符串口径字段集合”；并补齐单测覆盖混合类型输入，确保行为显式可见。
- [迁移范围] 删除本地函数会影响局部 import/调用 → 缓解：一次性替换所有调用点，并加一个小型“import-smoke”测试或 `rg` 确认无残留引用。

## Migration Plan

1. 新增 SSOT helper（含 docstring 与导出）。
2. 替换并删除三处 `_ordered_unique`。
3. 新增最小单测固化语义（`["a","a","b"]`、混合类型等）。
4. 运行 `just qa` 与 `just openspec-check`。
