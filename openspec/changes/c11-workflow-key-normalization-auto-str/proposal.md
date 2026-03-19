## Why

来自 cus_collect_infos 的迁移实践反馈（基于 Scalim 0.3.2 实际使用；FR5 延伸问题）：同一条业务链路内，上游 loader/数据源经常返回不一致的 key 类型（例如 `"1"` vs `1`、`Decimal("1")` vs `1`、`123.0` vs `"123"`），导致框架内部“需要做匹配/去重/分组”的位置出现:

- relations 查找 miss（本应命中但因为 key 类型不同而 miss）
- derived outputs 的 `group_by`/`dedup_by` 产生额外分组/重复行（相同语义的 key 被当作不同 key）
- 为修复上述问题，业务侧不得不在多个位置重复写 `lookup_cast/value_cast/_auto_cast` 等 glue code，易漏配且难以统一口径

当前仓库已具备部分“字符串规范化”能力，但它们没有形成一个覆盖面一致的 **SSOT 策略**：

- relations 目前主要依赖显式 `lookup_cast`（step 级优先，其次 source 级 `key.cast`）；`lookup_cast.name=auto` 会拒绝 float 并返回 `None`（见 `openspec/specs/source-relations/spec.md` 与实现 `src/scalim/utils/converters.py:auto_normalize_key`）。
- `auto_str_normalize` 已在框架内存在（`src/scalim/utils/converters.py:auto_str_normalize`），并被 `value_cast: auto` 等路径复用，但默认不会把“匹配点”统一变成字符串匹配。
- derived outputs 的 key 目前以原始行值构造（例如 `tuple(row.get(fid) ...)`），因此 `1` 与 `"1"` 会天然分裂成两个 group/dedup key；这与业务期望的“同语义合并”常冲突。

本变更希望提供一个 opt-in 的、跨模块一致的 key 规范化策略：当用户明确开启时，框架内部所有“匹配点”统一使用稳定字符串口径，从而减少显式 cast 配置与外部 glue code，同时保持默认行为不变（避免大面积 breaking）。

## What Changes

- 新增一个 opt-in 的 key 规范化开关（建议命名 `key_normalization` 或等价语义），并要求在以下入口可被启用：
  - by_yaml `run/compile`（`RunOptions`）
  - workflow `run_workflow`（workflow options 或入口参数）
  - 最终落到 execution core 的运行期上下文（确保 IR/Python-only 入口也可使用该能力）
- 当 `key_normalization=auto_str` 时，框架内部“需要匹配”的 key 统一按 `auto_str_normalize` 规范化：
  - relations lookup keys：在未显式配置 `lookup_cast`/`key.cast` 的情况下，将 `raw_key` 规范化为稳定字符串再参与 dict lookup / cache key；多字段 key 逐字段规范化并构造 `tuple[str, ...]`。
  - derived outputs 的 `group_by` / `dedup_by` keys：对 key_fields 逐字段规范化后再参与分组/去重；输出行中的 group_by 字段值也使用规范化后的字符串（避免“内部合并了但输出表现不一致/不稳定”）。
- 失败/诊断语义（需要在 spec 中明确以便后续讨论与实现）：
  - `auto_str_normalize(...) -> None` 视为“无法规范化”，在 relations 路径中应计入 `type_error` 并提供可诊断 message；在 derived group_by/dedup 路径中推荐 fail-fast（避免 silent drop 造成报表少行且难排查）。
  - 该能力为 opt-in：默认 `key_normalization=raw`（完全保持现有行为与性能/缓存语义）。
- Non-Goals（本 change 明确不做）：
  - 不引入 sheetbook 行值类型 schema/casts；sheetbook/CSV 通道仍视为 string channel（类型由下游显式转换）。
  - 不改变 `lookup_cast` 的既有 SSOT（用户显式配置的 cast 永远优先；仅在缺省时才由 key_normalization 提供 fallback 策略）。

## Capabilities

### New Capabilities
- `key-normalization`: 提供 workflow/run 级别的 key 规范化策略（本 change 首先实现 `auto_str`），用于统一 relations + derived group_by/dedup 的匹配边界与诊断语义。

### Modified Capabilities
- `source-relations`: 当启用 `key-normalization=auto_str` 时，缺省 lookup key 的规范化与 `type_error`/诊断语义需要补齐到规范。
- `derived-outputs`: 当启用 `key-normalization=auto_str` 时，`group_by`/`dedup_by` 的 key 边界与输出表现需要定义（避免 `1` vs `"1"` 分裂）。
- `dsl-runtime-structure`: by_yaml 与 workflow 对外入口需要新增 opt-in 参数，并定义其默认值/覆盖关系。

## Impact

- 受影响代码（示例，非详尽）：
  - relations lookup key 归一化：`src/scalim/execution/executor/runtime/runtime.py`（`normalize_lookup_key_with_status` 链路）
  - 规范化实现 SSOT：`src/scalim/utils/converters.py`（`auto_str_normalize`）
  - derived group_by/dedup keys：`src/scalim/execution/derived_outputs.py`（group key / dedup key 构造处）
  - by_yaml/workflow 入口 threading：`src/scalim/dsl/by_yaml/runtime/contracts.py`、`src/scalim/dsl/by_yaml/runtime/entrypoints.py`、`src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
- Public API：新增可选参数/选项；默认值为 `raw`，对存量调用保持兼容。
- 性能/内存：
  - 规范化会引入额外 CPU 开销；但可通过 batch-level cache（框架已有 `key_normalize_cache`）降低重复计算。
  - 规范化后的 key 以字符串/字符串元组参与 dict lookup，整体仍为轻量对象（相对保留 Decimal 等复杂对象更可控）。
- 风险与讨论点（作为后续讨论上下文，不在 proposal 阶段定实现细节）：
  - key collision：例如 `True`/`1`/`1.0` 规范化后可能合并到同一 `"1"`；该行为可能是期望也可能是风险，需要在 spec 中明确“这是 opt-in 且按字符串语义合并”。
  - float 规范化：`auto_str_normalize` 对非整数 float 使用 `format(x, ".15g")`；需要确认其对拍/稳定性是否满足业务需求。
