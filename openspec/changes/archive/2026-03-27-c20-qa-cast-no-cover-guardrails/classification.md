# 分类记录: cast / no-cover 命中 (c20)

本文件用于任务 **0.3**：按目录/职责分类 `cast(...)` 与 `# pragma: no cover` 命中，区分「应补类型/应补测试」与「必须 allow」的场景。

> 基线由以下命令生成（输出写入 `.tmp/artifacts/`）：
>
> - `uv run scripts/check-cast-usage.py --report .tmp/artifacts/cast-usage.report.txt`
> - `uv run scripts/check-no-cover.py --report .tmp/artifacts/no-cover.report.txt`

## 摘要 (当前基线)

- `cast(...)`: `389` 命中 / `74` 文件（全部为 `typing.cast`）
- `# pragma: no cover`: `132` 命中 / `34` 文件

## 逐文件用途与建议

- 逐文件的“主要用途 + 是否建议 allow”的清单见：`file_inventory.md`

## 分布 (当前基线)

> 数据来自 `.tmp/artifacts/cast-usage.report.json` 与 `.tmp/artifacts/no-cover.report.json` 的聚合。

### cast(...) 命中分布（按模块簇）

| 模块簇 | 命中 | 文件数 |
| --- | ---: | ---: |
| `src/scalim/dsl/by_yaml` | 199 | 24 |
| `src/scalim/execution` | 41 | 15 |
| `src/scalim/workflow` | 39 | 5 |
| `src/scalim/ob` | 31 | 10 |
| `src/scalim/spec` | 20 | 4 |
| `src/scalim/hooks` | 13 | 4 |
| `tests` | 12 | 4 |
| `src/scalim/cli` | 11 | 1 |
| `scripts` | 8 | 2 |
| `src/scalim/utils` | 8 | 3 |
| `src/scalim/_internal` | 5 | 1 |
| `src/scalim/planning` | 2 | 1 |

### cast(...) 热点文件（Top 15）

| 命中 | 文件 |
| ---: | --- |
| 32 | `src/scalim/dsl/by_yaml/workflow_config.py` |
| 20 | `src/scalim/workflow/execute.py` |
| 19 | `src/scalim/dsl/by_yaml/config_parsing/imports.py` |
| 19 | `src/scalim/dsl/by_yaml/config_parsing/unknown_fields.py` |
| 17 | `src/scalim/dsl/by_yaml/config_parsing/validator.py` |
| 16 | `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` |
| 12 | `src/scalim/dsl/by_yaml/config_parsing/security.py` |
| 12 | `src/scalim/spec/ir/sources.py` |
| 11 | `src/scalim/cli/yaml_dsl.py` |
| 10 | `src/scalim/dsl/by_yaml/runtime/compiler.py` |
| 10 | `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py` |
| 10 | `src/scalim/dsl/by_yaml/workflow_entrypoints.py` |
| 9 | `src/scalim/dsl/by_yaml/params_template.py` |
| 9 | `src/scalim/execution/pipeline/base/pipeline.py` |
| 8 | `src/scalim/dsl/by_yaml/config_parsing/models/__init__.py` |

### # pragma: no cover 命中分布（按模块簇）

| 模块簇 | 命中 | 文件数 |
| --- | ---: | ---: |
| `src/scalim/dsl/by_yaml` | 52 | 11 |
| `src/scalim/workflow` | 38 | 4 |
| `src/scalim/execution` | 22 | 6 |
| `scripts` | 10 | 9 |
| `src/scalim/hooks` | 3 | 1 |
| `src/scalim/sinks` | 3 | 1 |
| `tests` | 3 | 1 |
| `src/scalim/ob` | 1 | 1 |

### # pragma: no cover 热点文件（Top 15）

| 命中 | 文件 |
| ---: | --- |
| 21 | `src/scalim/workflow/execute.py` |
| 15 | `src/scalim/dsl/by_yaml/config_parsing/call_by.py` |
| 9 | `src/scalim/dsl/by_yaml/config_parsing/security.py` |
| 8 | `src/scalim/execution/adaptive/thread_loop_executor.py` |
| 8 | `src/scalim/workflow/resources_base.py` |
| 7 | `src/scalim/dsl/by_yaml/workflow_compile.py` |
| 7 | `src/scalim/workflow/resources_sheetbook.py` |
| 5 | `src/scalim/dsl/by_yaml/workflow_config.py` |
| 5 | `src/scalim/execution/derived_outputs.py` |
| 4 | `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py` |
| 4 | `src/scalim/execution/adaptive/_internal/loadref_scheduler_base.py` |
| 3 | `src/scalim/dsl/by_yaml/config_parsing/field_extract.py` |
| 3 | `src/scalim/dsl/by_yaml/workflow_entrypoints.py` |
| 3 | `src/scalim/execution/pipeline/base/_adaptive_pool.py` |
| 3 | `src/scalim/hooks/_internal/manager_base.py` |

### # pragma: no cover pragma 形态粗分类

| 类型 | 命中 | 文件数 |
| --- | ---: | ---: |
| `plain`（仅 `pragma: no cover`） | 125 | 34 |
| `type: ignore` 同行叠加 | 4 | 1 |
| `py<...` 兼容注释 | 3 | 1 |

## cast(...) 分类

### A. YAML DSL 解析/编译边界 (`src/scalim/dsl/by_yaml/**`)

- 现状：命中最多（约一半以上），主要来自「JSON-like → 结构化模型 / 运行时契约」的转换边界。
- 结论：短期先保持“报告 + 分布”口径，不做 blanket allow；优先从热点文件入手补运行时契约/收紧类型以减少 `cast`。对确属必要的边界，优先行级 `allow-cast` 并写清原因，文件级 allow 仅留给极少数“整文件都是边界且短期无法收口”的模块。

### B. Workflow / Execution 运行时边界 (`src/scalim/workflow/**`, `src/scalim/execution/**`)

- 现状：多为资源加载、执行器、输出组合等边界层与泛型容器拆装。
- 结论：
  - 能通过 **收紧函数签名/返回类型** 消除的，归为「应补类型」并优先重构（低风险优先）。
  - 仍依赖动态输入或外部库边界的，按点位补 `allow-cast`（行级优先；文件级仅限极少数整文件边界模块）。

### C. 工具脚本/测试 (`scripts/**`, `tests/**`)

- 现状：主要是 AST/脚本协议适配与测试夹具类型收窄。
- 结论：**允许存在，但必须显式 allow 并说明原因**（脚本允许文件级；测试优先行级或文件级，避免在核心运行时代码扩散）。

## # pragma: no cover 分类

### A. Python 版本/兼容分支（例如 `py<3.8` 注释附近）

- 现状：用于兼容分支在当前测试矩阵下不可达。
- 结论：大概率需要 allow，但应优先行级 `allow-no-cover`（原因写明兼容范围/不可达前提）；不要直接上文件级 allow。

### B. 抽象边界/兜底分支（例如不应被触达/强约束错误）

- 现状：多见于「理论不可达」或「防御性断言」分支。
- 结论：按点位补 `allow-no-cover` 并写清原因；后续逐步评估是否可通过更精确的测试覆盖移除 `no cover`。

### C. 可测试逻辑分支

- 现状：少量 no-cover 可能掩盖真实可测分支。
- 结论：归为「应补测试」：优先补测试并移除 `# pragma: no cover`，仅保留确属兼容/抽象边界的用法。
