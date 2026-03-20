## 1. Suite Split: public API 覆盖迁出

- [ ] 1.1 新建 `notebooks/marimo/example_public_api_suite/` 套件骨架（hub + chapters + headless 可导入 SSOT 入口）
- [ ] 1.2 迁移 `demo_big_data_report/chapters/ch130_public_api_*` 到 public API suite（保持 `__all__` 覆盖断言与扩展点演示）
- [ ] 1.3 更新 `tests/test_example_public_api_suite.py`：改为运行 public API suite 的章节集合
- [ ] 1.4 更新 `notebooks/marimo/run_examples.py`：默认跑 `demo_big_data_report` + public API suite；保持 `--suite/--chapter/--list` 可定位

## 2. Coverage 报告与 docs 入口同步

- [ ] 2.1 更新 `scripts/gen-marimo-coverage.py`：覆盖新 suite 映射（notebooks → SSOT → gate）
- [ ] 2.2 运行 `just gen-marimo-coverage` 生成 `notebooks/marimo/marimo_coverage.gen.md`（禁止手改生成物）
- [ ] 2.3 更新 `notebooks/marimo/index.py` 与 `docs/doc/getting-started/demo-big-data-report.md`：明确主线教学与 public API suite 的边界与入口

## 3. YAML 场景库：ads/support 第一版落地

- [ ] 3.1 在 `packages/scalim-misc/` 增加 ads 场景的确定性合成 loaders + 纯 Python oracle
- [ ] 3.2 新增 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/`：至少 1 份 demand YAML（可选 workflow），并确保 schema modeline 正确
- [ ] 3.3 在 `packages/scalim-misc/` 增加 support 场景的确定性合成 loaders + 纯 Python oracle（覆盖 guardrails/row_gap 等）
- [ ] 3.4 新增 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/`：至少 1 份 demand YAML（可选 workflow），并确保 schema modeline 正确
- [ ] 3.5 新增 coverage matrix（SSOT）：以 `demand.gen.json`/`workflow.gen.json` 为基准，映射关键能力点 → 覆盖 YAML/章节/断言

## 4. 主线章节重排：YAML-first + 场景化叙事 + 对拍

- [ ] 4.1 下线/移除 IR/Plan 相关章节；新增/改写主线章节为：`yaml_dsl_ecommerce`/`yaml_dsl_ads`/`yaml_dsl_support`/`workflow_yaml`/`workflow_demo_big_data_report`/`yaml_dsl_debugging`
- [ ] 4.2 为每个主线章节补齐“背景/需求方需求/方案取舍/对拍点”的人类叙事模板，并保持 headless 可运行
- [ ] 4.3 对拍补齐：优先纯 Python 真值；必要时固定小型 CSV fixtures（遵守 fixtures 存放约定）
- [ ] 4.4 workflow 章节确保覆盖：DAG `depends_on`、`$ctx` 注入、resources+writes、`cache_pool`（确定性断言）

## 5. 校验与门禁

- [ ] 5.1 demand YAML：对新增/改写 YAML 跑 `uv run scalim-cli yaml-dsl validate <file>`
- [ ] 5.2 workflow YAML：跑 `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <file>`
- [ ] 5.3 跑 `just examples`：两套 suite 全部通过且输出可定位 summary
- [ ] 5.4 跑 `just qa`：lint/tests + drift checks + OpenSpec checks 全部通过

