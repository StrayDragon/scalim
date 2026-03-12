## ADDED Requirements

### Requirement: Excel sinks 支持公式注入防护并允许显式写公式
当使用内建 Excel sinks 输出数据时,系统 MUST 提供“公式注入防护”能力,避免不可信字符串在 Excel 中被当作公式执行.

系统 MUST 支持两种模式:
- **escape**: 将疑似公式的字符串以文本形式写出(例如前缀转义),确保 Excel 不会将其作为公式执行
- **allow**: 允许将字符串原样写入,使其可被 Excel 当作公式解析(用于可信场景主动写公式)

系统 MUST 明确规定“疑似公式字符串”的识别规则(至少覆盖 `=`, `+`, `-`, `@` 前缀,允许忽略前导空白).

#### Scenario: escape 模式将 `=HYPERLINK(...)` 写成文本
- **GIVEN** 某个输出字段来自不可信输入且值为字符串 `=HYPERLINK("http://evil", "x")`
- **WHEN** Excel sink 以 escape 模式写出该值
- **THEN** 该单元格在 Excel 中 MUST 以纯文本显示(不得作为公式执行)

#### Scenario: allow 模式允许写公式
- **GIVEN** 用户显式启用 allow 模式且输出值为字符串 `=1+1`
- **WHEN** Excel sink 写出该值
- **THEN** 该单元格 MAY 被 Excel 解析为公式

### Requirement: file sinks 支持可选的并发写出保护(避免静默覆盖)
当多个进程/实例可能同时写入同一输出路径时,系统 MUST 允许用户启用低成本的并发写出保护,以避免“最后写入者覆盖”静默发生.

启用保护时:
- 系统 MUST fail-fast 并给出清晰错误信息(包含目标路径与恢复建议:改用唯一路径/外部加锁/清理锁)
- 系统 MUST best-effort 清理其并发保护资源(例如 lock 文件)

#### Scenario: 并发保护启用且锁已存在时 fail-fast
- **GIVEN** 并发保护启用且目标路径的锁已存在
- **WHEN** sink 尝试 close 并写出
- **THEN** close MUST 失败并提示冲突与恢复建议
