---
name: scalim-public-api
description: "治理 Scalim Tier1 public API: 入口标记(# pragma: scalim-public-api tier1:...) → examples suite → pytest public_api suite → 受控生成 references + drift gates。"
---

# Scalim Public API (Tier1)

本 skill 面向“public API 漂移治理”场景：当维护者调整 `scalim.*` 的 Tier1 curated entrypoints / `__all__` 导出面时，用它把 **入口清单 → 可运行示例 → pytest 回归 → gates** 串成确定性闭环。

## SSOT / Rules

- Tier1 curated entrypoints (SSOT): `src/scalim/**/__init__.py` 的 markers
  - `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
- 每个 Tier1 入口模块 MUST 声明字面量 `__all__`（静态扫描；不 import）
- examples suite (SSOT): `notebooks/marimo/example_public_api_suite/chapters/*.py` 的章节集合（每章提供 `run_chapter()`）
- pytest public_api suite (SSOT): `tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids=[...]`
- Generated outputs (禁止手改):
  - `references/**/*.gen.*`
  - `references/generated/**`

## Commands (Repo)

- Coverage drift gate (fail-fast before pytest): `just check-public-api-suite-coverage`
- Run runnable examples (headless suite): `just examples`
- Run pytest public_api suite: `pytest -q tests/public_api/ --no-cov`
- Generate skill references: `just gen-public-api-skill`
- Validate skill references drift: `just validate-public-api-skill`
- Full quality gate: `just qa`

## References (Generated)

- Tier1 catalog: `references/generated/tier1-entrypoints.gen.md`
- Tier1 ↔ examples/pytest coverage map: `references/generated/tier1-suite-coverage.gen.md`

与 YAML DSL 的交叉入口:
- 若任务是写/改 YAML DSL,优先用 `agentdev/skills/scalim-yaml-dsl/SKILL.md`（`scalim-yaml-dsl`）。
- 若任务涉及宽表 Excel 峰值 / `StreamingColumnExcelSink` 选型:读 `references/streaming-column-excel.md`（并交叉 `scalim-yaml-dsl` 的 `references/streaming-column-excel-guidance.md`）。

