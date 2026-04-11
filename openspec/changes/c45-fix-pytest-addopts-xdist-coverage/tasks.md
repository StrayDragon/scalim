## 1. 轻量默认 pytest addopts（移除隐式重型）

- [ ] 1.1 更新 `pyproject.toml` 的 `[tool.pytest.ini_options].addopts`：移除默认 `-n auto` 与 `--cov*` 等重型选项，保留必要的默认行为（例如排除 bench、禁用 benchmark 插件等）
- [ ] 1.2 确认 `just test` 成为真正的 fast/local 入口：默认不启用 xdist/coverage，反馈明显变快

## 2. CI/qa 显式启用重型 gate（xdist + coverage）

- [ ] 2.1 在 `justfile` 增加/调整一个“gate 级测试”入口（例如 `test-gate`）：显式携带 `-n auto` 与 `--cov=scalim --cov-branch --cov-report=... --cov-fail-under=...`
- [ ] 2.2 将 `just qa`/`just check`（SSOT gate）接线为运行 `test-gate` 而不是轻量 `test`，确保 CI 仍执行覆盖率门禁与并行（CI 入口见 `.github/workflows/ci.yaml`）
- [ ] 2.3 更新相关文档/注释：明确 `just test` = fast/local；`just qa`/CI = full gate（避免入口语义误解）

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/testing-quality/spec.md` 明确“默认轻量 + gate 显式重型”的分层策略
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 在本地与 CI 验证：
  - `just test` 不启用 xdist/coverage 且更快
  - `just qa` 仍启用 xdist + coverage gate 且覆盖率门禁有效

