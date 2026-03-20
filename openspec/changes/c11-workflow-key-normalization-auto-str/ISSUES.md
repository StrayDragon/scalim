# ISSUES — c11-workflow-key-normalization-auto-str

本文用于沉淀该提案在 **IR 级别**推进前需要明确的开放问题、风险点与取舍项（避免实现时出现两套口径或隐性 breaking）。

## 1) SSOT 与 threading（开关放哪、怎么贯穿）

- `key_normalization` 的 **SSOT** 建议落在 execution core（例如 IR 的 `ExecutionRequest` / runtime context）而不是散落在 relations/derived 内部；需要明确最终承载体、默认值与覆盖规则：
  - by_yaml `run/compile`（`RunOptions`）→ `ExecutionRequest`
  - workflow `run_workflow` → `RunOptions` → `ExecutionRequest`
  - IR/Python-only 入口（直接构造 `ExecutionRequest`）也能开关
- 需要明确：当同时存在多个入口（例如 workflow node overrides vs run options），优先级如何定义（以及是否允许 node 级覆盖）。

## 2) Relations：normalize 的 key 到底影响哪里（最关键决策）

当前架构里，“lookup key”同时用于：
1) 传给 loader（`$keys` / `$rows` 绑定），以及
2) 作为索引命中 loader 返回 mapping 的 key（`intermediate_result[fk_value]`）。

因此启用 `key_normalization=auto_str` 时需要明确采用哪条路线：

- **路线 A（强一致 / 改 loader 入参）**：缺省情况下把 raw key 规范化为字符串后，再参与 loader 调用与 mapping lookup（等价于“默认 lookup_cast=auto_str”）。
  - 优点：实现最小；语义最统一；和既有 `lookup_cast` 心智模型一致。
  - 风险：可能改变 loader 的入参类型（int→str），一些 loader 可能依赖原始类型（SQL/参数绑定/类型分派），启用后可能查不出或报错。
- **路线 B（解耦 / 不改 loader 入参）**：loader 仍拿 raw keys；框架内部为“匹配点”构建 normalized match key（包括对 loader result mapping keys 的 normalized view），在 match 层做容错合并。
  - 优点：更不容易破坏 loader 期望；更像框架内部容错层。
  - 风险：实现复杂（需要 raw↔normalized 映射、冲突策略、缓存 key 设计变更），并且必须定义 collision 诊断语义。

> 该决策不明确时，容易出现“修了 match、坏了 loader”或“启用后表面生效、缓存/预加载却不生效”的情况。

## 3) 显式 cast 的优先级与边界（SSOT 不打架）

- 需要在 spec 中写死并验证：
  - step 级 `lookup_cast` 优先于 source 级 `key.cast`
  - 两者都优先于 `key_normalization` 的缺省策略（`auto_str` 仅做 fallback）
- 需要明确：多字段 key 时是逐字段 normalize 还是整体 stringify（建议逐字段并组成 `tuple[str, ...]`，但要写进 spec）。

## 4) `None` 语义：空值 vs “无法规范化”必须区分

`auto_str_normalize` 会对以下情况返回 `None`：
- raw 为 `None`（合法“空值”）
- raw 非 `None` 但无法规范化（类型不支持、NaN/inf、bytes 非 utf-8 等）

需要明确：
- relations：raw 为 `None` → `null_key`；raw 非 `None` 且 normalize 失败 → `type_error`（并给诊断 message）
- derived group_by/dedup_by：raw 为 `None` 是否允许作为 key（类似 SQL）？与 “normalize 失败” 如何区分、如何 fail-fast

## 5) key collision：允许/告警/拒绝的策略（必须显式）

启用 `auto_str` 后潜在的语义合并：
- `True` / `1` / `1.0` 可能都归一化到 `"1"`
- `Decimal("1")` / `1` / `"1"` 合并到 `"1"`
- datetime/date/time 的字符串口径可能造成意外合并或顺序问题

需要明确：
- collision 是否被视为 **预期行为**（opt-in 的“按字符串语义合并”），还是需要 guardrail/warn
- 是否需要提供“检测 collision”与脱敏诊断（例如计数、hash 摘要），尤其对 derived outputs 的 meta/audit（不得泄露具体 key 值）

## 6) float 口径：与现有 `auto_normalize_key` 的差异如何解释

当前：
- relations 的 `lookup_cast: auto`（`auto_normalize_key`）会 **拒绝 float**（返回 `None` 并发出诊断告警）
- `auto_str_normalize` 会把 float 规范化为字符串（整数 float 变 `"123"`，非整数 float 用 `format(x, ".15g")`）

需要明确：
- `key_normalization=auto_str` 对 float 的行为是否真的符合业务预期（稳定性/对拍/跨版本一致性）
- 是否要对 float 做额外限制（例如保持与 relations 的 “float 需显式 cast” 一致，或者至少有 warn）

## 7) derived outputs：覆盖面边界（不仅是 group_by/dedup_by）

提案目前点名了：
- `group_by`
- `dedup_by`

但从“匹配点”语义看，还可能包含：
- `count_distinct` 的 distinct key（否则仍会出现 `1` vs `"1"` 被当作不同 distinct 的情况）
- 排名/排序相关的 partition key / tie-break（当前 `_stable_group_key_tuple` 使用稳定字符串签名，但它是“排序”而非“相等合并”）

需要明确本 change 的覆盖边界与 Non-Goals（否则用户会质疑不一致）。

## 8) derived outputs 输出字段类型：是否强制变成 string

提案建议“输出行中的 group_by 字段值也使用规范化后的字符串”，这会导致：
- 输出类型从 int/Decimal/bool → str（opt-in breaking）

需要明确：
- 这是 MUST 还是 SHOULD（只影响内部合并 vs 同步改变输出表现）
- 如果改变输出字段值，是否影响 downstream（导出 schema、excel/pandas、对拍等）

## 9) Workflow / preload_forever：跨 run 缓存与一致性

`PreloadCache` 用于跨 runs 共享 `preload_forever` 结果（workflow 场景）。

需要明确：
- 若某次 run 开启 `auto_str`，而 cache 中存的是 raw-key mapping（int/Decimal…），如何处理？
  - 要求 workflow 全程一致开关
  - 或按 `(source_id, key_normalization)` 分桶
  - 或构建“lazy normalized view”
- 否则容易出现“开了开关但命不中 preload cache”的隐性问题。

## 10) 缓存指纹/命中语义：需要把 key_normalization 纳入哪些 cache key

当前缓存点包括：
- `key_normalize_cache`（按 relation signature + (row_id, from_fields) 缓存）
- `load_ref_cache`（按 step signature + lookup_keys_fingerprint 缓存）

需要明确：
- 若 key_normalization 改变 lookup key 口径，`build_step_signature`/`load_ref_cache` 是否需要纳入该开关（避免不同口径共享缓存导致错命中/漏命中）
- multi-field key 的 fingerprint 如何稳定表示（以及是否要与 normalized key 口径一致）

## 11) 诊断与可观测性：哪些地方记录 raw/normalized，哪些地方必须脱敏

需要明确并对齐现有规范：
- relations：`type_error/null_key` 诊断信息应包含足够上下文（source/field/step）但避免泄露敏感值（尤其在落盘报告中）
- derived outputs：meta/audit 明确“不泄露明细 key 值”，因此若引入 collision/normalize 失败诊断，必须用计数/摘要/hash
- 需要定义 `auto_str_normalize(...) -> None` 的错误 message 规范（例如 bytes decode 失败、NaN/inf、unsupported type 等）

## 12) 性能/内存：开关开启后的开销与缓存策略

- normalize 会引入额外 CPU；需要明确是否依赖批次级缓存（现有 `key_normalize_cache`）以及是否要扩展到 derived outputs 的 key normalization cache
- 输出层（derived）若做 normalize，是否会在高基数下造成额外对象分配/内存膨胀；是否需要明确 guardrail/warn

