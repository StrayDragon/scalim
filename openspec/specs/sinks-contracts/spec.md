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
