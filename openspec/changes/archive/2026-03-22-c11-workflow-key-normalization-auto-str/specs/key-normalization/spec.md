## ADDED Requirements

### Requirement: `key_normalization` MUST be a validated opt-in runtime option (default `raw`)
系统 MUST 提供一个运行期开关 `key_normalization`,取值域为:

- `raw`: 保持现有 key 口径(默认)
- `auto_str`: 使用稳定字符串口径做 key 匹配(仅在未显式配置 cast 时作为缺省策略生效)
- `force_str`: 强制使用稳定字符串口径做 key 匹配(即使显式配置 cast 也会在最终匹配边界做字符串规范化)

系统 MUST 在对外入口对该字段进行校验;未知取值 MUST fail-fast(编译期/启动期均可).

该开关 MUST 可在以下入口启用并最终落到 execution core 的运行期上下文(例如 `ExecutionRequest`/runtime context):

- by_yaml `run/compile`(RunOptions)
- workflow `run_workflow`(入口参数)
- IR/Python-only(直接构造 `ExecutionRequest`)

#### Scenario: unknown key_normalization is rejected
- **GIVEN** 用户传入 `key_normalization="whatever"`
- **WHEN** 系统开始编译或运行
- **THEN** 系统 MUST fail-fast 并提示仅支持 `raw|auto_str|force_str`

### Requirement: `key_normalization` non-raw modes MUST be explicitly marked as EXPERIMENTAL
当用户启用 `key_normalization` 的非 `raw` 模式(例如 `auto_str`/`force_str`)时,系统 MUST 提供清晰且可观测的提示,表明该能力为实验性特性且后续可能调整.

系统 MUST 在一次运行内至少发出一次 warning(或等价的“诊断告警事件”),并满足:

- warning 文案 MUST 包含 `EXPERIMENTAL`
- warning 文案 MUST 包含当前启用的 `key_normalization` 值
- warning 文案 MUST NOT 包含任何明细 key 值
- 若系统具备 `sample_once`/去重语义,则 SHOULD 对同一次运行去重(避免刷屏)

#### Scenario: enabling auto_str emits an experimental warning
- **GIVEN** 用户启用 `key_normalization=auto_str` 或 `key_normalization=force_str`
- **WHEN** 系统开始运行(或首次使用该策略做 key 匹配)
- **THEN** 系统 MUST 发出一次包含 `EXPERIMENTAL` 的 warning/诊断告警事件

### Requirement: explicit cast precedence and normalization mode MUST be well-defined
当同时存在显式 cast 与 `key_normalization` 时,系统 MUST 按以下步骤确定最终 match key:

1. 先按优先级计算 candidate key:
   - step 级 `lookup_cast`
   - source 级 `key.cast`
   - raw key(缺省)
2. 再根据 `key_normalization` 得到最终 match key:
   - `raw`: 直接使用 candidate key
   - `auto_str`: 仅当 candidate key 来自 raw key(即未配置任何显式 cast)时,对 candidate key 应用字符串规范化;否则保持 candidate key 不变
   - `force_str`: 无论 candidate key 来自何处,都 MUST 对 candidate key 应用字符串规范化

字符串规范化指逐字段应用 `auto_str_normalize`,并构造 `str` 或 `Tuple[str, ...]` 作为 match key.

并且:

- step 级 `lookup_cast` MUST 优先于 source 级 `key.cast`
- `key_normalization=auto_str` MUST 仅作为缺省 fallback 策略生效(存在显式 cast 时不得额外做字符串规范化)
- `key_normalization=force_str` MUST 对 candidate key 强制执行字符串规范化(显式 cast 先执行)

#### Scenario: step lookup_cast overrides key_normalization
- **GIVEN** raw lookup key 为 `"1"`(str)
- **AND** step 显式配置 `lookup_cast` 将 key 转换为 `int`
- **WHEN** 用户启用 `key_normalization=auto_str`
- **THEN** 系统 MUST 使用显式 `lookup_cast` 的结果作为 match key(例如 `1`),而不是 `"1"`

#### Scenario: force_str normalizes even when lookup_cast is set
- **GIVEN** raw lookup key 为 `"1"`(str)
- **AND** step 显式配置 `lookup_cast` 将 key 转换为 `int`
- **WHEN** 用户启用 `key_normalization=force_str`
- **THEN** 系统 MUST 在最终匹配边界将 candidate key 规范化为稳定字符串(例如 `"1"`)

### Requirement: `key_normalization` string modes MUST normalize match keys via `auto_str_normalize`
系统 MUST 提供基于字符串的 key 规范化策略 `key_normalization=auto_str` 与 `key_normalization=force_str`。

当启用任一字符串策略时,框架内部所有“需要匹配”的 key(例如 relations lookup key、derived outputs 的 `group_by`/`dedup_by` key)在进入匹配边界时 MUST 逐字段应用 `auto_str_normalize` 后再参与匹配.

并且字符串规范化的启用时机 MUST 遵循上一条 requirement 的算法(即 `auto_str` 为 fallback,`force_str` 为强制).

#### Scenario: auto_str normalizes raw int key into a stable string
- **GIVEN** raw match key 为 `1`(int)
- **WHEN** 用户启用 `key_normalization=auto_str`
- **AND** 未显式配置 `lookup_cast`/`key.cast`
- **THEN** 系统 MUST 将该 key 规范化为稳定字符串 `"1"` 后参与匹配

#### Semantics: `None` vs normalize failure

- raw 为 `None` 表示“空值”: 在 relations 中 MUST 计入 `null_key`;在 derived `group_by`/`dedup_by` 中 MUST 允许作为 key 的组成部分
- raw 非 `None` 但 `auto_str_normalize(raw)` 返回 `None` 表示“无法规范化”: 在 relations 中 MUST 计入 `type_error`;在 derived `group_by`/`dedup_by` 中 MUST fail-fast

当需要输出错误/诊断 message 时,系统 MUST NOT 在 message 中包含 raw key 的明细值(避免泄露敏感数据);message SHOULD 仅包含类型/字段/来源/原因等上下文信息.

#### Semantics: float keys
当 raw key 为 `float` 时:

- `NaN/inf` MUST 视为规范化失败
- 其余 float MUST 按 `auto_str_normalize` 规则规范化为稳定字符串(整数 float 去除小数部分;非整数 float 使用稳定格式化)

注意: 该行为与 relations 的 `lookup_cast: {name: auto}`(会拒绝 float) 不同;启用 `key_normalization=auto_str` 或 `key_normalization=force_str` 表示用户接受按字符串语义做 key 匹配的风险.

#### Semantics: multi-field keys
当 key 为多字段复合键时(例如 `Tuple[object, ...]`):

- 系统 MUST 对每个组成字段逐字段应用 `auto_str_normalize`
- 系统 MUST 将规范化后的结果组成 `Tuple[str, ...]` 作为 match key
- 任一组成字段 raw 为 `None` → relations MUST 视为 `null_key`
- 任一组成字段 raw 非 `None` 且规范化失败 → relations MUST 视为 `type_error`(derived MUST fail-fast)

#### Semantics: key collisions after normalization
当多个不同 raw key 规范化到同一个稳定字符串 key 时:

- derived outputs 的 `group_by`/`dedup_by` 语义为“合并”: 这是该能力的预期行为(按规范化 key 合并)
- relations 在构建“需要匹配的 mapping 的规范化视图”时,若发生 collision,系统 MUST fail-fast(避免 silent 选择导致隐性错误);错误信息 MUST 不包含明细 key 值

### Requirement: relations MUST use the normalized key space consistently (including cached sources)
当 relations 实际采用字符串规范化口径进行匹配时(例如 `key_normalization=force_str`,或 `key_normalization=auto_str` 且未显式配置 `lookup_cast`/`key.cast`),relations 查找 MUST 使用规范化后的 key 口径,且该口径 MUST 在下列边界保持一致:

- loader 调用入参(例如 `$keys` 绑定)
- loader 返回 mapping 的命中(`intermediate_result[lookup_key]`)
- 针对 `preload/preload_forever` 等缓存源,系统 MUST 在“匹配点”使用与 lookup key 相同的 key 口径进行命中

注意:

- 当 `key_normalization=auto_str` 且存在显式 cast 时,系统 MUST 使用显式 cast 的 key 口径,不得额外做字符串规范化(避免破坏已有 loader 期望)
- 当 `key_normalization=force_str` 时,系统 MUST 在最终匹配边界对 candidate key 强制做字符串规范化(显式 cast 先执行)

#### Scenario: cached mapping with int keys still hits when enabled
- **GIVEN** 某个目标 source 为 `preload_forever`,其 loader 返回 mapping 的 key 为 `1`(int)
- **AND** relations raw lookup key 值为 `"1"`(str)
- **WHEN** 用户启用 `key_normalization=auto_str` 或 `key_normalization=force_str`
- **AND** 未对该 lookup 配置 `lookup_cast`/`key.cast`
- **THEN** 系统 MUST 将两侧 key 统一到相同的规范化口径并命中该 mapping

### Requirement: derived outputs MUST normalize `group_by`/`dedup_by` keys and output key fields when enabled
当 `key_normalization=auto_str` 或 `key_normalization=force_str` 时,系统 MUST 在 derived outputs 的 `group_by`/`dedup_by` 中使用规范化后的 key 做合并,并在输出行中回填规范化后的 key 字段值(保证内部口径与输出表现一致).

- derived outputs 的 `group_by` 与 `dedup_by` 的 key MUST 逐字段应用 `auto_str_normalize` 后再参与分组/去重
- 输出行中 `group_by`/`dedup_by` 的对应字段值 MUST 使用规范化后的值(保证内部合并口径与输出表现一致)
- 若 raw 非 `None` 但规范化失败,系统 MUST fail-fast,且错误信息 MUST 不包含 raw 明细值

#### Scenario: derived outputs group_by merges semantically equal keys when enabled
- **GIVEN** derived outputs 的 `group_by` 字段在不同输入行中分别为 `1` 与 `"1"`
- **WHEN** 用户启用 `key_normalization=auto_str` 或 `key_normalization=force_str`
- **THEN** 系统 MUST 将两者规范化为相同的分组 key,从而落入同一分组
- **AND** 输出行中该 `group_by` 字段值 MUST 为规范化后的稳定字符串

#### Scenario: derived outputs dedup_by merges semantically equal keys when enabled
- **GIVEN** derived outputs 的 `dedup_by.key_fields` 字段在不同输入行中分别为 `1` 与 `"1"`
- **WHEN** 用户启用 `key_normalization=auto_str` 或 `key_normalization=force_str`
- **THEN** 系统 MUST 将两者规范化为相同的去重 key,从而视为同一条记录

#### Scenario: relations lookup key `"1"` and `1` are treated as the same key when enabled
- **GIVEN** relations 需要查找的 raw key 值为 `1`
- **AND** 上游数据源在关系映射中使用了字符串 key `"1"`
- **WHEN** 用户启用 `key_normalization=auto_str` 或 `key_normalization=force_str`
- **AND** 未对该 lookup 配置 `lookup_cast`/`key.cast`
- **THEN** 系统 MUST 将 `1` 规范化为稳定字符串并命中 `"1"` 的映射
