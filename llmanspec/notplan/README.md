# notplan

本目录用于存放**尚未进入 llmanspec 正式变更工作流**的暂缓提案(例如 proposal/design/tasks),方便先沉淀候选方向与讨论记录。

## 边界与约束

- 本目录**不是** `llmanspec/changes/` 下的 active change；不会被 `llman sdd list` 识别为“可推进的变更”。
- 本目录内容属于 `llmanspec/` 范围：会被 `just llmanspec-sanitize` 扫描(避免把私有字面量带入可共享工件)。
- 这里的草案不要求完备、也不要求可实现；当你准备推进时再“转正”为 active change。

## 如何转正为 active change

1. 使用 `llman-sdd-propose` 创建正式变更(建议遵循 `c<priority>-<kebab-case>` 命名)。
2. 将本目录下对应草案的 proposal/design/specs/tasks 迁移到新建的 change 目录。
3. 运行 `just llmanspec-check` 与 `just qa`，确保 sanitize/validate 与 repo 门禁全部通过。
4. 完成实施后按流程 `llman sdd archive run <id>` 归档。

## 已落地（勿再当 notplan 缺口）

下列方向 **已在主路径实现并归档**；notplan 长文已删。评审 ROI 时不要把它们当成待做项：

| 主题 | 归档 change | 主路径证据（摘要） |
|------|-------------|-------------------|
| write-precompute | `archive/2026-08-01-c10-write-precompute-derived-fields` | `execution/write_precompute.py`；pipeline / batch 写出前物化 late 字段 |
| compute expr / 无 `$ctx` call_by rowwise fusion | `archive/2026-08-02-c20-compute-expr-rowwise-fusion` | `planning/.../fusion_groups` + `executor/operators/compute/fusion.py` |
| refloader chunk parallelism | `archive/2026-08-02-c30-refloader-chunk-parallelism` | （见归档） |
| streaming column excel sink | `archive/2026-07-12-c0-streaming-column-excel-sink`（及相关 multi-batch） | `StreamingColumnExcelSink` |
| `FieldValue` datetime 族 | `2026-07-18-c0-add-field-value-datetime`（冻结于 `freezed_changes.7z.archived`） | `typedefs.FieldValue` |
| books / files oneOf | books: `archive/...-c20-add-unified-xlsx-book-kind` + `...-c999-remove-deprecated-xlsx-file-memory-kinds`；files: `csv_file:` 分支 + `kind` fail-fast（loader/validator） | schema `FileConfig` / `BookConfig` |

**勿混淆**：`c0-call-by-multi-output-fusion`（仍 notplan）是 **显式** multi-output / call group（一次用户函数返回多字段），**不是** 已落地的 automatic compute fusion（c20）。

## 已转正 / 部分转正短指针

| notplan 目录 | 状态 |
|--------------|------|
| `c0-shortcuts-public-api-consolidation` | 已转正 → `2026-04-14-c60-output-discovery-facade`（v1；v2/v3 另案）；目录已删 |
| `c0-trusted-mode-defense-in-depth` | 已转正 → `2026-04-28-c3-security-hardening-yaml-dsl`；目录已删 |
| `c0-yaml-dsl-ensure-keys`（原 `c0-yaml-dsl-ensure-keys-defaults`） | **ensure_keys only**：field `default` 已落地并移出范围；见其 proposal 状态块 |

## Perf ROI 判断链路（必读）

内存优先 + 2026-08-11 采样结论的完整决策记录：

- [`2026-08-11-perf-roi-judgment-chain.md`](./2026-08-11-perf-roi-judgment-chain.md)

**立场摘要**：不产品化 `call_by` memo；不推进跨批隐式 overlap cache；优先 multi-output / 减分配 / 更早释放。

## 已移出候选池（目录已删）

不再保留草案正文，避免与「可转正候选」混淆：

### 2026-08-11（perf / 内存优先）

| 原目录 | 原因 |
|--------|------|
| `c999-overlap-optimization` | 跨批缓存与内存优先冲突；无「不增峰」证据（见判断链路 §3） |
| `c1-runtime-performance-profiles` | 等待条件已被主路径覆盖；`speed` 档与内存优先相悖 |

### 2026-08-10

| 原目录 | 原因 |
|--------|------|
| `c0-output-write-path-allowlist` | 暂无威胁驱动；接入面大 |
| `c5-workflow-temp-file-permissions` | 优先序低；不进近期池 |
| `c1-compute-eval-dos-mitigation` | 威胁模型/误伤面未收敛 |
| `c0-roadmap-yaml-dsl-oneof-checklist.md` | books/files oneOf 均已完成，清单无开放项 |
| `c5-lockless-cache-and-viz` | viz 单写者路径已落地；cache 去锁无 contention 证据 |
| `c999-hook-event-bridge` | 无进程外投递消费者；属产品扩展非近缺口 |

## 范围已裁剪的候选

| 目录 | 说明 |
|------|------|
| `c2-batch-call-by`（原 `c2-call-count-reduction-and-parallelism`） | 仅 **batch call_by**；转正门控 **不再** 依赖 EXP memo（见其 proposal + 判断链路） |

## 写出策略 draft 序列（2026-08-11）

| 目录 | 角色 |
|------|------|
| `c10-output-write-path-decision-matrix` | D1 文档矩阵（站点 §3 已写；壳保留） |
| `c20-streaming-column-excel-write-column-aligned` | D2 WINDOW sink 补 aligned（**主路径已实现**；壳保留动机） |
| `c30-output-write-layout-python-policy` | D3 闭集 Python 布局策略面（**已归档** `changes/archive/2026-08-11-c30-...`） |
| `c40-output-write-layout-advisory` | D4 run_stats 建议 **搁置**；调优走 docs/skills；research HTML 留在 notplan |
