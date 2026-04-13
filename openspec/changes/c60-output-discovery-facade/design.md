## Context

当前 D-2 版本化输出协议通过以下文件为下游提供“稳定入口”:

- `<output_root>/manifest/latest.json`
- `<output_root>/versions/<version_id>/manifest.json`

在真实集成中(服务端按请求并发跑 demand/workflow、pytest 对拍、agent skill 的 downstream 适配),下游经常需要:

1. 读取 `latest.json` 得到当前 `version_id`
2. 再读取版本 manifest 或按约定拼接 `books/<book_id>.xlsx`、`files/<file_id>.csv`

目前这些逻辑多以“手写 JSON + 手写路径拼接”的形式出现,使得 D-2 的内部落盘形状(例如 `versions/` 目录名、manifest 文件名与字段名)扩散为事实公共 API。

本变更希望引入一个稳定的 facade,让用户只表达“给我这个 output root 的最新产物”,而不是理解/依赖“versioned outputs”内部协议细节。

约束:

- `src/scalim/` 运行时必须兼容 Python 3.6。
- public API 必须纳入 `__all__` 治理与 public API suite 回归。
- docs/skills/notebooks 属于用户材料,不得把内部实现路径当作推荐导入;生成物与 injected blocks 仍遵守仓库治理规则。

## Goals / Non-Goals

**Goals:**

- 提供一个稳定公开入口模块(建议 `scalim.shortcuts.resources`),将“从 output root 发现最新产物”的需求收敛为单点 API。
- facade 语义不暴露 `versioned` 概念,用户不需要:
  - 读取/解析 `manifest/latest.json`
  - 拼接 `versions/<id>/...` 路径
- facade 必须覆盖:
  - workflow/demand 写出的 workbook(books) 与 csv files 两类产物
  - 缺失产物/缺失 latest 的可诊断失败模式或 `try_*` 模式
- 该入口的命名与边界应允许未来扩展:
  - input artifacts（workflow 节点间输入工件）
  - ctx resources（ctx store 的对外可见/可消费形态）
  - 其它资源/工件发现能力
- 将该入口纳入 public API 治理:
  - curated entrypoints 文档与规范
  - marimo public API suite 新增章节覆盖
  - skills/docs 示例优先使用 facade（不再手写 JSON）

**Non-Goals:**

- 不修改 D-2 底层协议（`workflow-versioned-outputs`）的目录布局或并发语义。
- 不在本变更内引入 retention/prune/GC（版本清理）。
- 不提供跨 root 的“全局 latest”一致性或分布式锁语义；并发语义仍以 D-2 为准（last-writer-wins, root 是 namespace 边界）。
- 不把该 facade 设计为“可写入/发布”接口；写出仍由 sinks/workflow 负责。

## Decisions

### Decision 1: facade 属于“输出发现/产物定位”,不放入 `sinks`

备选:

1. `scalim.sinks`:
   - 优点: 用户常用模块。
   - 缺点: sinks 的语义是“写出端契约”,而 output discovery 是“读/发现已发布产物”;边界混淆会放大模块耦合与维护成本。
2. `scalim.dsl.yaml_dsl.tools`:
   - 优点: 已是 curated entrypoint。
   - 缺点: 输出协议并非 YAML DSL 专属（Python DSL / workflow runtime / 未来其它入口同样需要）；放入 DSL tools 会把跨 DSL 的 IO 合同绑定到 authoring 层。
3. `scalim.execution.versioned_outputs`（维持现状）:
   - 优点: 已有实现。
   - 缺点: 暴露 `versioned` 概念与落盘细节;不符合“隐藏内部架构”的目标。

选择:

- 新增一个更稳定、更通用的 shortcut/facade 入口: **`scalim.shortcuts.resources`**。
  - `shortcuts` 表达“用户侧快捷用法”,减少与 `sinks`（写出端）/`outputs`（YAML authoring 术语）的概念混淆。
  - `resources` 与 YAML 中 `workflow.resources.*` 的用户心智对齐,并预留未来把 input artifacts / ctx resources / 其它资源类能力纳入同一入口的扩展空间。
- `scalim.execution.versioned_outputs` 保留为底层实现与内部协议工具（不作为推荐入口）。

### Decision 2: `scalim.shortcuts.resources` 从 v1 起采用 package 结构（并提供清晰可导入的子域）

本变更要求 `scalim.shortcuts.resources` **从一开始就采用 package 结构**，以便未来在同一命名空间下按子域扩展，而不是不断新增新的顶层模块让用户记忆。

约定（v1 + 预留 v2+）：

- `scalim.shortcuts.resources`：稳定入口 package（用户从这里开始）
- `scalim.shortcuts.resources.outputs`：**v1** 子域（本轮仅实现 outputs discovery）
- `scalim.shortcuts.resources.inputs`：未来子域（input artifacts 相关）
- `scalim.shortcuts.resources.ctx`：未来子域（ctx resources 相关）

推荐导入方式（直接、规范、便于未来扩展）：

```py
from scalim.shortcuts.resources import outputs
```

使用示例（仅示意）：

```py
from scalim.shortcuts.resources import outputs

latest = outputs.load_latest_outputs(output_root)
report_xlsx = outputs.latest_book_path(output_root, book_id="report")
```

### Decision 3: 对外契约以“output root → latest published outputs snapshot”为核心（v1）

建议 API 形态（仅示意;具体符号以实现为准；入口位于 `scalim.shortcuts.resources.outputs`）:

- `load_latest_outputs(output_root) -> LatestOutputs`
- `try_load_latest_outputs(output_root) -> Optional[LatestOutputs]`
- `latest_book_path(output_root, book_id) -> Path`
- `latest_file_path(output_root, file_id) -> Path`

其中 `LatestOutputs` 是一个稳定数据结构(例如 dataclass),至少包含:

- `run_id: str`: 对应 D-2 的 `version_id`（来自 workflow 的 `workflow_exec_id` 或 standalone demand 的 `run_id`；但不在命名上暴露“version”）
- `books: Mapping[str, Path]`
- `files: Mapping[str, Path]`

约束:

- facade 返回的路径 MUST 为可直接使用的 `Path`（用户无需拼接 `versions/<id>`）。
- facade MUST 在错误信息中提供可诊断上下文（root、缺失文件、解析失败原因等）。

### Decision 4: 兼容“没有产物/没有 latest”的场景

当前实现中,部分运行在 outputs 被跳过时不会产生 `latest.json`（例如没有写出/被覆盖/被显式禁用）。

因此 facade 必须同时支持:

- fail-fast 模式：`load_latest_outputs()` 在缺失时抛出明确异常
- optional 模式：`try_load_latest_outputs()` 缺失时返回 `None`

### Decision 5: public API 治理与材料同步策略

SSOT/生成边界:

- 行为 SSOT: 本 change 新增 capability spec `resources-discovery`。
- public surface 治理 SSOT: 修改 `public-api-surface-governance` 与 `marimo-example-public-api-suite` 的 delta spec,要求示例与 curated entrypoints 同步。
- 用户材料（docs/skills/notebooks）只表达官方用法,不承担行为 SSOT；不得手写依赖内部协议细节作为推荐路径。
- 本变更不修改任何 `*.gen.*` 或 injected blocks；若需扩展生成页,应按 doc governance 走生成入口（后续实现阶段处理）。

## Risks / Trade-offs

- [命名与边界争议] `resources` vs `artifacts/exports` 等命名可能引发理解偏差或 scope creep → 在 spec 中明确这是“发现已发布产物”的 facade(v1 仅 outputs),并在 public API suite 里给出最小示例。
- [语义漂移] 如果未来内部不再使用 `latest.json`/manifest,facade 需要稳定迁移策略 → facade 的实现必须完全隐藏底层文件形状,并为未来替换保留单点改动空间。
- [并发误用] 多请求共享同一 root 时 `latest` 为 last-writer-wins → facade 文档必须明确 root 是 namespace 边界,并建议服务端按请求/租户拆 root。

## Migration Plan

- 文档/示例迁移:
  - 将现有示例中“手写读取 latest.json + 拼路径”的写法迁移为 `scalim.shortcuts.resources` facade。
  - 保留底层 D-2 协议不变,因此不会影响现有产物布局。
- 回滚策略:
  - 若 facade 出现问题,下游仍可退回到直接读取 `latest.json` 的旧写法（但该写法不再作为官方推荐）。

## Open Questions

- 是否需要提供一个“固定路径适配器”（latest → copy/rename / symlink）作为额外工具（不在 v1 范围内）？
  - 背景：D-2 的产物路径天然包含 `versions/<run_id>/...`；对某些下游系统（例如 Nginx 静态目录、传统 BI/脚本、外部调度器）而言，它们更偏好一个固定且可预测的最终路径。
  - 适配器要做的事：把某次运行的 “latest outputs 快照” 物化到稳定位置（例如 copy/rename/symlink），从而让下游继续用固定路径消费。
  - 示例（仅示意）：
    - 运行后产物位于 `./out/versions/<run_id>/books/report.xlsx`
    - 适配器将其物化为 `./out/latest/report.xlsx`（或用户指定的 `./public/report.xlsx`）
    - 下游永远读取 `./out/latest/report.xlsx`，无需理解 manifest/versions
  - 注意：服务端并发共享同一 root 时 `latest` 为 last-writer-wins；适配器更安全的输入应是“已解析的快照对象/显式 run_id”，而不是再次读取 `latest.json`。
