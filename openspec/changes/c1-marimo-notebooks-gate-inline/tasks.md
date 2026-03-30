## 1. Directory rename & registry contracts

- [ ] 1.0 移除 notebooks/marimo/index.py notebooks/marimo/run_examples.py notebooks/marimo/marimo_coverage.gen.md 文件
- [ ] 1.1 使用 `git mv` 更名目录：`notebooks/marimo/demo_big_data_report/chapters` → `chapters_of_yaml_dsl`。
- [ ] 1.2 使用 `git mv` 更名目录：`notebooks/marimo/demo_big_data_report/chapters_legacy` → `chapters_of_ir`。
- [ ] 1.3 更新 YAML DSL chapters registry 的 module_name 拼接与导入路径（从 `.chapters.` 改为 `.chapters_of_yaml_dsl.`），并确保 `run_all_chapters()` 仍返回 `List[ExampleResult]`。
- [ ] 1.4 为 IR chapters 新增 `chapters_of_ir/registry.py`（自动发现 `*.py` 并执行 `run_chapter()`/`run_*()`/`run()` 入口；输出 `ExampleResult`）。
- [ ] 1.5 升级 notebooks 内引用路径与文案：将 legacy notebooks 中写死的 `chapters/...` SSOT 路径更新为 `chapters_of_yaml_dsl/...`。

## 2. `just examples` gate inline runner (parallel + auto-discovery)

- [ ] 2.1 修改 `justfile`：将 `examples` recipe 从执行 `notebooks/marimo/run_examples.py` 改为 `uv run python -` 的内联 runner（保持 `PYTHONPATH` 指向 repo root）。
- [ ] 2.2 内联 runner 实现 suite + chapter group 自动发现：扫描 `notebooks/marimo/` 下 `demo_*`/`example_*` suites，并发现 `chapters*/registry.py` 作为可执行 group。
- [ ] 2.3 并行执行策略：suite 粒度多进程并行（默认本地 2、CI 1），suite 内 group 串行（确保 IR/YAML 不互相竞态）。
- [ ] 2.4 环境变量支持（最小集合）：`SCALIM_EXAMPLES_JOBS`（并行度）、`SCALIM_EXAMPLES_SUITES`（suite 白名单）。
- [ ] 2.5 输出与退出码：复用 `scalim_misc.examples.harness` 的 format/summary/exit_code（确保失败时退出码非零且可定位到章节）。

## 3. Remove obsolete notebooks gate scripts

- [ ] 3.1 删除 `notebooks/marimo/index.py`（不再维护 notebooks hub）。
- [ ] 3.2 删除 `notebooks/marimo/run_examples.py`（不再作为 gate 入口）。
- [ ] 3.3 全仓升级引用：docs/tests/packages 说明文字中不再引用上述脚本路径，统一改为 `just examples`（不做兼容双写）。

## 4. Coverage generator & generated artifact governance

- [ ] 4.1 更新 `scripts/gen-marimo-coverage.py`：适配新目录结构（`chapters_of_yaml_dsl` + `chapters_of_ir`）与 gate 标识（`just examples`）。
- [ ] 4.2 generator 增加入口校验：`justfile` 中必须存在 `examples:` recipe（缺失时在报告中标记为 missing，确保 drift-check 可发现入口误删）。
- [ ] 4.3 运行 `just gen-marimo-coverage` 更新生成物 `notebooks/marimo/marimo_coverage.gen.md`（SSOT=脚本；生成物=`.gen.` 文件，禁止手改）。
- [ ] 4.4 运行 `just marimo-coverage-drift-check` 验证无漂移。

## 5. Tests + docs + OpenSpec SSOT sync

- [ ] 5.1 更新 `tests/test_notebook_examples_readme_paths.py`：不再断言 `index.py`/`run_examples.py` 存在；改为断言新目录与 registry/gate 约定成立。
- [ ] 5.2 更新/补齐 pytest 回归：覆盖 `chapters_of_ir` 至少若干章节可跑通（避免 gate 引入后无人回归）。
- [ ] 5.3 更新 docs（SSOT=`docs/doc/**`）：`reading-guide.md`、`demo-big-data-report.md` 等不再引用脚本路径，改为 `just examples`。
- [ ] 5.4 更新 OpenSpec SSOT（SSOT=`openspec/specs/**/spec.md`）：同步修改 `marimo-notebooks-examples-suite`、`testing-quality`、`docs-site` 中对 `run_examples.py`/`index.py` 的要求/描述。
- [ ] 5.5 实现完成后运行 `openspec sync --change c1-marimo-notebooks-gate-inline` 将增量 specs 同步回 `openspec/specs/**/spec.md`（并保持结构校验通过）。

## 6. Verification

- [ ] 6.1 运行 `just examples`：确认 demo + public API suite + IR/YAML chapter groups 都被执行，且失败可定位、退出码正确。
- [ ] 6.2 运行 `just qa`：确保 lint/tests + drift gates 全通过（含 generated artifacts drift 与 docs governance）。
- [ ] 6.3 运行 `just openspec-check`：sanitize + `openspec validate --all --strict --no-interactive` 通过，确保 change 工件可发布。

