# Design: README examples → marimo suite

## Approach

1. **同构套件**：`notebooks/marimo/example_readme_suite/`，命名匹配 `just examples` 的 `example_*` 发现规则；含 `chapters/registry.py` + `chNNN_*.py`（每章 `run_*` / `run_chapter`）。
2. **转写切片**（建议章节）：
   - `ch010_min_python` — 最小 Python IR
   - `ch020_min_yaml` — 最小 YAML + loaders
   - `ch030_memory_compare` — naive vs scalim + knobs（测量 helper 可放 `support/`）
3. **Hub**：`demo_main.py` 薄封装，只调用 registry / 展示结果与图表路径（r497）。
4. **README 面**：inject 改为指向 notebooks 源文件（或短摘录仍从 SSOT 生成）；图表仍由 snapshot→SVG；相对比不硬闸。
5. **删除**：`examples/readme/**`；更新 `justfile` / governance tests / AGENTS。
6. **合约**：`examples-marimo` 吸收「README suite 是 marimo 套件」；`governance-readme-examples` 只保留公开页注入/图资产；删 r986/r988。

## Alternatives rejected

| 方案 | 为何不选 |
|------|----------|
| 薄伴侣 + 保留 `examples/readme` | 双 SSOT，违背用户「转写并移除 examples」 |
| 仅改 docs、不改合约 | r986/r988 仍禁止纳入 marimo 章节 SSOT |
| 并入 `demo_big_data_report` 章节 | 污染主线教学；README 着陆应独立 suite |

## Migration

1. Specs landing（本 propose）→ apply 实现 → verify → finalize。
2. stash `wip: readme charts+companion before c25 propose`：apply 时 cherry-pick 多图/FAQ；丢弃「伴侣调用 examples/readme」形态。
3. `just readme-examples`：改为 drift-only，或删除并由 `just examples` + `gen-readme-examples --check` 覆盖；`just qa`/`check` 清单更新。

## Risks

- `just examples` 发现空/无 chapters 的目录会失败——套件必须带 registry。
- 注入路径变更易漏 drift——tasks 含 gen + check。
