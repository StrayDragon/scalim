---
name: scalim-perf-investigation
description: >
  Scalim 框架性能调研标准流程（evidence-first）。当需要排查 Scalim 性能问题、
  评估优化方向 ROI、或构造可复现的 A/B 对拍实验时使用。涵盖：从真实 bench 提炼 shape、
  构造 MVP 复现、固定证据、输出 ROI 草案的完整方法论。
compatibility: Requires Python 3.10+, uv, py-spy, memray (profiling). Repros live under .tmp/.
metadata:
  project: scalim
  version: "1.0"
---

# Scalim 性能调研标准流程

## 核心原则

1. **先证据，后改代码**：任何优化必须先在 `.tmp/repro/` 给出可复现实验与证据，再讨论是否合入。
2. **尽可能不改用户侧代码**：优先框架内部优化。
3. **不引入新三方依赖**：用户环境可能严格限制安装/审核。
4. **所有复现/证据输出落在 `.tmp/` 下**：不提交；也不会随 `git worktree` 自动复制。

## 标准流程

### Step 1: 提炼 shape

从真实 bench / 用户场景提炼关键参数，**只保留计数/分布**，不写业务字符串/SQL/字段名：

- 行数、列数（字段数）
- 数据源数量、关联关系类型（1:1 / 1:N / N:M）
- LoadRef key 基数分布
- 派生字段依赖深度与类型（call_by / compute）
- 输出 sink 类型（CSV / Excel / memory）
- 关键上下文：streaming vs batch，seq vs adaptive

### Step 2: 构造 MVP 复现

在 `.tmp/repro/<topic>/` 下创建独立复现脚本，要求：

- **自包含**：只需要 scalim + 项目 deps，不依赖外部 DB/服务
- **合成数据**：用随机/确定性生成，避免业务敏感信息
- **A/B 对拍**：脚本同时跑 baseline 和 optimized 两条路径，输出对比 JSON
- **输出到 `.tmp/evidence/<topic>/<timestamp>/result.json`**

模板见 `references/repro-template.py`。

### Step 3: 固定证据

| 环境 | 工具 | 用途 |
|---|---|---|
| 本机 | `py-spy` / `memray` | 火焰图、内存分配热点 |
| 本机 | `time` / `psutil` RSS | 端到端耗时、内存趋势 |
| 服务端 | 结构化日志 + 低开销 instrumentation | 无 profiler 时的替代方案 |

每个证据目录应包含 `result.json`，格式：
```json
{
  "baseline": { "total_s": 10.0, "rss_kb_begin": 40000, "rss_kb_end": 45000, "rows": 10000, "fields": 100 },
  "optimized": { "total_s": 9.0, "rss_kb_begin": 40000, "rss_kb_end": 42000, "rows": 10000, "fields": 100 },
  "speedup_total": 1.11
}
```

### Step 4: ROI 草案

在代码修改前，先给出 ROI 评估：

```markdown
## ROI 草案: <优化名称>

- **收益**: 预估提升 X%（基于合成复现）
- **风险**: 类型/契约/边界
- **内存趋势**: RSS 增减方向与幅度
- **实现复杂度**: 低/中/高
- **依赖变更**: 无 / 需新增 xxx
- **决策**: 继续 / 搁置 / 否决
```

ROI 草案应随 proposal 放入 `llmanspec/changes/<change-id>/`。

## 已完成的调研索引

### ✅ 已实现

| 调研 | 结论 | 实现位置 |
|---|---|---|
| A: main_rows(list) consume-clear | 内存杠杆高，RSS 随 batch 递减 | `pipeline.py:_maybe_consume_clear_main_rows_list` |
| B: RowRelease hotpath 减少 keys 拷贝 | ~16% release 子阶段加速 | `context.py:delete_row_from_all_fields` 延迟删除空字段 |
| ExcelSink write_row_aligned 索引缓存 | 已合入；真 A/B 增量 ~2%（2026-08-11） | `sinks/_internal/excel.py`（`527c106f`） |

### ❌ 已否决 / 不推进

| 调研 | 原因 |
|---|---|
| call_by kwargs → positionalize | 上限 ~1%，用户签名多为 pos-or-kw |
| `call_by` memo 产品化 | **内存优先**：uniq>cache 时变慢且 RSS↑；不作默认/DSL 路线（判断链路 2026-08-11） |
| 跨批 overlap load_ref 缓存 | 与批次边界释放冲突；notplan 已删 |

### 🔍 探索中（内存友好）

| 调研 | 状态 | 指针 |
|---|---|---|
| 显式 multi-output / call group | notplan；行内减调用、默认不增峰 | `llmanspec/notplan/c0-call-by-multi-output-fusion/` |
| 热路径减临时对象 | 待 memray；禁止引入缓存 | 判断链路 §5 P2 |
| batch call_by（opt-in） | notplan；门控已去 memo 前置 | `llmanspec/notplan/c2-batch-call-by/` |

完整判断链路：`llmanspec/notplan/2026-08-11-perf-roi-judgment-chain.md`

## Gotchas

- `.tmp/` 不会随 `git worktree` 自动复制；所有复现脚本需在"主仓库路径"下运行，或手动复制到目标 worktree。
- 服务端通常无法安装 `py-spy`/`memray`，需依赖框架内置 instrumentation 点位（如 `SCALIM_PROBE_CALL_BY_DEP_CARDINALITY`）。
- 合成数据复现的结论仅作为 ROI 边界感知，不能直接外推到真实业务场景。真实业务验证是必须的。
