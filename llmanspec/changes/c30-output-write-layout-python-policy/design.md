# Design: OutputWriteLayout

## Deep-dive 锁定（2026-08-11）

| # | 决策 | 锁定 | 理由 |
|---|------|------|------|
| D1 | Enum 名 | `OutputWriteLayout`；值 `row_stream` / `column_hold` / `column_window` | 闭集 Policy SSOT；builtin str 出 |
| D2 | CSV + `column_window` | **fail-fast** | 无 WINDOW sink；禁止静默映射 HOLD |
| D3 | 优先级 | 显式 layout > 推导(streaming+residency) > 默认 | 与 c40 覆盖叙事一致 |
| D4 | 旧字段 | 迁移窗保留；未设 layout 时推导 | 无静默行为漂移 |
| D5 | composition | 仅允许 effective `row_stream`；否则 fail-fast | 推广现 r176 |
| D6 | 手写 sink | `ExecutionRequest.sink` 优先，layout 不改手写路径 | 最高自主 |
| D7 | 自动选型 | **不做**（D4 advisory 另案） | 内存优先可解释性 |
| D8 | New knob gate | 仅 Python；换部署不改 YAML | AGENTS Hard Rules |

### 推导表（未设显式 layout）

| 条件 | effective layout |
|------|------------------|
| 有 `output_composition` | `row_stream`（若 residency=WINDOW → 仍 fail-fast，与今日一致） |
| `streaming=True`（或默认行文件） | `row_stream` |
| `streaming=False` + excel + HOLD | `column_hold` |
| `streaming=False` + excel + WINDOW | `column_window` |
| `streaming=False` + csv | `column_hold` |

显式 `column_window` + csv → fail-fast。  
显式 `column_*` + composition → fail-fast。

### 工厂映射

| effective | csv | excel |
|-----------|-----|-------|
| `row_stream` | `CSVSink` | `ExcelSink` |
| `column_hold` | `ColumnCSVSink` | `ColumnExcelSink` |
| `column_window` | fail-fast | `StreamingColumnExcelSink` |

## 测试 seams（确认）

1. **Public options**：`DemandRunRuntimeOptions(output_write_layout=...)` 拒 str；接受 Enum  
2. **Factory**：`_create_file_sink` / run_ir 装配按 effective layout 选类型  
3. **Fail-fast**：composition+column_*；csv+column_window；YAML 声明 layout 字段  
4. **Regression**：未设 layout 时 sink 类型与今日相同（对拍表）

无新 `.feature` harness（仓库未开 `bdd:`）；用 pytest 覆盖上述 seams。

## 非目标

- YAML layout 字段  
- 默认改 WINDOW  
- HOLD 内部去 dict 存储重构  
- D4 advisory 实现（可 depends 本 change 命名）
