## Meta

- Type: `fix-0`
- Topic: pytest 默认 addopts 强制 `-n auto` + coverage，放大测试不稳定性与本地开发成本
- Related code:
  - `pyproject.toml:220`（`[tool.pytest.ini_options].addopts`）
  - `justfile:340`~`:342`（`just test`：看起来希望“fast/local”，但实际上仍会继承 addopts）

## 背景

当前 pytest 默认配置：

```
addopts = "-rs -n auto --cov=scalim --cov-branch --cov-report=term-missing --cov-fail-under=99 ..."
```

这意味着：

- 无论开发者怎么运行 `pytest`，默认都会启用 xdist 并行与 coverage；
- `just test` 虽然注释写的是 “Fast/local functional checks”，但实际仍会继承上述 addopts（除非显式 `-o addopts=""`）。

这种“默认即重型”的策略有好处（强治理、覆盖率门禁提前暴露），但也带来两个现实问题：

1) 放大 flaky：并行 + coverage 会把很多“边缘时间敏感”的测试抖动放大成偶发失败；  
2) 本地开发成本高：每次本地跑测试都背上 coverage/xdist，导致反馈变慢，反而降低迭代效率。  

## 现状与问题

### 问题 1：flaky 概率被系统性放大

仓库内已经存在一些时间敏感测试（例如 barrier wait / event wait / sleep/polling）。在 `-n auto` + coverage 场景下：

- 线程调度更不稳定；
- CPU/IO 争用更大；
- 测试对 wall-clock 的假设更容易被破坏。

这会使“本来改一下 timeout 就能稳定”的测试，演化为“经常需要重跑”的 CI 成本。

### 问题 2：本地开发循环与配置意图不一致

`justfile` 里 `test` recipe 的注释明显希望它是“快速本地检查”，但它没有覆盖 addopts：

- 结果：开发者以为自己跑的是 fast test，实际跑的是重型门禁版本。

## 目标

- 保留 CI 的严格门禁能力（coverage/并行仍可启用）；
- 让本地默认更快、更稳定；
- 降低 flaky 的系统性放大因子；
- 不改变测试语义（只是运行方式分层）。

## 方案候选

### 方案 A：把重型选项从 pyproject 移到 `just qa` / CI（推荐）

做法：

1) 将 `pyproject.toml` 的 pytest `addopts` 改成轻量默认（例如仅 `-rs -q -m "not bench"`）；  
2) 在 `just check/qa` 或 CI workflow 中显式追加：
   - `-n auto`
   - `--cov ... --cov-fail-under ...`

优点：

- 本地默认更快；
- CI 仍然严格；
- 能显著降低“重型配置放大 flaky”的概率。

缺点：

- 需要同步调整 CI/just 入口，避免覆盖率门禁被意外绕过；
- 需要对团队达成共识（默认行为会变化）。

性价比：

- 高（一次调整，持续收益）。

### 方案 B：保持 pyproject 重型默认，但 `just test` 明确覆盖为轻量（折中）

做法：

- 在 `justfile:test` 中显式禁用默认 addopts，例如：
  - `pytest -o addopts="" -n 0 --no-cov ...`
- 并新增 `just test-ci` 或 `just test-full` 跑重型版本（或复用 `just check`）。

优点：

- 不改变“直接跑 pytest”的默认行为；
- 立刻让 `just test` 名副其实（fast/local）。

缺点：

- 仍然存在：开发者手工跑 `pytest` 时默认重型（慢 + 放大 flaky）；
- 规则分散（pyproject 与 justfile 各一套），需要文档同步。

性价比：

- 中到高（改动更小，但系统性收益略弱于方案 A）。

### 方案 C：保留全部默认，只修测试（不推荐单独作为解决方案）

缺点：

- 即使把所有测试都改得更稳，`-n auto` + coverage 仍然会持续带来更高的环境抖动；
- “默认重型”会持续压低本地开发体验。

## 推荐方案

推荐 **方案 A**（运行方式分层，轻量默认 + CI/qa 显式重型）。

如果团队希望最小扰动快速落地，可先做方案 B 作为过渡，再逐步迁移到方案 A。

补强（推荐一并落地）：

- 在 CI/gate 入口增加一个 sanity check，断言覆盖率门禁确实启用（例如 `.coverage` 或覆盖率报告产物存在），避免入口接线漂移导致“误以为有 coverage gate 但实际没开”。

## 性价比总结

- 成本：中（需要调整配置入口与 CI/just 语义）。
- 收益：高（降低 flaky、提升本地反馈速度、减少 CI 重跑）。

## 验证建议

- 更新后确保以下都成立：
  - `just test` 在本地明显更快（不启用覆盖率与 xdist）；
  - `just check/qa` 或 CI 仍启用覆盖率门禁；
  - CI 通过率提升（减少偶发失败）。
