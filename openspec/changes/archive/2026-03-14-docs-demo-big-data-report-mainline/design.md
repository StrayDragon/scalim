## Context

docs-site 的 SSOT 为 `docs/doc/`,并通过 `docs/zensical.toml` 组织导航与站点构建。

当前仓库已经把 `notebooks/marimo/demo_big_data_report/` 收敛为:

- 唯一主线教程入口(`demo_main.py`)
- `just examples` 的集成对拍 gate(`notebooks/marimo/run_examples.py`)
- YAML DSL canonical example 的 SSOT(`by_yaml_dsl/ecommerce_report.yaml`)

但 docs-site 缺少一页显式说明与串联上述入口的“教程索引页”,导致读者需要从 reading-guide/YAML DSL 文档/示例目录中拼线索,可发现性不足。

文档治理约束:

- 禁止手改 `*.gen.*` 文件与 `AUTOGEN:*` 注入区块内部
- 需要生成/注入时通过 `just gen-docs` 刷新并由 `just qa` drift gate 兜底

## Goals / Non-Goals

**Goals:**

- 在 docs-site 增加一页“主线教程: demo_big_data_report”入口页,把跑起来/对拍/排错/SSOT 边界说明清楚。
- 从 `docs/doc/getting-started/reading-guide.md` 等常走入口链接到该页面,提升可发现性。
- 保持文档治理边界清晰: 手工页只承载稳定说明,生成物/注入区块走统一入口刷新。

**Non-Goals:**

- 不在本 change 内重组 YAML DSL 文档体系或新增第二条教程主线。
- 不把 `openspec/specs/**` 或归档变更内容直接纳入 docs-site 页面(保持 docs-site scope)。

## Decisions

### Decision 1: 入口页放在 getting-started 体系内

入口页优先放在 `docs/doc/getting-started/` 下,并从 reading-guide 引用,原因:

- reading-guide 面向贡献者/排查者,天然是“找入口”的第一站
- demo_big_data_report 同时面向“用法/入口”与“回归/对拍”,放在 getting-started 更符合定位

同时,入口页也需要从 `docs/doc/yaml-dsl/index.md` 引用,确保 YAML authoring 使用方在同一信息架构内可发现该主线。

### Decision 2: 页面内容以稳定入口与命令为核心

入口页内容以以下稳定元素为主:

- 入口脚本路径: `notebooks/marimo/demo_big_data_report/demo_main.py` 与 `notebooks/marimo/run_examples.py`
- `just`/`uv` 运行命令(优先引用 `just` SSOT 入口,避免多处复制命令漂移)
- canonical YAML 路径与其 SSOT 角色说明

避免在该页内复制大段 YAML/代码(减少漂移点),改为链接到 canonical example 与 YAML DSL user-guide 的相关章节。

### Decision 3: doc governance 边界显式写入页面

入口页必须包含:

- 哪些路径是 SSOT(手工维护)
- 哪些内容是生成物/注入区块(不可手改)
- 对应的生成入口(`just gen-docs`)与 QA 门禁(`just qa`)

## Risks / Trade-offs

- [风险] 命令/入口路径随重构漂移 → 缓解: 优先链接 `justfile`/stable entrypoint,并在页面中减少复制命令的数量。
- [风险] 页面与 generated reference 重复导致维护点变多 → 缓解: 入口页只做“串联与导航”,reference 仍以 `*.gen.*` 页面为准。

## Migration Plan

1) 新增入口页与最小导航链接(reading-guide/索引页)。
2) 如涉及 injected blocks 或生成 reference,运行 `just gen-docs` 刷新生成物。
3) 通过 `just qa` 与 `just openspec-check`。

## Open Questions

- 导航是否需要在 `docs/zensical.toml` 显式增加该页(若当前 nav 不是自动发现)?
