## 1. 调研与基线（先调研后搬迁）

- [x] 1.1 统计当前 `tests/` 文件/用例分布（按前缀、按 marker：`bench`/`slow`，并列出 top N 超大文件）
- [x] 1.2 全仓清点 YAML/配置中的字符串引用入口（`loader:`/`call_by:`/`allowed_modules`），产出“可移动/不可移动”入口清单
- [x] 1.3 清点重复热点：`test_*_additional.py`、`*_coverage.py`、`cover_branches` 命名，以及重复 helper（如 `_write_*`/YAML 生成脚手架）
- [x] 1.4 固化基线口径：记录当前 `pytest --collect-only` 的收集规模与 `just test` 的通过状态（用于迁移后对拍）

## 2. 建立 domain suites 骨架与边界

- [x] 2.1 创建 domain suites 目录骨架：`tests/public_api/`、`tests/yaml_dsl/`、`tests/workflow/`、`tests/execution/`、`tests/governance/`、`tests/integration/`（`tests/bench/` 保持不动）
- [x] 2.2 建立 `tests/support/`（仅 Python import 复用工具）并开始收敛重复 helper（确保不被 YAML 字符串引用）
- [x] 2.3 明确并落地“字符串引用稳定边界”为 `tests/fixtures/`：将所有 string-reference callable 迁入该边界，并一次性升级全仓引用（不保留旧路径兼容）
- [x] 2.4 新增门禁（pytest 扫描或等价脚本）：禁止新增 `tests.support.*` 的字符串引用；禁止新增散点 `tests.<non-fixtures>` 字符串引用
- [x] 2.5 新增门禁：禁止新增 `test_*_additional.py`（要求同主题 SSOT 收敛）

## 3. 低风险先行迁移（governance / 基础护栏）

- [x] 3.1 迁移治理/护栏类测试到 `tests/governance/`（module layout、API surface、OpenSpec/脚本类 gate 等），保持语义不变
- [x] 3.2 确保默认 pytest 入口仍收集并执行这些测试（`testpaths=["tests"]` 语义不变）

## 4. 按 domain 分批迁移与去重（保持 100% 覆盖率）

- [x] 4.1 public_api：建立/收敛 `tests/public_api/`，覆盖 public API catalog（由 `src/scalim/**` `__all__` 扫描生成,排除 `cli/vendor`）与核心链路 API 的“用户侧最小闭环”（import + `__all__` + 最小运行）
- [x] 4.2 yaml_dsl：迁移 `test_yaml_*` 相关文件到 `tests/yaml_dsl/`，合并 `*_additional.py` 并收敛重复 YAML 生成脚手架
- [x] 4.3 workflow：迁移 `test_workflow_*` 到 `tests/workflow/`，将 coverage-only/guard 用例显式归类并参数化去重
- [x] 4.4 execution：迁移 `test_execution_*`/`test_executor_*`/`test_pipeline_*`/`test_adaptive_*` 到 `tests/execution/`，按主题拆分超大文件并保持覆盖率不回落
- [x] 4.5 其它领域：`planning/`、`sinks/`、`ob/`（含 hooks/events/observer）按同样策略迁移与去重
- [x] 4.6 integration：将 `slow`/真实 demo 对拍相关测试迁移到 `tests/integration/`（延续 `@pytest.mark.slow` 约定）

## 5. public API 双链路对齐（pytest + examples）

- [x] 5.1 实现 public API catalog 生成：扫描 `src/scalim/**` 中所有声明了 `__all__` 的模块与导出（排除 `src/scalim/cli/**`、`src/scalim/vendor/**` 等），并提供可自动化的差异检测
- [x] 5.2 文档自动生成化：将 public API 导入指南与导出清单生成到 `docs/doc/getting-started/public-api.gen.md`（纳入 `just gen-docs`/`just docs-drift-check`）
- [x] 5.3 对齐 `notebooks/marimo/example_public_api_suite/` 的覆盖范围（补齐 `events/sinks` 等最小章节覆盖；确保 `just examples` 稳定回归）
- [x] 5.4 pytest public_api 与 examples suite 的覆盖集合对齐：两条链路都以 public API catalog 为 SSOT,并在 drift 时 fail-fast
- [x] 5.5 更新 `scripts/gen-marimo-coverage.py` 的 pytest 路径引用（若 pytest public_api 文件迁移导致路径变化）
- [x] 5.6 生成物治理（SSOT/入口/验收）：
  - SSOT: `scripts/gen-marimo-coverage.py`
  - 生成入口: `just gen-marimo-coverage`
  - 漂移门禁: `just marimo-coverage-drift-check`

## 6. 验收与收尾

- [x] 6.1 验收：`just test`（非 bench）通过且 `src/scalim` 覆盖率仍为 100%
- [x] 6.2 验收：`just examples` 通过（public API suite + demo suite）
- [x] 6.3 验收：`just qa` 通过（含 drift checks 与治理脚本门禁）
- [x] 6.4 OpenSpec 验收：`just openspec-check` 通过（sanitize + 结构校验）
