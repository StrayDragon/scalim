# 2026-07-18 — tabular bus object + sink accept / opt-in precheck

## 变更摘要

- `InMemoryRows` 细胞放宽为任意 Python `object`（只校验表结构）；**禁止**中间态静默 `str()`。
- `FieldValue` / `FIELD_VALUE_TYPES` 降为 **内建 Excel 推荐闭集**（文档 + opt-in 预检参考），不再是 ROWS 门禁。
- Python SSOT：`SinkTypePrecheck`（`OFF` 默认 / `ON`）经 `DemandRunRuntimeOptions.sink_type_precheck` / `ExecutionRequest.sink_type_precheck` / `ExcelSink(type_precheck=...)`。
- 写出失败 / CM 异常：调用 `discard()`，**不** promote 最终半成品（Excel/CSV temp 清理）。

## 迁移

1. 依赖「非 FieldValue 在 `InMemoryRowsSink` 必 TypeError」的测试/代码 → 删除该断言，或改用 `SinkTypePrecheck.ON`。
2. 开发期想早失败：`DemandRunOptions.runtime.sink_type_precheck = SinkTypePrecheck.ON`。
3. numpy/`Timestamp` 等：默认可进总线；Excel 写出仍按 openpyxl；需要早反馈再开预检。**不要**期待框架静默 coerce。

## 非目标

- YAML knobs
- 自动 `np.datetime64` → `datetime`
- 改变 workflow `keep_on_failure` 默认
