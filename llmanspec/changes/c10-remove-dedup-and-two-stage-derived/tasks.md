## 1. Specs + IR 拆除

- [x] 1.1 live `execution-derived-outputs`：删除/改写 r755、r160、r199 及 scenarios；`ir-key-normalization` 收窄 dedup_by 专用场景；yaml-dsl 侧清理误写 YAML `dedup_by` / `on_overflow` / `on_conflict` 条款；capability-matrix 改为「已移除」
- [x] 1.2 删除 `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec` 及 `output_composition` 导出
- [x] 1.3 删除 `DedupByThenAggregator` / `TwoStageGroupByAggregator` / `ScalimDedupKeyConflictError`；确认后删除仅服务 dedup 的 `DedupOnConflictPolicy`

## 2. 测试 / demo

- [x] 2.1 删除或改写 `tests/yaml_dsl/test_derived_outputs.py`、`tests/execution/test_output_composition.py` 中相关用例
- [x] 2.2 删除或改写 notebooks `ch120_derived_set_aggregations` 与 `scalim-misc` `derived_set_aggregations_demo`（可改为「两段 demand / loader 去重」说明）

## 3. 文档 / 门禁

- [x] 3.1 新增 upgrade `YYYY-MM-DD-remove-dedup-and-two-stage-derived.md`；修订 `2026-03-13-derived-outputs-set-aggregations.md`「现行能力」口吻
- [x] 3.2 相关 pytest + `llman sdd validate c10-remove-dedup-and-two-stage-derived --strict --no-interactive`
