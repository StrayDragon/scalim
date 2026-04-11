## Context

当前仓库将较重的 pytest 运行选项（`-n auto` + coverage + coverage gate）固化在 `pyproject.toml` 的 `addopts` 中。这导致：

- 开发者无论如何运行 `pytest`，默认都会启用 xdist 并行与 coverage（本地反馈慢、资源占用大）
- 并行 + coverage 会系统性放大时间敏感测试的抖动，增加 flaky 概率
- `just test` 的注释语义倾向于“fast/local”，但实际仍继承重型 addopts，造成入口意图与实际行为不一致

与此同时，CI/qa 仍需要严格门禁（覆盖率阈值、并行跑全套、drift checks），因此需要把“默认本地体验”与“质量门禁”分层，而不是将重型门禁强加给所有入口。

## Goals / Non-Goals

**Goals:**

- 将 pytest 的默认运行方式收敛为轻量、本地友好且更稳定（不默认开启 xdist/coverage）
- 在 `just qa` / CI 入口中仍保留严格门禁（xdist + coverage gate）
- 降低 flaky 的系统性放大因子，同时提升本地迭代效率

**Non-Goals:**

- 不改变测试语义与覆盖范围（仍需要能跑到所有非 bench 测试）
- 不弱化 CI 的质量门禁（覆盖率/并行仍必须在 gate 中执行）

## Decisions

### 1) 采用运行方式分层：轻量默认 + 显式重型 gate（方案 A）

Phase 0 采用提案推荐的方案 A：

- 将 `pyproject.toml` 的 pytest `addopts` 改为轻量默认（只保留必要的输出/marker 筛选等；不默认启用 `-n auto` 与 `--cov`）
- 在 `just qa` / CI workflow 中显式追加重型参数：
  - `-n auto`
  - `--cov ... --cov-branch --cov-report ... --cov-fail-under ...`

这样：

- 本地直接 `pytest`/`just test` 的反馈更快且更稳定
- CI/qa 仍能保持强治理与覆盖率门禁

### 2) 将“质量门禁”入口作为 SSOT，并在文档中明确入口含义

为避免覆盖率门禁被绕过：

- `just qa`（或 CI 的测试 job）必须成为“带 coverage/xdist 的 SSOT gate 入口”
- 文档与贡献指南需要明确：
  - `just test` = fast/local
  - `just qa`/CI = full gate

### 3) 增加 coverage gate 的 sanity check（CI 与本地 gate 一致）

为进一步降低配置漂移风险（例如某次调整不小心漏传 `--cov` 参数）：

- 在 gate 级测试入口中增加一个 sanity check：断言 coverage 数据确实被收集（例如 `.coverage` 文件存在，或显式生成/检查覆盖率报告产物）
- CI 仅运行 gate 入口（`just qa`），从机制上确保覆盖率门禁不可绕过

## Risks / Trade-offs

- **默认行为变化**：直接运行 `pytest` 将不再默认携带 coverage/xdist；需要通过 `just qa`/CI 明确承接门禁职责。
- **入口同步风险**：需要同步更新 `justfile`/CI 配置，确保 coverage gate 不会被意外漏掉；可通过在 CI 中强制执行 gate 入口来兜底。

## Migration Plan

- Phase 0：调整 `pyproject.toml` addopts 为轻量默认；更新 `just qa`/CI 入口显式启用 xdist + coverage gate；补充文档说明
- 后续（可选）：若团队希望更小扰动，可先在过渡期保留一个 `just test-full`，最终仍以“默认轻量 + gate 显式重型”为目标

## Open Questions

- 无。
