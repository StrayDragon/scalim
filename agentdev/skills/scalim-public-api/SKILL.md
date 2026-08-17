---
name: scalim-public-api
description: "治理 Scalim Tier1 public API: 入口标记(# pragma: scalim-public-api tier1:...) → examples suite → pytest public_api suite → 受控生成 references + drift gates。含 EventType/Observer/Hook 破坏性适配指引。"
---

# Scalim Public API (Tier1)

本 skill 面向“public API 漂移治理”场景：当维护者调整 `scalim.*` 的 Tier1 curated entrypoints / `__all__` 导出面时，用它把 **入口清单 → 可运行示例 → pytest 回归 → gates** 串成确定性闭环。

也用于 **Event / Observer / Hook 二开适配**:进程内事件身份已收敛为 `EventType`(breaking)。

自定义观测 / 钩子扩展（继承 + 组合）：`references/task-observer-hook-extension.md`。  
生产静默 vs 开发服 psutil 门控：`agentdev/skills/scalim-run-stats/references/task-downstream-env-gating.md`。

## SSOT / Rules

- Tier1 curated entrypoints (SSOT): `src/scalim/**/__init__.py` 的 markers
  - `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
- 每个 Tier1 入口模块 MUST 声明字面量 `__all__`（静态扫描；不 import）
- examples suite (SSOT): `notebooks/marimo/example_public_api_suite/chapters/*.py` 的章节集合（每章提供 `run_chapter()`）
- pytest public_api suite (SSOT): `tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids=[...]`
- Generated outputs (禁止手改):
  - `references/**/*.gen.*`
  - `references/generated/**`

### Event / Hook 身份(硬规则)

- 进程内身份与订阅: `EventType` only(`Event.event_type`、`event_types`、`wants`/`emit`)
- 公开 payload: `from scalim.events import PipelineStartEvent, ...`(禁止用户契约依赖私有实现模块)
- 边界: `to_dict`/`JSONL` 可出 builtin `str`;读回用 `parse_event_type`
- 适配入口: `references/task-event-type-adaptation.md`
- 完整升级批次: `references/upgrades/2026-07-19-event-type-enum-identity.md`

## Commands (Repo)

- Coverage drift gate (fail-fast before pytest): `just check-public-api-suite-coverage`
- Run runnable examples (headless suite): `just examples`
- Run pytest public_api suite: `pytest -q tests/public_api/ --no-cov`
- Generate skill references: `just gen-public-api-skill`
- Validate skill references drift: `just validate-public-api-skill`
- Full quality gate: `just qa`

## References

### Generated

- Tier1 catalog: `references/generated/tier1-entrypoints.gen.md`
- Tier1 ↔ examples/pytest coverage map: `references/generated/tier1-suite-coverage.gen.md`

### Hand-authored (适配 / 升级)

- EventType 下游适配任务卡: `references/task-event-type-adaptation.md`
- **Observer / Hook 二开扩展（继承 + 组合）**: `references/task-observer-hook-extension.md`
- EventType Enum 身份升级批次: `references/upgrades/2026-07-19-event-type-enum-identity.md`
- typed handlers 收 `Event`（可读 `meta`）: `references/upgrades/2026-08-02-typed-handlers-receive-event.md`
- 宽表 Excel: `references/streaming-column-excel.md`

与 YAML DSL 的交叉入口:
- 若任务是写/改 YAML DSL,优先用 `agentdev/skills/scalim-yaml-dsl/SKILL.md`（`scalim-yaml-dsl`）。
- 若下游同时升级 YAML DSL 与 EventType: YAML 走 `scalim-yaml-dsl`;Observer/Hook 走本 skill 的 `task-event-type-adaptation.md`。
- 若任务涉及宽表 Excel 峰值 / `StreamingColumnExcelSink` 选型:读 `references/streaming-column-excel.md`（并交叉 `scalim-yaml-dsl` 的 `references/streaming-column-excel-guidance.md`）。
- **0.10.0 性能亮点**(write-precompute / fusion / chunk 并行;YAML 无强制迁移):`scalim-yaml-dsl/references/0.10-release-highlights.md` + 人类总览 `docs/doc/releases/0.10.0/`。
  - 订阅 `FIELD_COMPUTE` / `OPERATOR_SPAN` 或 `VizObserverConfig(trace_enabled=True)` → **关掉** row-wise fusion(安全外壳)。
  - keys 分片 / 片间并行：Python `LookupChunking.sized(N[, parallel=True])` + `adaptive`（YAML `lookup_chunk_size` 已迁出；遗留 `parallelize_lookup_chunks` 仅兼容）。何时用/事件自证：`scalim-yaml-dsl/references/lookup-chunking-guidance.md`；oracle：`ch164_public_api_lookup_chunking`。
- **0.10.1**(相对 0.10.0): typed `on_*` 收完整 `Event`（breaking；YAML 无强制迁移）— `scalim-yaml-dsl/references/0.10.1-release-highlights.md` + `docs/doc/releases/0.10.1/` + `2026-08-02-typed-handlers-receive-event.md`。经 `event.payload` / `event.meta`（含 `scalim_compute_phase`）。
- YAML DSL breaking 升级索引仍在 `scalim-yaml-dsl/references/task-upgrade-legacy.md`;**本 EventType / typed Event 批次属于 Python public API**,不进 YAML upgrades 索引。
- **低漂移 run_stats / write 归因**(装配 profiles、`nodes[]`、baseline↔bench 对拍): `agentdev/skills/scalim-run-stats/SKILL.md` + 人类文档 `docs/doc/viz/run-stats.md`。
  - 最佳实践: `agentdev/skills/scalim-run-stats/references/best-practices.md`
  - 下游升级卡: `references/upgrades/2026-08-08-run-stats-low-drift-and-write-attribution.md`
