## Why

当前 `notebooks/marimo/` 的回归入口与结构约定对贡献者来说偏复杂:

- `just examples` 依赖独立脚本 `notebooks/marimo/run_examples.py`，导致“入口文件 + justfile + specs/docs/tests”多处耦合；删除/迁移时牵一发动全身。
- `notebooks/marimo/index.py` 作为 hub 的价值变低：读者通常直接点击具体 suite notebook（如 `demo_main.py`）即可，不需要额外聚合入口。
- demo 的章节目录语义不清晰（`chapters` / `chapters_legacy`），且 gate 自动发现/并行策略缺少清晰契约，后续新增 suite/章节时容易引入额外脚本与约定碎片。

需要收敛入口与目录语义：把 `just examples` 变成唯一稳定 gate（在 justfile 内联实现 runner），同时保持 examples coverage 报告与 drift-check 治理不变，并让未来新增 suite/章节可自动发现并纳入回归。

## What Changes

- **BREAKING**：移除 `notebooks/marimo/run_examples.py`，`just examples` 改为在 `justfile` 内联 headless runner（支持并行与环境变量控制）。
- 移除 `notebooks/marimo/index.py`（不再维护 notebooks hub；读者直接使用各 suite 的 `demo_main.py` 作为交互入口）。
- `demo_big_data_report` 目录更名以明确语义并保留内容:
  - `notebooks/marimo/demo_big_data_report/chapters/` → `chapters_of_yaml_dsl/`
  - `notebooks/marimo/demo_big_data_report/chapters_legacy/` → `chapters_of_ir/`
  - `chapters_of_ir` 同样纳入 `just examples` gate（与 `chapters_of_yaml_dsl` 一并 deterministic 回归）。
- 保留并更新 examples coverage 治理：
  - 继续由 `scripts/gen-marimo-coverage.py` 生成 `notebooks/marimo/marimo_coverage.gen.md`
  - coverage 报告中的 gate 标识由 “脚本路径” 收敛为 “`just examples`”
  - coverage 报告与 drift-check 需要适配新的目录结构与入口约定。
- 全仓同步升级引用（一次性升级，不做兼容双写）：`docs/`、`tests/`、`openspec/specs/`、以及 `packages/scalim-misc` 内的说明文字，统一指向 `just examples`。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `marimo-notebooks-examples-suite`: 回归入口从脚本路径收敛为 `just examples`（justfile 内联 runner），并移除 hub `index.py` 的强依赖；章节目录语义化更名并纳入 gate 自动发现。
- `testing-quality`: `just examples` 不再要求执行 `notebooks/marimo/run_examples.py`，而是要求其行为等价（覆盖 demo + public API suite + 可定位 PASS/FAIL + 非零退出码）。
- `docs-site`: docs-site 的“主线教程入口页”不再引用脚本路径作为 gate 入口，而是引用 `just examples` 作为稳定入口。

## Impact

- 受影响代码/配置：
  - `justfile` 的 `examples`/相关 recipes
  - `notebooks/marimo/**`（demo 章节目录更名 + registry/引用更新）
  - `scripts/gen-marimo-coverage.py` 与生成物 `notebooks/marimo/marimo_coverage.gen.md`
  - `tests/` 中对 notebooks 入口路径的断言与回归用例
  - `docs/doc/**` 与相关 OpenSpec specs 的入口文案
- 受影响使用方式：
  - `python notebooks/marimo/run_examples.py ...` 将不可用；统一改用 `just examples`。
- 受影响 specs：
  - SSOT: `openspec/specs/<capability>/spec.md`
  - 本 change 的增量规范写入 `openspec/changes/c1-marimo-notebooks-gate-inline/specs/<capability>/spec.md`
  - 提交前运行 `just openspec-check` 做 sanitize + 结构校验。

