# Design: 低漂移自我观测

## 原则

1. **Correctness over glitter**：证据错误比证据少更糟。
2. **Same event plane**：只订阅已有 lite `EventType`；不另开热路径 instrumentation。
3. **Opt-in + warn**：默认静默；`bench` 显式装配；高影响面 MUST warn。
4. **Workflow-first**：多 demand 必须以 `nodes[]`（或等价）呈现，禁止只暴露「最后一次 pipeline」指标当全貌。
5. **Structured readable**：运行时 SSOT = dataclass；落盘 JSON（py3.6 stdlib）；人类 TOON 仅离线可选。

## 「假零」与本 change 的关系

| 现象 | 根因 | 本 change | c55 |
|------|------|-----------|-----|
| Relation / Perf 末态为空或仅 metrics | 共享 observer `PIPELINE_START` reset | **修：快照累加 / nodes[]** | — |
| `stages.write == 0` | 现代 sink 未进 WRITE_* 计时 | 文档标明「write 归因未完成」 | **修计时** |

## Profile 矩阵

| Profile | 订阅 | 警告 | 用途 |
|---------|------|------|------|
| baseline | 无 | — | 墙钟/RSS 对照 |
| bench | PIPELINE/BATCH/STAGE/LOADER(+summary)/OUTPUT_END；可选 memory(psutil) | 无（或轻提示含观测税） | 日常自我观测 |
| bench_plus | + StageMemory 疏采样 | memory 采样间隔说明 | 内存趋势 |
| debug | + relation / operator_span / viz(summary) | **MUST warn** 高开销 | 短窗深挖 |

## 警告文案契约（摘要）

启用下列任一能力时 MUST 打 warning（级别：UserWarning 或 structured log）：

- `RELATION_LOOKUP` 全量诊断（O(row)）
- `OPERATOR_SPAN` / field_compute top-N
- `viz_trace` / `payload_policy=full`
- `include_batch_lines` 或全量 `batches[]` 持久化在超大 batch 数时

警告 MUST 含：能力名、为何贵、建议改用的低漂移替代（如 bench）。

## Viz

- 文件：与 viz run 目录 sibling `run_stats.json`
- MUST NOT 改 `viz_snapshot.json` 图契约
- MAY：`meta.viz.run_stats` 相对路径

## 证据消费方

- **用户**：判断 loader / compute / call_by / relation 热点
- **框架**：A/B 优化前后同一 schema 对比（`.tmp/evidence` 或 CI）
- 两者共用同一 run_stats；报告须区分 `profile` 与是否含观测税
