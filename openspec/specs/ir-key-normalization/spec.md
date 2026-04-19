# key-normalization Specification

## Purpose
`key_normalization` 提供一个运行期可控的“稳定字符串口径”键匹配策略,用于解决 relations/derived outputs 中 `1` 与 `"1"` 等跨来源类型不一致导致的 miss/分组拆分问题. 该能力为 `EXPERIMENTAL`,默认关闭(`raw`).
## Requirements
### Requirement: `key_normalization` MUST be a validated opt-in runtime option (default `raw`)
系统 MUST 提供一个运行期开关 `key_normalization`,取值域为:

- `raw`: 保持现有 key 口径(默认)
- `auto_str`: 使用稳定字符串口径做 key 匹配(仅在未显式配置 cast 时作为缺省策略生效)
- `force_str`: 强制使用稳定字符串口径做 key 匹配(即使显式配置 cast 也会在最终匹配边界做字符串规范化)

系统 MUST 在对外入口对该字段进行校验;未知取值 MUST fail-fast(编译期/启动期均可).

该开关 MUST 可在以下入口启用并最终落到 execution core 的运行期上下文(例如 `ExecutionRequest`/runtime context):

- yaml_dsl `run/compile`(RunOptions)
- workflow `run_workflow`(入口参数)
- IR/Python-only(直接构造 `ExecutionRequest`)

#### Scenario: unknown key_normalization is rejected
- **GIVEN** 用户传入 `key_normalization="whatever"`
- **WHEN** 系统开始编译或运行
- **THEN** 系统 MUST fail-fast 并提示仅支持 `raw|auto_str|force_str`

### Requirement: `key_normalization` EXPERIMENTAL warning MUST be visible by default

当用户启用 `key_normalization` 的非 `raw` 模式时,系统 MUST 在一次运行内至少发出一次包含 `EXPERIMENTAL` 的提示,且该提示在默认配置下 MUST 可见(不要求用户额外挂载 observer/hook,也不要求显式开启 fallback logger)。

该提示仍需满足原有约束:

- MUST 包含当前启用的 `key_normalization` 值
- MUST NOT 包含任何明细 key 值
- SHOULD 在一次运行内去重(避免刷屏)

#### Scenario: enabling key_normalization emits a visible experimental warning by default
- **GIVEN** 调用方启用 `key_normalization="auto_str"`(或 `"force_str"`)
- **AND** 调用方未注册任何 observer/hook,也未显式开启 fallback logger
- **WHEN** 系统开始运行
- **THEN** 系统 MUST 发出一次包含 `EXPERIMENTAL` 的提示,且该提示在默认配置下可见

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
- relations 在构建“需要匹配的 mapping 的规范化视图”时的 collision 处理,见下方 requirement(`relations mapping collisions after normalization...`),并保持 redacted

### Requirement: relations mapping collisions after normalization MUST be handled safely by default

当 relations 在构建“规范化后的 mapping 视图”时,若多个不同 raw key 规范化到同一个稳定字符串 key(即发生 collision),系统 MUST 按以下规则安全处理:

- 若 collision 对应的 value 全部 `==`(深度相等),系统 MUST 保留任一值并继续(并发出一次 redacted 告警,便于用户后续清理 loader/data)
- 若 collision 对应的 value 存在差异,系统 MUST fail-fast(避免 silent 选择导致隐性错误)

并且:

- 告警/错误文案 MUST NOT 包含任何明细 key 值
- 告警/错误文案 SHOULD 包含 source/loader 标识、`key_normalization` 模式、collision 计数等上下文信息

#### Scenario: collision with identical values continues with a redacted warning
- **GIVEN** 启用 `key_normalization="force_str"`(或满足进入字符串规范化 key space 的条件)
- **AND** loader 返回的 mapping 同时包含 key `1` 与 `"1"`,且两者规范化后 collision
- **AND** 两个 key 对应的 value 深度相等(`==`)
- **WHEN** 系统构建规范化 mapping 视图并执行 relations lookup
- **THEN** 系统 MUST 继续执行并命中该 mapping
- **AND** 系统 SHOULD 发出一次 redacted 告警提示发生了可安全合并的 collision

#### Scenario: collision with different values fails fast
- **GIVEN** 启用 `key_normalization="force_str"`(或满足进入字符串规范化 key space 的条件)
- **AND** loader 返回的 mapping 同时包含 key `1` 与 `"1"`,且两者规范化后 collision
- **AND** 两个 key 对应的 value 不相等(`!=`)
- **WHEN** 系统构建规范化 mapping 视图
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST NOT 包含明细 key 值

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

### Requirement: loader mapping key-space mismatches MUST be diagnosable and redacted

当 `key_normalization` 与显式 cast(例如 `lookup_cast`/`key.cast`)组合导致“预期 key 口径”与 loader mapping 的实际 key 口径不一致时,系统 MUST 提供可诊断的告警/错误,并满足:

- MUST NOT 泄露明细 key 值
- SHOULD 提供可操作的修复建议(例如调整 cast、改用 `force_str`、统一 loader key 口径)

#### Scenario: auto_str with explicit cast hits only after normalization emits a redacted warning
- **GIVEN** `key_normalization="auto_str"`
- **AND** 存在显式 `lookup_cast`/`key.cast`,使得最终候选 key 口径为非字符串(例如 `int`)
- **AND** loader 返回的 mapping key 口径为字符串(例如 `"1"`)
- **WHEN** 系统发现 cast 后候选 key 命中失败,但对候选 key 做字符串规范化后可以命中
- **THEN** 系统 SHOULD 发出 redacted 告警提示存在 key 口径错配
- **AND** 告警 SHOULD 提示调整 cast 或改用 `force_str`

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

### Requirement: key_normalization MUST propagate into adaptive per-task runtimes
当系统为 `parallel_mode=adaptive` 创建 per-task 子运行时(例如调度器为每个 `LoadRef(keys)` 任务创建隔离 runtime/context 并在提交点回放事件)时,子运行时 MUST 继承本次运行的 `key_normalization` 值,并使用相同的规范化规则参与匹配与诊断.

#### Scenario: adaptive per-task runtime uses the same normalization mode as the parent run
- **GIVEN** 本次运行 `key_normalization="auto_str"`(或 `"force_str"`)
- **WHEN** 系统在 adaptive 下创建 per-task 子运行时并执行 `LoadRef(keys)`
- **THEN** 子运行时 MUST 使用与父运行时相同的 `key_normalization` 值
- **AND** 任何依赖 key_normalization 的命中/告警语义 MUST 与 `seq` 等价

### Requirement: ordered-unique helper MUST be centralized
系统 MUST 提供一个公共的"去重保序"工具函数作为 SSOT，并要求相关模块复用该函数而不是各自维护副本。

该工具函数 MUST：

- 对输入序列按出现顺序去重
- 输出结果 MUST 可预测且稳定

#### Scenario: duplicates are removed while preserving order
- **WHEN** 输入为 `["a", "a", "b"]`
- **THEN** 输出 MUST 为 `["a", "b"]`（或等价的 tuple 形态）
