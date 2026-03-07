# loader-retry-policy Specification

## Purpose
TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.
## Requirements
### Requirement: Loader retry policy 配置模型与默认值
系统 SHALL 提供可配置的 loader retry policy,用于在 loader 调用因**瞬态错误**失败时执行有限的自动重试.
该 policy MUST 支持如下字段(字段名可按实现调整,但语义必须等价):
- `enabled`: bool,默认 `false`
- `should_retry`: 用户提供的可调用对象(或可解析为可调用对象的安全引用),当 `enabled=true` 时 MUST 提供
- `max_attempts`: int,默认 `3`,MUST >= 1,且 MUST <= 5(硬上限)
- `max_elapsed_seconds`: float,默认 `10`,MUST > 0,且 MUST <= 20(硬上限)
- `backoff`: `"fixed" | "exponential"`,默认 `"exponential"`
- `base_delay_seconds`: float,默认 `0.2`,MUST >= 0
- `max_delay_seconds`: float,默认 `2`,MUST >= 0,且 MUST <= 5(硬上限)
- `jitter`: bool,默认 `true`

系统 MUST 在配置解析/编译阶段校验上述字段类型与范围;任何超过硬上限或为负值/非法枚举的配置 MUST 被拒绝并报告清晰的字段路径.

#### Scenario: 默认关闭无行为变化
- **WHEN** 用户未提供任何 retry policy(YAML/driver 均缺省)
- **THEN** 系统不得发生额外 sleep 或重试;loader 异常语义与当前版本一致

#### Scenario: 超出硬上限被拒绝
- **WHEN** 用户配置 `max_attempts=6`(或 `max_elapsed_seconds=30` / `max_delay_seconds=10`)
- **THEN** 系统 MUST 在配置校验阶段失败并报告对应字段路径

### Requirement: should_retry 回调契约
系统 MUST 在捕获到 loader 抛出的 `Exception` 后(不得捕获 `BaseException`),调用 `should_retry(exc, ctx) -> bool` 判定是否继续重试.
其中 `ctx` MUST 至少包含:
- `loader_name`(等价于 `source_id`)
- `callsite`(例如 `load|load_ref|preload_forever|main_source` 之一,或等价枚举)
- `attempt_num`(从 1 开始的已执行尝试次数)
- `max_attempts`
- `elapsed_seconds`(从第一次尝试开始累计,包含 sleep 时间)

当 `should_retry` 返回 `false` 时系统 MUST 不再重试并传播**原始 loader 异常**.
当 `should_retry` 自身抛出异常时系统 MUST 视为 `false`(不再重试)并传播**原始 loader 异常**.

#### Scenario: should_retry=false 不重试
- **WHEN** loader 第 1 次调用抛出异常且 `should_retry` 返回 `false`
- **THEN** 系统 MUST 立即传播该异常且不得再次调用该 loader

### Requirement: Retry runner 语义(次数/耗时/退避)
当 `enabled=true` 且 `should_retry` 返回 `true` 时,系统 MUST 在以下约束内执行重试:
- 尝试次数上限:最多执行 `max_attempts` 次调用(包含首次尝试);当 `attempt_num == max_attempts` 时 MUST 不再重试.
- 累计耗时上限:当 `elapsed_seconds >= max_elapsed_seconds` 时 MUST 不再重试.
- 退避:每次决定重试时 MUST 计算下一次尝试前的 sleep 时长 `delay_seconds`:
  - `backoff="fixed"`:`delay_seconds = min(base_delay_seconds, max_delay_seconds)`
  - `backoff="exponential"`:在第 `attempt_num` 次尝试失败并决定重试时,`delay_seconds = min(base_delay_seconds * (2 ** (attempt_num - 1)), max_delay_seconds)`
  - 当 `jitter=true` 时,系统 MUST 对 `delay_seconds` 做随机扰动并保证其落在 `[0, max_delay_seconds]` 区间内(例如在 `[0, delay_seconds]` 内取值再 clamp).

#### Scenario: attempt 上限生效
- **GIVEN** `enabled=true` 且 `max_attempts=2`
- **WHEN** loader 连续两次抛出异常且 `should_retry` 始终返回 `true`
- **THEN** 系统 MUST 仅调用 loader 两次并在第 2 次失败后传播异常

### Requirement: 全局策略与 per-loader 覆盖的解析
系统 MUST 支持全局默认 policy 与按 `loader_name==source_id` 的 per-loader 覆盖 policy.
系统 MUST 以“overlay”方式构建 effective policy:
- per-loader policy 中未提供的字段 MUST 继承自全局默认 policy
- driver 注入的字段 MUST 覆盖 YAML/DSL 编译产物中同名字段
- per-loader policy MUST 覆盖全局默认 policy(无论来源)

#### Scenario: 单个 loader 禁用重试
- **GIVEN** 全局默认 policy `enabled=true`
- **WHEN** `sources.customers.retry.enabled=false`
- **THEN** customers loader 调用不得发生重试;其它未覆盖 loader 仍按全局 policy 执行

### Requirement: iterable/generator 的重试边界
系统 MUST 仅对“调用 loader 得到返回值”这一动作做重试.
当 loader 返回 iterable/generator 且其在后续迭代过程中抛出异常时,系统 MUST 不进行通用自动重试(异常直接传播).

#### Scenario: generator 迭代抛错不重试
- **WHEN** main_source loader 返回 generator,且在后续 `next()` 时抛出异常
- **THEN** 系统 MUST 传播该异常且不得重新调用 main_source loader
