## Context

当前 `notebooks/marimo/` 的 examples gate 由脚本 `notebooks/marimo/run_examples.py` 承载，并被 `just examples`、docs、tests、OpenSpec specs 与 `scripts/gen-marimo-coverage.py` 多处硬编码引用。与此同时，`notebooks/marimo/index.py` 作为 notebooks hub 的价值下降：读者通常直接打开各 suite 的 `demo_main.py` 即可完成交互阅读。

本变更希望把回归入口收敛为“命令级”稳定入口 `just examples`，并把 runner 的实现移动到 `justfile` 内联代码中（支持并行与环境变量控制），从而降低维护复杂度与入口耦合；同时保留 `marimo_coverage.gen.md` 的生成与 drift-check 治理链路。

约束/治理边界：

- `notebooks/marimo/marimo_coverage.gen.md` 为 `.gen.` 全文件生成物，不允许手改，必须由 `scripts/gen-marimo-coverage.py` 生成。
- OpenSpec 的 SSOT 为 `openspec/specs/<capability>/spec.md`；本 change 的增量规范写入 `openspec/changes/<change>/specs/<capability>/spec.md`。
- `just qa`/CI 作为最终门禁，必须继续包含 `just examples` 与 `just marimo-coverage-drift-check`。

## Goals / Non-Goals

**Goals:**

- 移除 `notebooks/marimo/index.py` 与 `notebooks/marimo/run_examples.py`，并将 `just examples` 的 runner 逻辑以内联方式迁移到 `justfile`。
- `just examples` 支持自动发现并执行：
  - suites：`notebooks/marimo/` 下 `demo_*` 与 `example_*` 目录
  - chapter groups：suite 目录下以 `chapters*` 命名且包含 `registry.py` 的子目录（例如 `chapters/`、`chapters_of_yaml_dsl/`、`chapters_of_ir/`）
- 支持并行执行（默认小并行；CI 默认串行），并提供少量环境变量用于特殊情况（例如筛选 suites 或调整并行度）。
- `demo_big_data_report` 目录语义化更名并保留内容：
  - `chapters` → `chapters_of_yaml_dsl`
  - `chapters_legacy` → `chapters_of_ir`
  并将 `chapters_of_ir` 纳入 `just examples` gate。
- 保留 `marimo_coverage.gen.md` 治理：更新 generator 以反映新的 gate 标识与目录结构，确保 drift-check 可用。
- 全仓一次性升级引用（docs/tests/specs/packages 说明），不做兼容双写。

**Non-Goals:**

- 不改变 canonical YAML fixtures 的路径与含义（例如 `by_yaml_dsl/ecommerce_report.yaml`、`workflow_fixture.yaml`）。
- 不重写示例章节内容/Oracle/性能口径（除路径/导入/文案与最小必要适配外）。
- 不引入新的外部依赖；runner 复用现有 `scalim_misc.examples.harness` 的结果格式化/退出码逻辑。

## Decisions

1) **稳定 gate 入口改为 `just examples`（justfile 内联 runner）**

- `just examples` 作为唯一稳定入口；不再承诺 `python notebooks/marimo/run_examples.py ...` 可用。
- runner 以内联 Python 代码实现，使用 `uv run python -`（stdin heredoc）执行；由 justfile 负责设置 `PYTHONPATH` 指向 repo root。

替代方案与取舍：
- 继续保留 `run_examples.py` 并由 justfile 调用：实现改动更小，但入口耦合与维护成本不降，且与本次“移除脚本”目标冲突。

2) **自动发现契约：suite + chapter group + registry**

- suites：枚举 `notebooks/marimo/` 下满足 `demo_*` 或 `example_*` 的目录。
- chapter groups：suite 目录下 `chapters*` 且包含 `registry.py` 的子目录。
- registry 模块导入路径约定：
  `notebooks.marimo.<suite_dir>.<chapters_dir>.registry`
- registry 运行时契约（运行 `just examples` 与 coverage generator 共同依赖）：
  - MUST 提供 `run_all_chapters(*, slow_ok: bool = False) -> List[ExampleResult]`
  - SHOULD 提供 `all_chapter_ids() -> List[str]`（用于列表/调试）

3) **并行策略：suite 粒度多进程并行，suite 内串行**

- 并行只在 suite 粒度启动多个独立 Python 进程，避免同一进程内共享全局状态导致竞态（例如 IR 章节中存在显式 `set_config/get_config`）。
- `demo_big_data_report` 的 YAML/IR 两个 chapter group 在同一 suite 内按固定顺序串行执行。
- 环境变量：
  - `SCALIM_EXAMPLES_JOBS`：并行 suite 数（默认：`CI` 环境为 `1`，本地为 `2`）
  - `SCALIM_EXAMPLES_SUITES`：逗号分隔白名单（为空则自动发现全部）

4) **coverage 报告中的 Gate 字段从脚本路径改为命令标识**

- `scripts/gen-marimo-coverage.py` 的 gate 字段改为展示 `just examples`（字符串）。
- generator 额外做轻量校验：`justfile` 中必须存在 `examples:` recipe；缺失时在报告中标记为 missing，以便 drift-check 及时发现入口被误删。

5) **目录更名不做兼容：一次性升级所有导入与文案**

- 使用 `git mv` 进行目录更名，确保历史可追踪。
- 更新：
  - notebooks 内的 `module_name` 拼接与导入路径
  - docs/specs/tests 里硬编码路径
  - 生成脚本与覆盖报告的路径枚举逻辑

## Risks / Trade-offs

- [并行带来 uv 启动开销] → 默认 jobs 小且可配；CI 固定串行；必要时可在后续迭代把并行迁移到单进程内的 `ProcessPoolExecutor`。
- [自动发现误纳入非 deterministic notebooks] → 通过 “必须存在 `chapters*/registry.py`” 约束将纳入范围限制为明确声明的章节集合；suite 的其它 notebooks 不会被 gate 扫到。
- [justfile gate 校验不如脚本路径直观] → coverage generator 通过检查 `examples:` recipe 存在性兜底；并由 `just qa` 实际执行验证。
- [IR 章节存在不稳定/慢用例] → 允许用 `SCALIM_EXAMPLES_SUITES` 做最小手动过滤；若后续确需细粒度筛选，再在 registry 层提供过滤能力（不在本变更首批强制引入）。

## Migration Plan

1. 实施目录更名与 registry/导入升级，确保所有 notebooks 与 pytest 导入路径可用。
2. 修改 `justfile`：将 `examples` recipe 迁移为内联 runner，并移除对 `notebooks/marimo/run_examples.py` 的引用。
3. 修改 `scripts/gen-marimo-coverage.py` 以适配新 gate 标识与目录结构；运行 `just gen-marimo-coverage` 更新生成物。
4. 更新 docs 与 OpenSpec specs（SSOT），并补齐本 change 的增量规范文件。
5. 运行 `just qa` 与 `just openspec-check` 验收；确保 examples 与 drift-check 均通过。

## Open Questions

- (none)

