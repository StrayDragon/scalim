## Context

来自真实迁移反馈: 同一条业务链路内,上游 loader/数据源经常返回不一致的 key 类型(例如 `"1"` vs `1`、`Decimal("1")` vs `1`、`123.0` vs `"123"`),导致框架内部所有“需要做匹配/去重/分组”的边界出现:

- relations 查找 miss(本应命中但因为 key 类型不同而 miss)
- derived outputs 的 `group_by`/`dedup_by` 产生额外分组/重复行(相同语义的 key 被当作不同 key)
- 为修复上述问题,业务侧不得不在多个位置重复写 `lookup_cast/value_cast/_auto_cast` 等 glue code,易漏配且难以统一口径

当前仓库已具备部分字符串规范化能力(例如 `auto_str_normalize`、`lookup_cast: auto`),但它们没有形成覆盖面一致的 SSOT 策略,导致同一需求在 relations 与 derived outputs 上需要两套配置/心智模型。

本变更引入一个 opt-in 的 key 规范化策略: 当用户显式开启时,框架内部所有“匹配点”统一使用稳定字符串口径进行匹配,减少重复 cast 配置与外部 glue code;默认行为仍保持 raw(避免大面积 breaking)。

## Goals / Non-Goals

**Goals:**

- 新增运行期开关 `key_normalization`(默认 `raw`),并在以下入口可启用:
  - by_yaml `run/compile`(`RunOptions`)
  - workflow `run_workflow`(入口参数/Options threading)
  - IR/Python-only 入口(`ExecutionRequest`)
- 当 `key_normalization=auto_str` 或 `key_normalization=force_str`:
  - relations lookup keys: 在最终匹配边界对 match key 应用 `auto_str_normalize`(多字段逐字段规范化并构造 `tuple[str, ...]`)后参与匹配/缓存(具体何时启用规范化由 `auto_str`/`force_str` 语义决定)
  - derived outputs 的 `group_by` / `dedup_by`: 对 key_fields/group_by 逐字段规范化后参与分组/去重;并使输出行中对应 key 字段使用规范化后的值(保证输出表现与内部合并一致)
- 显式 cast 与 key_normalization 的关系明确:
  - `auto_str`: 仅作为缺省 fallback 策略(存在显式 cast 时不做字符串规范化)
  - `force_str`: 强制在最终匹配边界做字符串规范化(显式 cast 先执行)
- 诊断语义明确且可观测: relations 路径区分 `null_key` vs `type_error`,并提供稳定 error message(不泄露敏感值)
- Python 3.6 兼容;不引入新的运行时依赖

**Non-Goals:**

- 不在本变更中引入 workflow YAML schema 的 `options.key_normalization` 字段(避免与 c12 的 unknown-fields 校验产生耦合;先作为 Python API/IR 级能力)
- 不引入类型 schema/casts 体系(例如 sheetbook 行值类型声明);sheetbook/CSV 通道仍视为 string channel
- 不扩展到更多“匹配点”(例如 `count_distinct` 的 distinct key)与 collision 诊断;如需可后续提案

## Decisions

1) **SSOT 与 threading**

- SSOT 放在 execution core: `ExecutionRequest.key_normalization`(默认 `raw`)
- `RunOptions.key_normalization` 与 `run_workflow(...)` 入口参数 thread 到 `ExecutionRequest`
- MVP 仅支持 run-level 开关,不引入 node/step 级覆盖(避免缓存/签名语义复杂化);如后续需要,再单独提案

2) **取值与校验**

- `key_normalization` 取值域: `raw | auto_str | force_str`
- 对外入口(compiler/workflow entrypoints)在编译期/启动期做校验,非法值 fail-fast
- `auto_str/force_str` 为实验性能力: 启用后必须有明显提示(例如运行期诊断告警事件),并在文档中声明后续可能调整

3) **Relations 采用路线 A(与 lookup_cast 心智模型一致)**

在 relations 中,lookup key 同时影响:

- loader 调用入参(例如 `$keys` 绑定)
- loader 返回 mapping 的命中(`intermediate_result[fk_value]`)

因此本变更选择 **路线 A**: 在实际启用字符串规范化口径进行匹配时,在 normalize 阶段直接把 candidate key 规范化为稳定字符串后再参与 loader 调用与 mapping 命中。

差异:

- `auto_str`: 仅当未配置显式 cast 时才对 raw key 做规范化(等价“缺省 lookup_cast=auto_str”)
- `force_str`: 无论是否配置显式 cast,都在最终匹配边界做规范化(显式 cast 先执行,再转稳定字符串)

理由:

- 语义与既有 `lookup_cast` 一致,实现简单且行为可预测
- 规范化在匹配边界发生,对缓存与 instrumentation 的口径统一
- 若某些 loader 依赖原始类型,用户可不启用该开关,或通过显式 `lookup_cast`/`key.cast` 明确口径

失败语义:

- raw 为 `None` → `null_key`(保持现有行为)
- raw 非 `None` 但规范化失败 → `type_error`(error message 仅包含类型/原因,避免泄露 raw value)

补充: **cached/preload sources 的匹配边界**

对 `preload/preload_forever` 等缓存源,执行路径会直接复用 loader 返回的 mapping,因此当 relations 实际启用字符串规范化口径进行匹配时(例如 `force_str`,或 `auto_str` 且缺省未配置 `lookup_cast/key.cast`),系统需要在“匹配点”使用同一套规范化 key 空间:

- 实现方式允许二选一:
  - 构建该 mapping 的“规范化视图”(lookup 时按规范化 key 命中)
  - 或对 mapping key 做等价的规范化后再用于命中
- MUST 约束: 不得破坏显式 cast 的语义(显式 `lookup_cast/key.cast` 仍按其口径命中 raw mapping)
- 若在构建规范化视图时出现 key collision(不同 raw key 规范化到同一 key),MUST fail-fast(避免 silent 选择导致隐性错误)

4) **Derived outputs 的 key 合并与输出表现**

- `GroupByAggregator`/`DedupByThenAggregator` 的 key 构造处引入 key_normalization:
  - `raw`: 维持现有行为(按原始值构造 key)
  - `auto_str`: 对每个 key 字段应用 `auto_str_normalize`
- 对 raw `None`:
  - 允许作为 key 的组成部分(保持现有“可分组/可去重”语义)
- 对 raw 非 `None` 但规范化失败:
  - fail-fast 抛错,避免 silent drop(错误信息仅包含字段名/目标/类型,不包含明细值)
- 输出行中对应 key 字段的值使用规范化后的值(保证“内部已合并”与“输出表现”一致,避免对拍/审计歧义)

5) **缓存与 workflow cache pool**

- 批次级缓存(`key_normalize_cache`/`load_ref_cache`)在同一次运行内 key_normalization 恒定,因此不要求把该开关纳入 signature 才能保证正确性
- workflow cache pool 在单次 workflow 执行内创建并使用,不跨 `run_workflow(...)` 调用复用;因此不引入签名字段变更
- 若未来引入 node 级覆盖或跨 run 复用,需要把 key_normalization 纳入相关 signature/cache key(作为后续提案)

## Risks / Trade-offs

- [Loader 入参类型改变] 启用 `auto_str` 会把缺省 lookup key 变为字符串(或字符串元组),可能影响依赖原始类型的 loader → 该能力为 opt-in;必要时使用显式 cast 或保持 `raw`
- [Force 模式的破坏性更强] 启用 `force_str` 会将 lookup key 强制转为字符串,即使显式 cast 输出为 int/Decimal 等 → 该能力为 opt-in 且标注 EXPERIMENTAL;必要时保持 `auto_str/raw`
- [Key collision] `True/1/1.0/Decimal("1")/"1"` 可能被合并到同一 `"1"` → 视为 opt-in 的字符串语义合并;文档需要明确风险
- [输出字段类型变化] 启用后,group_by/dedup key 字段输出可能从 `int/Decimal/bool` 变为 `str` → 仅在 opt-in 下发生;需在 spec/文档中明确
- [性能开销] 规范化引入额外 CPU/对象分配 → 通过既有批次缓存与“仅在开启时启用”控制开销;高基数场景可后续再考虑引入 derived key 缓存
 - [float 口径差异] `lookup_cast: auto` 会拒绝 float,但 `auto_str_normalize` 会将 float 规范化为字符串 → 在 spec 中明确: 启用 `auto_str` 即表示用户接受“按字符串语义匹配”的风险

## Migration Plan

- 新增字段默认 `raw`,对存量调用保持行为不变
- 更新 specs 与实现后:
  - `just qa`
  - `just openspec-check`
- 若涉及 docs-site/注入区块,通过 `just gen-docs` 刷新(不手改 `.gen.*` 与 injected blocks)

## Open Questions

- 是否需要把 `count_distinct` 的 distinct key 一并纳入 key_normalization(当前不做,避免扩大范围)
- 是否需要提供 collision 检测/告警(当前不做,后续可提案)
