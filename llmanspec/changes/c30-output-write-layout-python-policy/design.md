# Design: OutputWriteLayout

## Deep-dive 锁定（2026-08-11）

| # | 决策 | 锁定 | 理由 |
|---|------|------|------|
| D1 | Enum 名 | `OutputWriteLayout`；值 `row_stream` / `column_hold` / `column_window` | 闭集 Policy SSOT；builtin str 出 |
| D2 | CSV + **显式** `column_window` | **fail-fast** | 无 WINDOW sink；禁止静默映射 HOLD |
| D2b | CSV + **未设** layout + residency=WINDOW | 仍推导 `column_hold`（与今日工厂一致） | CSV 本就忽略 residency；禁止行为漂移 |
| D3 | 优先级 | 显式 layout > 推导(streaming+residency) > 默认 | 与 c40 覆盖叙事一致 |
| D4 | 旧字段 | 迁移窗保留；未设 layout 时推导 | 无静默行为漂移 |
| D5 | composition | 仅允许 effective `row_stream`；显式 `column_*` 或 residency=WINDOW → fail-fast | 推广现 r176；HOLD+composition 今日合法故保留 |
| D6 | 手写 sink | `ExecutionRequest.sink` 优先，layout 不改手写路径 | 最高自主 |
| D7 | 自动选型 | **不做**（D4 advisory 另案） | 内存优先可解释性 |
| D8 | New knob gate | 仅 Python；换部署不改 YAML | AGENTS Hard Rules |
| D9 | 性能预算 | 默认路径 median 墙钟/peak RSS 回归 **≤ ~5%**（≥5 跑） | 布局解析必须 O(1)/可忽略；不得改 sink 热路径 |

### 推导表（未设显式 layout）— 已对拍 `_create_file_sink`

| 条件 | effective layout | 今日 concrete sink |
|------|------------------|-------------------|
| 有 `output_composition` 且 residency≠WINDOW | `row_stream` | 行式 tee / CSVSink/ExcelSink |
| 有 `output_composition` 且 residency=WINDOW | fail-fast（先于 layout） | 同今日 |
| `streaming=True` + excel + WINDOW | fail-fast | 同今日 |
| `streaming=True`（其余） | `row_stream` | `CSVSink` / `ExcelSink` |
| `streaming=False` + excel + HOLD | `column_hold` | `ColumnExcelSink` |
| `streaming=False` + excel + WINDOW | `column_window` | `StreamingColumnExcelSink` |
| `streaming=False` + csv（**含** residency=WINDOW） | `column_hold` | `ColumnCSVSink`（residency 忽略） |

显式 `column_window` + csv → fail-fast。  
显式 `column_*` + composition → fail-fast。  
未设 layout + composition + HOLD → 合法（effective `row_stream`）。

### 工厂映射

| effective | csv | excel |
|-----------|-----|-------|
| `row_stream` | `CSVSink` | `ExcelSink` |
| `column_hold` | `ColumnCSVSink` | `ColumnExcelSink` |
| `column_window` | fail-fast | `StreamingColumnExcelSink` |

实现注意：未设 layout 时 MUST 先 `resolve` 再按表选 sink，结果类型与上表「今日 concrete」列一致；解析本身不得引入可测热路径开销。

## 性能门禁（校准）

- **场景**：未设 `output_write_layout` 的小 IR 写出：`csv` streaming、`excel` HOLD、`excel` WINDOW（各场景独立）。
- **指标**：墙钟（`perf_counter`）与 peak RSS（`resource.RUSAGE_SELF.ru_maxrss`，Linux KB）。
- **方法**：每场景 **≥5** 次；报告 **median**；**子进程隔离**（避免同进程 excel 抬高后续 csv 的 `ru_maxrss`）；与 HEAD 源码 **交错采样**（取消冷热偏差）。
- **阈**：相对 HEAD 基线 median，墙钟与 RSS 各自回归 **≤ ~5%**。
- **落盘**：`.tmp/evidence/c30-output-write-layout/`（不提交）。

### 参数扫描（≤10GB，2026-08-11）

证据：`param_probe.json`。主机可用 ~17GiB；硬顶 **10GB**。

| 布局 | 主导参数 | 观察 |
|------|----------|------|
| `row_stream` CSV | **rows**（cols 次要） | RSS 几乎持平 ~30–40MB；墙钟近似随 rows×cols 线性 |
| `column_hold` Excel | **cells≈rows×cols** | RSS ≈ **120–140 B/cell**（短字符串）；墙钟 ~0.32–0.64 s/1k rows（随 cols） |
| `column_window` Excel | rows×cols 主吃墙钟 | RSS 远低于 HOLD（同 50k×50：HOLD 0.33GB vs WINDOW 0.07GB） |

推荐回归基数（墙钟数十秒、RSS≪10GB）：

| 场景 | rows | cols | batch | 探针墙钟 | 探针 RSS |
|------|------|------|-------|----------|----------|
| csv_stream | 100k | 50 | 1000 | ~5.7s | ~0.04GB |
| excel_hold | 50k | 100 | 1000 | ~32s | ~0.61GB |
| excel_window | 100k | 100 | 1000 | ~66s | ~0.09GB |

HOLD 逼近 10GB 需 ~cells≳70M（按 ~130 B/cell）；本门禁不强制顶满 10GB——布局解析开销在「数十秒写出」上更可辨，且避免本机抖动/写盘时间爆炸。

### 已跑结果

- 小基数 interleaved（N=7, 3k×12）：PASS（见 `interleave_compare.json`）
- 大基数 interleaved（N=5）：**PASS**（`large_interleave_compare.json`）
  - csv 100k×50：墙钟 +1.61%，RSS -0.20%
  - HOLD 50k×100：墙钟 +0.46%，RSS +0.03%
  - WINDOW 100k×100：墙钟 -0.15%，RSS +0.56%
- HOLD 天花板单次（`ceiling_hold.json`）：100k×200 ≈ 2.25GB / 124s；150k×150 ≈ 2.16GB / 140s（均 ≪10GB）

## 测试 seams（确认）

1. **Public options**：`DemandRunRuntimeOptions(output_write_layout=...)` 拒 str；接受 Enum  
2. **Factory**：`_create_file_sink` / run_ir 装配按 effective layout 选类型  
3. **Fail-fast**：composition+显式 column_*；显式 csv+column_window；YAML 声明 layout 字段  
4. **Regression**：未设 layout 时 sink 类型与今日相同（对拍表，含 csv+WINDOW→ColumnCSVSink）  
5. **Perf**：上节多跑门禁

无新 `.feature` harness（仓库未开 `bdd:`）；用 pytest 覆盖 seams 1–4。

## 非目标

- YAML layout 字段  
- 默认改 WINDOW  
- HOLD 内部去 dict 存储重构  
- D4 advisory 实现（可 depends 本 change 命名）
- 为 layout 引入 memo / 跨批 cache
