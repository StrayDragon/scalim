# Perf ROI 判断链路（2026-08-11）

> 用途：之后 review「删了什么 / 留下什么 / 为何避开 memo / 下一步采什么」时的 SSOT。  
> 证据根：`.tmp/evidence/`、`.tmp/obs-demo/runs/mid_20260811_111812/`（不入库；本文件只记路径与数字摘要）。

## 0. 硬约束（先于一切候选）

| # | 约束 | 来源 |
|---|------|------|
| C1 | **内存节省优先**；对「用缓存换时间」的峰值 RSS 容忍低 | 产品定位 + 本次用户确认 |
| C2 | 先证据后改代码；复现落 `.tmp/`；不引入新三方依赖 | `scalim-perf-investigation` skill |
| C3 | 框架内优化优先；尽量不改用户侧业务代码 | 同上 |
| C4 | Python 3.6 runtime 兼容；Policy 闭集用 `StrEnum` | 根 `AGENTS.md` |
| C5 | 合成数据只定 ROI **边界**；真实业务验证才能合入默认路径 | skill Gotchas |

**推论（本次锁定）**：

- **不推进 / 不产品化** `call_by` 结果 memo（含把 `SCALIM_EXP_CALL_BY_MEMOIZE_*` 做成默认或 DSL 开关）。
- **不推进** 跨批次隐式缓存（重叠 load_ref 留存）——与「批次边界释放」内存叙事冲突。
- 可接受的加速路径：减少调用次数 / 减少临时对象 / 更早释放 / 显式用户侧 preload（`PreloadCache` / `preload_forever`，内存成本由用户承担）。

## 1. 证据清单（本次采样，均 ≤10GB）

| ID | 实验 | 路径 | 关键数字 |
|----|------|------|----------|
| E1 | ExcelSink aligned-index：**真** A/B（每行重建索引 vs 主路径） | `.tmp/evidence/excel_sink_write_row_aligned/20260811_111018_vs_uncached/result.json` | write **~1.02×**；已合入 `527c106f` |
| E2 | dep-tuple memo 矩阵（含 mid_fit / uniq>cache） | `.tmp/evidence/dep_tuple_cardinality/20260811_111019/matrix_summary.json` | uniq≤cache：**~1.9–2.7×**；uniq>cache：**~0.52–0.58× 变慢** + RSS↑ |
| E3 | write-precompute small 引擎矩阵 `--allow-rss-gb 10` | `.tmp/evidence/write_precompute_scale/20260811_111116/result.json` | 6/6 golden；峰值 **~53–468 MB** ≪ 5GiB 驻留估算 |
| E4 | obs mid 端到端（200k fact，soft cap 8GB） | `.tmp/obs-demo/runs/mid_20260811_111812/sampling_matrix.json` | baseline **22.6s**；bench tax **+5.6%**；debug **+48.9%** |
| E4b | mid bench stage | `.../runs/bench/run_stats.json` | compute **4.50s** / loader **1.45s** / write **1.28s** |

旧 repro「baseline vs FastExcelSink」作废：主路径已含缓存，差值≠未落地优化（见 E1 note）。

## 2. 决策树（如何判「删 / 留 / 改门控」）

```text
候选方向
  ├─ 是否依赖「框架代持跨行/跨批缓存」换时间？
  │    ├─ 是 → 与 C1 冲突 → 移出候选池（记理由）
  │    └─ 否 ↓
  ├─ 合成/端到端证据是否显示 wall 收益 < ~3% 且无内存收益？
  │    ├─ 是 → 关闭探索 / 不转正（记 E*）
  │    └─ 否 ↓
  ├─ 是否已被主路径能力覆盖？
  │    ├─ 是 → 删草案，指到 archive（README「已落地」）
  │    └─ 否 ↓
  └─ 保留 notplan：写清「内存影响方向」+「转正门控（禁止依赖 memo）」
```

## 3. 候选逐项结论

| 候选 | 动作 | 判断链路（约束→证据→结论） |
|------|------|---------------------------|
| ExcelSink `write_row_aligned` 索引缓存 | **关闭探索**（已实现） | C2 → E1：主路径已有；增量 ~2% → 不再开 change |
| `call_by` EXP memo 产品化 | **不推进** | C1 → E2：仅工作集≤cache 时加速，否则变慢且 RSS↑ → 禁止默认化；EXP 可留作实验，不作路线图 |
| `c999-overlap-optimization` | **已删** | C1 → 提案本体即跨批缓存 → 与批次释放叙事冲突；无 E* 证明「不增峰」 |
| `c1-runtime-performance-profiles` | **已删** | 草案自述等 hotpath；主路径已落地 write-precompute/fusion/chunk 并行（README 已落地表）→ 档位无近缺口；`speed` 档鼓励内存换时间与 C1 相悖 |
| `c0-call-by-multi-output-fusion` | **保留** | 行内一次调用写多字段；默认不增峰；对齐 E4b compute 占主导 |
| `c2-batch-call-by` | **保留并改门控** | 列式可减 `List[Dict]` 打包（潜在 **减** 分配）；门控改为「fusion 之后仍调用次数主导」，**禁止**以 memo 为前置 |
| `c10-adaptive-cache-explicit-locks` | **保留（非 perf ROI）** | 正确性/free-threaded；非加速提案 |
| `c1-preloaded-cache-safety-check` | **保留（安全）** | 误用 warning；不新增默认缓存 |
| 其它 YAML/LSP/viz notplan | **不动** | 非本次 perf 范围 |

## 4. 本次从 notplan 移除

| 原目录 | 删除日 | 原因（短） |
|--------|--------|------------|
| `c999-overlap-optimization` | 2026-08-11 | 跨批缓存 ↔ 内存优先冲突；无「不增峰」证据 |
| `c1-runtime-performance-profiles` | 2026-08-11 | 主路径优化已覆盖等待条件；speed 档与 C1 冲突 |

## 5. 非 memo、内存友好的后续方向（按推荐序）

| 优先级 | 方向 | 预期内存 | 预期时间杠杆 | 建议下一证据 |
|--------|------|----------|--------------|--------------|
| P1 | **显式 multi-output / call group**（现 `c0`） | 持平或略降（少中间字段物化） | 同行多字段：调用 N→1 | 合成「一行多派生共享一次 call」shape；对拍调用次数 + RSS |
| P2 | **热路径临时对象减配**（value list / dep tuple 复用、少建临时 dict） | **降** 或持平 | 视分配占比；对齐 E4b compute | memray 分配热点 on mid/wide compute；禁止引入缓存 |
| P3 | **batch call_by**（现 `c2`，opt-in） | 倾向降（去行 dict 打包） | 宽表薄逻辑 | 同 P1 之后；门控见上；须收束 `$ctx` |
| P4 | **写出路径**（openpyxl / 列式流式已有） | 流式已优；避免大缓冲 | E4b write ~1.3s；E1 微优化已吃完 | 仅当真实 xlsx wall 占比高时再开题 |
| P5 | **更早/更广字段释放**（consume-clear / row release 续作） | **降** | 间接（GC/缺页） | 已有 A/B 基线；找仍驻留的 retained_fields 案例 |
| — | 用户显式 `PreloadCache` / `preload_forever` | 用户自担 | IO/loader | **不是**框架隐式 memo；文档说清 |

**明确不做（近期）**：框架默认 memo、跨批 overlap cache、performance `speed` 档默认化。

## 6. Review 清单（后人核对用）

- [ ] 约束 C1–C5 是否仍成立？若「可接受有界 memo」变更，须新开采样，不得静默复活已删提案。
- [ ] E1–E4 路径是否仍可读？若 `.tmp` 被清，须按同参重跑并更新本节数字。
- [ ] 新候选是否通过 §2 决策树？通过后才 `llman-sdd-propose`。
- [ ] 任何「缓存」提案必须写明：**生命周期（行/批/run）**、**峰值 RSS 方向**、**谁承担成本（框架默认 vs 用户显式）**。
- [ ] 合入默认路径前：值等价 + RSS 不劣于基线（建议峰增 ≤0% 或有文档化的用户 opt-in）。

## 7. 关联指针

- Skill：`.claude/skills/scalim-perf-investigation/SKILL.md`（索引已按本次结论更新）
- notplan 索引：`llmanspec/notplan/README.md`
- 已落地 perf：`c10-write-precompute` / `c20-rowwise-fusion` / `c30-refloader-chunk-parallelism` / consume-clear / row-release

## 8. 续采（2026-08-11，P1 multi-output + P2 memray）

### E5 — multi-output ROI 边界

路径：`.tmp/evidence/multi_output_call_group/20260811_114514/`  
脚本：`.tmp/repro/multi_output_call_group/repro-multi-output-call-group.py`

| 子实验 | 结论 |
|--------|------|
| 薄逻辑 micro（50k×40）：separate vs multi tuple/dict | **multi 更慢**（tuple ~0.87×，dict ~0.31×）— 打包/解包压过调用节省 |
| 共享重算 micro（20k×40，body×20）：dup-heavy vs multi once | **~12.5×**；RSS Δ≈0；`checksum_ok` |
| Engine 现网（50k×40 call_by，fusion_groups=1） | **2M calls / 7.4s**；RSS Δ ~176MB（含 InMemory sink）；**c20 不减 call_by 次数** |

**判断**：multi-output **只**在「同行多字段共享昂贵中间结果」时有墙钟 ROI；薄字段纯减调用不够。转正门控应要求 **共享体重算 shape** 证据，而非仅调用次数。

### E6 — wide compute memray（减分配方向）

路径：`.tmp/evidence/wide_compute_alloc/20260811_114549/`（`memray.bin` / `flamegraph.html` / `table.html`）  
shape：30k×80 call_by，discard sink，无 memo。

| 指标 | 值 |
|------|-----|
| wall | ~8.4s；calls 2.4M |
| RSS Δ | ~12.6 MB |
| memray peak | ~38 MB；累计分配 ~231 MB / 114k allocs |

**Top alloc by size（框架内）**：

1. `batch/executor.py:_extract_results` ~117 MB — 每行新建 `dict` 装全 target 字段（即使用 discard sink，batch 路径仍 materialize `List[RowData]`）
2. `dataclasses._create_fn` ~38 MB — 导入/dataclass 构造噪声（次要）
3. `compute/fusion.py:_execute_fused_dense` ~22 MB — 融合路径上的临时 `args_list`/`dep_args` 等
4. `context._DenseFieldStorage.__init__` ~20 MB — 每字段 `values=[None]*n` + `bytearray`

**判断（P2 优先杠杆，内存友好）**：

1. **绕开 / 推迟 `_extract_results` 行 dict**：对齐已有 `write_row_aligned` 路径，避免 batch 末再组 `Dict`（预期降分配与 GC，不增峰）。
2. **Dense storage / fusion 临时 list 复用**：有界复用缓冲区（批生命周期），禁止跨批缓存。
3. multi-output 仍按 E5 门控，与减分配正交。

## 9. 写出策略（有手动、无自动）— draft 路线 D1–D4

人类文档 SSOT 增补：`docs/doc/getting-started/excel-column-residency.md` §3。

| 事实 | 说明 |
|------|------|
| YAML books | 强制行流式；**无** streaming/residency authoring |
| `DemandRunRuntimeOptions.excel_column_residency` | Python 可设；仅 IR `excel`+`streaming=False` 生效 |
| `WorkflowRunOptions.demand` | 嵌套同一 runtime；无独立字段 |
| 自动选型 | **无**；禁止静默行↔列 / HOLD↔WINDOW |

**Draft change 序列（notplan → propose）**：

| ID | 主题 | 行为？ |
|----|------|--------|
| D1 `c10-output-write-path-decision-matrix` | 决策矩阵文档（本轮已写入站点 + 本链路） | 无 |
| D2 `c20-streaming-column-excel-write-column-aligned` | WINDOW sink 补 `write_column_aligned` | **已实现**（`streaming_column_excel.py`） |
| D3 `c30-output-write-layout-python-policy` | 闭集 Python 写出布局策略面 | active SDD（propose→readyToImplement） |
| D4 `c40-output-write-layout-advisory` | run_stats 建议，默认不改行为 | 设计稿 |

原则：YAML 简单默认；Python 显式；自主先做 advisory，禁止静默 auto。
