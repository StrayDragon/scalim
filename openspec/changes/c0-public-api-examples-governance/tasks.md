## 1. Public API 覆盖漂移门禁（Tier1 ↔ examples ↔ pytest）

- [ ] 1.1 新增静态 gate：`scripts/check-public-api-suite-coverage.py --check`（SSOT：Tier1 markers + 示例/测试源码；验收：未同步补齐覆盖时 fail-fast 输出缺失/新增模块集合）
- [ ] 1.2 在 `justfile` 增加 `check-public-api-suite-coverage:` recipe，并把它加入 `quick-check-only-py-no-test-gate`（验收：`just qa` 在 pytest 前阶段即可失败退出）
- [ ] 1.3 将 gate 输出做成可操作（验收：错误信息明确提示“新增章节/更新 pytest 章节选择”的修复入口）

## 2. 补齐 `example_public_api_suite` 的 Tier1 缺口章节

- [ ] 2.1 新增章节覆盖 `scalim.events.type_groups`（验收：`just examples` 执行该章节且 oracle 通过；仅使用稳定 facade 导入）
- [ ] 2.2 新增章节覆盖 `scalim.sinks.pandas`（验收：`just examples` 执行该章节且 oracle 通过；缺失 pandas 时 fail-fast 或在 dev 依赖中保证可用）
- [ ] 2.3 更新 `tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids=[...]`（验收：pytest public_api suite 覆盖集合满足 Tier1 gate）
- [ ] 2.4 运行并刷新 `notebooks/marimo/marimo_coverage.gen.toon`（生成入口：`just gen-marimo-coverage`；验收：`just marimo-coverage-drift-check` 无漂移）

## 3. 新增 `scalim-public-api` skill（含受控生成 references + 可运行样例索引）

- [ ] 3.1 创建 `agentdev/skills/scalim-public-api/SKILL.md`（SSOT：手工维护；验收：包含推荐导入、常用 gate/生成入口、与 YAML DSL skill 的交叉引用）
- [ ] 3.2 实现 skill 生成器（建议放在 `packages/scalim-misc/src/scalim_misc/`）与脚本入口 `scripts/gen-public-api-skill.py`（验收：仅写入 `references/**/*.gen.*` 与 `references/generated/**`，支持 `--validate` 校验漂移，并拒绝写入用户 skill 目录）
- [ ] 3.3 在 `justfile` 增加：
  - `gen-public-api-skill:`（生成入口）
  - `validate-public-api-skill:`（校验入口）
  并将其串入 `just gen` 与 `just qa`（验收：生成/校验与其它 drift gate 一致）
- [ ] 3.4 生成 references 内容至少包含：
  - Tier1 entrypoints 列表（markers + `__all__` 导出面摘要；静态扫描）
  - Tier1 → examples/pytest 覆盖映射（静态扫描）
  - 可运行样例索引（指向 notebooks/pytest 的 SSOT 入口；必要时提供可复制片段）
  （验收：Tier1 新增时 validate 必须 fail-fast 指出缺失覆盖）

## 4. marimo 元信息刷新（顺带修复）

- [ ] 4.1 统一更新 `notebooks/marimo/**` 的 `__generated_with` 到当前依赖锁版本（验收：无语义变更，仅元信息对齐）

## 5. 验收清单（统一口径）

- [ ] 5.1 `just examples` 通过（examples gate）
- [ ] 5.2 `pytest -q tests/public_api/ --no-cov` 通过（pytest public_api suite）
- [ ] 5.3 `just gen` 后 `just generated-artifacts-drift-check` 通过（受控生成物无漂移）
- [ ] 5.4 `just qa` 通过（含新增静态 gate，且其在 pytest 前 fail-fast）

