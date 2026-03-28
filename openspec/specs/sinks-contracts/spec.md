# sinks-contracts Specification

**状态: ✅ 已实现**
## Purpose
定义 sink 接口稳定性与可选依赖提示规范,确保内建与外部 sink 的长期兼容、可诊断性与一致行为.
## Related Code (as implemented)
- `src/IMPL_ROOT/sinks/sink_base.py` (sink interfaces)
- `src/IMPL_ROOT/sinks/sink_csv.py`
- `src/IMPL_ROOT/sinks/sink_excel.py` (optional `openpyxl`)
- `src/IMPL_ROOT/sinks/sink_pandas.py` (optional `pandas`)
- `tests/test_sinks_base.py`
- `tests/test_sinks_additional.py`
- `tests/test_sinks_optional_imports.py`
- `tests/test_csv_flush_policy.py`
- `tests/test_sinks_real.py`
## Requirements
### Requirement: Sink 契约稳定
系统 MUST 保持 `ISink`/`IRowSink`/`IColumnSink`/`BaseRowSink` 等接口契约稳定,并确保内建 sinks 满足契约.

#### Scenario: 旧 sink 实现可继续工作
- **WHEN** 现有 sink 继承 `BaseRowSink` 或实现 `IRowSink`
- **THEN** 不需修改即可运行

### Requirement: 可选依赖错误提示清晰
系统 MUST 对可选依赖(如 Excel 的 `openpyxl`)提供一致且可诊断的错误路径.

#### Scenario: 缺少可选依赖
- **WHEN** 在未安装依赖时导入或使用相关 sink
- **THEN** 抛出明确且可读的错误信息

### Requirement: file sinks 写入前创建输出目录
系统 MUST 在 file sinks(如 CSV/Excel)写入输出文件前确保 `output.path` 的父目录存在;当父目录不存在时系统 MUST 以 best-effort 方式创建目录(`mkdir(parents=True, exist_ok=True)`).

#### Scenario: 输出目录不存在仍可写出
- **WHEN** 用户直接构造并使用 file sink,且 `output.path` 的父目录不存在(例如 `CSVSink("a/b.csv")` 的 `a/` 不存在)
- **THEN** sink close 写出结果时系统应自动创建父目录并成功生成输出文件

### Requirement: file sinks 原子替换失败路径可清理且可诊断
系统 MUST 在 file sinks(如 CSV/Excel)采用“临时文件 + close 时原子替换”的写出策略时,确保 replace 失败路径具备 best-effort 清理与可诊断性:

- replace 失败时系统 MUST 以 best-effort 方式清理临时文件(避免残留 `.tmp` 垃圾文件).
- 若清理失败,系统 MUST 通过日志或错误信息暴露临时路径与目标路径,便于用户手动处理.

#### Scenario: replace 失败时临时文件被清理
- **GIVEN** file sink 已写入临时文件
- **WHEN** close 阶段的原子替换操作失败
- **THEN** close MUST 抛出异常
- **AND** 系统 MUST best-effort 清理临时文件(无残留或明确提示其路径)

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

### Requirement: CSV sinks MUST escape spreadsheet formulas by default

当使用内建 CSV sinks 输出数据时,系统 MUST 提供“公式注入防护”能力,避免不可信字符串在 Excel 等工具中被当作公式执行或触发外连.

系统 MUST 支持两种模式:
- **escape**(默认): 将疑似公式的字符串以文本形式写出(例如前缀转义),确保工具不会将其作为公式执行
- **allow**: 允许将字符串原样写入,使其可被工具当作公式解析(用于可信场景主动写公式)

系统 MUST 明确规定“疑似公式字符串”的识别规则(至少覆盖 `=`, `+`, `-`, `@` 前缀,允许忽略前导空白).

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头与数据行。

#### Scenario: escape mode writes formula-like values as text
- **GIVEN** 某个输出字段来自不可信输入且值为字符串 `=HYPERLINK("http://evil", "x")`
- **WHEN** CSV sink 以默认 escape 模式写出该值
- **THEN** 输出的 CSV 字段值 MUST 以 `'` 前缀写出,以避免被解析为公式

#### Scenario: allow mode preserves raw values
- **GIVEN** 用户显式启用 allow 模式且输出值为字符串 `=1+1`
- **WHEN** CSV sink 写出该值
- **THEN** 输出的 CSV 字段值 MUST 保持为 `=1+1`

### Requirement: file sinks 支持可选的并发写出保护(避免静默覆盖)
当多个进程/实例可能同时写入同一输出路径时,系统 MUST 允许用户启用低成本的并发写出保护,以避免“最后写入者覆盖”静默发生.

启用保护时:
- 系统 MUST fail-fast 并给出清晰错误信息(包含目标路径与恢复建议:改用唯一路径/外部加锁/清理锁)
- 系统 MUST best-effort 清理其并发保护资源(例如 lock 文件)

#### Scenario: 并发保护启用且锁已存在时 fail-fast
- **GIVEN** 并发保护启用且目标路径的锁已存在
- **WHEN** sink 尝试 close 并写出
- **THEN** close MUST 失败并提示冲突与恢复建议

### Requirement: Sinks MAY implement aligned-write fastpath without breaking existing contracts
系统 MUST 在保持现有 `ISink`/`IRowSink`/`IColumnSink` 契约可用的前提下，允许 sinks 通过“可选方法”提供 aligned-write fastpath（见 `sink-fastpath` capability）。

内建 sinks MUST 覆盖该 fastpath（当实现类型适用时），并通过测试保证：
- fastpath 与现有接口写出结果一致
- fastpath 不改变 close/flush 等资源语义

#### Scenario: built-in sinks produce identical output via fastpath
- **WHEN** 内建 sink 同时支持现有接口与 aligned-write fastpath
- **THEN** 在相同输入下两条路径写出的结果 MUST 一致
