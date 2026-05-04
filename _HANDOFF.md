# Temporary Handoff: scalim perf workflow (evidence-first)

本文件记录“性能调研 → 证据 → ROI → 实现”的工作模式，以及已产出的复现与证据索引，便于不同 worktree/执行者交接。

约束与目标：
- 尽可能不改用户侧代码；优先框架内部优化。
- 不引入新三方依赖（用户环境可能严格限制安装/审核）。
- **先证据，后改代码**：任何优化必须先在 `.tmp/repro/` 给出可复现实验与证据，再讨论是否合入。
- 所有复现/证据输出必须落在 `.tmp/` 下（不提交；也不会随 `git worktree` 自动复制）。

## 标准流程（必须遵循）

1. 从真实 bench 提炼 shape（只保留计数/分布，不写业务字符串/SQL/字段名）
2. 在 `.tmp/repro/` 构造用户相似 MVP（A/B 对拍，输出 JSON）
3. 固定证据：本机用 `py-spy`/`memray`；服务端用结构化日志 + 低开销 instrumentation 点位
4. 给出 ROI 草案（收益/风险/内存趋势/实现复杂度），review 通过后才实现

## 已验证：A — main_rows(list) 消费后清空引用（内存杠杆高）

问题形态：
- 用户主 loader 返回 `list[dict]`（大对象）；pipeline 分批消费，但 backing list 持有所有行引用直到 pipeline 结束。
- 在“流式写出 + 行级释放”已生效的情况下，RSS 仍高且不下降，典型根因就是 main_rows list retention。

本机合成复现（无业务数据）：
- 脚本：`.tmp/repro/main_rows_list_retention/repro-main-rows-list-retention.py`
- 证据：
  - baseline：`.tmp/evidence/main_rows_list_retention/20260503_225851/result.json`
  - consume_clear：`.tmp/evidence/main_rows_list_retention/20260503_225857/result.json`
- 结论（结论级）：
  - checksum 一致
  - consume_clear 模式 RSS 随 batch 递减，baseline 不下降

实现策略（框架侧）：
- 仅当 `main_rows` 由框架内部 main loader 加载、且为 `list` 时，批次完成后对已消费 slice 做“定长置 None”。
- 不改变 list 长度，避免破坏 list iterator 语义。

风险/契约提醒：
- 若用户 main loader **复用/缓存** 同一个 list 对象（不推荐，且会长期占用内存），该优化会清空其内容；此模式视为不受支持。

## 已验证：B — RowRelease 热路径减少 keys 拷贝（CPU 杠杆中等）

问题形态：
- streaming 模式下每行写出后都会调用 `context.delete_row_from_all_fields(...)`。
- 该方法若每次都复制外层 keys 列表，会在 rows×fields 很大时形成固定开销。

本机合成复现（无业务数据）：
- 脚本：`.tmp/repro/context_release_hotpath/repro-context-release-hotpath.py`
- 证据：
  - baseline：`.tmp/evidence/context_release_hotpath/20260503_230524/result.json`
  - optimized：`.tmp/evidence/context_release_hotpath/20260503_231458/result.json`
- 结论（结论级）：
  - 释放热点在 `delete_row_from_all_fields` 路径可量化（~16% release 子阶段加速，规模越大越显著）

实现策略（框架侧）：
- `BatchContext` / `DenseBatchContext`：迭代 `dict.items()`，延迟删除空字段（收集后统一 pop），避免每次复制 keys。

## 已否决/低优先级：call_by kwargs → positionalize（杠杆低）

- 复现：`.tmp/repro/derived_fields_userlike/`
- 证据：`.tmp/evidence/userlike_20260503/`、`.tmp/evidence/userlike_20260503_ab/`
- 结论：在“用户真实签名多为 pos-or-kw”的情况下，上限约 ~1%，不作为优先优化线。

## 探索中：方向 1 — ExcelSink `write_row_aligned` 可能的内置优化（ROI 待定）

动机：
- pipeline 写出时优先走 `sink.write_row_aligned(field_keys, values)`（若 sink 支持）。
- `ExcelSink.write_row_aligned()` 当前实现为 `dict(zip(...)) -> write_row()`，会额外构造 `dict` 并执行 `row.get()` 查找。
- 假设宽表 + 大行数时，这部分属于“可被框架内部消除的固定开销”。

本机合成复现（无业务数据）：
- 脚本：`.tmp/repro/excel_sink_write_row_aligned/repro-excel-sink-write-row-aligned.py`
- 证据（最新覆盖写到同一路径，按需自行另存时间戳版本）：`.tmp/evidence/excel_sink_write_row_aligned/result.json`

当前结论（先证据）：
- 在 `rows=20k, fields=250` 的合成场景下，fast 实现相对 baseline 提升约 **2–3%**（主要在 write 阶段）。
- 推断：openpyxl append/序列化本身占比更大，`dict(zip)+get` 的收益可能有限；除非真实业务的 write path 更接近“CPU 受 dict 开销主导”。

下一步（需要 review 决策后再动代码）：
- 若要继续：用更接近业务 1 的 shape（列数/字符串比例/allow_formulas 配置）补充复现；并在本机对写出阶段做 `py-spy`/`memray` 证据。

## 探索中：方向 2 — 派生字段（call_by/compute）“依赖元组重复率”评估（决定是否值得缓存）

动机：
- 对于热字段（尤其 call_by），若大量行共享相同依赖组合（dep tuple），理论上可通过 memoization 显著降耗。
- 但缓存通常以增加 RSS/峰值内存为代价；当重复率不足或工作集过大时，会 **变慢且更占内存**。

本机合成复现（无业务数据，仅用于 ROI 边界感知）：
- 脚本：`.tmp/repro/dep_tuple_cardinality/repro-dep-tuple-cardinality.py`
- 证据（最新覆盖写到同一路径）：`.tmp/evidence/dep_tuple_cardinality/result.json`

观察要点（用于指导是否进入实现/以及 cache 设计边界）：
- **重复率低** 或 cache 容量明显小于 working-set 时：cache 会产生额外哈希/字典开销，整体变慢，并引入额外 RSS。
- **重复率高** 且 cache 覆盖 working-set 时：cache 可显著加速，且缓存条目数受控时 RSS 增量较小。

业务落地的关键缺口（必须补证据）：
- 需要拿到真实热字段的 dep tuple 重复率/工作集规模。
- 由于服务端无法安装 `py-spy/memray`，建议在框架内加入一个“低开销、可开关”的统计点位：仅输出计数（total/unique/重复率），不落依赖值本身。

## worktree 提示

`.tmp/` 不会随 `git worktree` 自动复制；所有复现脚本需要在“主仓库路径”下运行，或手动复制 `.tmp/repro/` 到目标 worktree。
