## Context

`resources.files`(当前稳定仅 `kind=csv_file`) 用于声明最终 CSV 输出路径,并通过 staging → publish 两阶段落盘:

- commit: 资源先写入 staging 路径(同一 workflow 执行目录/临时目录),避免中间产物直接污染最终输出
- publish: workflow 结束统一把 staged 输出发布到 `final_path`(原子 replace/copy-atomic)

当多个 workflow 进程并发写同一 `final_path` 时,现状对 CSV 输出会发生“最后写入者胜”的静默覆盖。相比 `books` 已有/正在强化的 `write_lock`,`files` 侧缺少 `write_lock` 配置入口,导致无法选择 fail-fast 行为。

此外,`resources.files` 也是 standalone demand 输出的稳定入口: 运行时会把 `resources.files.<id>` 编译为 `OutputSpec(format=\"csv\", path=..., encoding=...)`,并创建 `CSVSink/ColumnCSVSink` 写入文件(原子 replace),同样存在并发覆盖风险。

约束与治理:

- 运行时保持 Python 3.6 兼容
- YAML DSL JSON Schema 为生成物(禁止手改): SSOT 在 `src/scalim/dsl/yaml_dsl/schema_dsl/**`,通过 `just gen-yaml-dsl-schema` 生成 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`
- 生成物漂移门禁: `just schema-drift-check` 与 `just qa`
- OpenSpec 工件门禁: `just openspec-check`

## Goals / Non-Goals

**Goals:**

- 为 `resources.files.<id>.kind=csv_file` 新增 `write_lock: bool`(默认 `false`) 的配置入口(YAML + overrides)
- 当 `write_lock=true` 时,系统 MUST 在最终文件写入边界对目标路径跨进程互斥,并在冲突时 fail-fast:
  - standalone demand: `CSVSink/ColumnCSVSink.close()` 的原子 replace 边界
  - workflow: publish(staged → final) 边界
  - 错误信息包含 `lock_path` 与可用的 lock owner 信息
- 锁持有时间短: 仅覆盖 publish 边界(影响最终 `final_path` 的步骤)
- 默认行为不变: `write_lock=false` 时不引入锁冲突失败,允许覆盖(历史语义)

**Non-Goals:**

- 不引入阻塞等待/队列化 publish 策略(本次仅 fail-fast)
- 不新增 `csv_memory` 等新的 file kind(如需减少文件 IO,另开 change 讨论新的输出形态)
- 不在 staging 写入/计算阶段持锁(避免长时间占锁)

## Decisions

### 1) 语法与配置面: YAML + overrides 双入口,默认关闭

新增字段:

- YAML: `resources.files.<file_id>.write_lock: bool = false`
- Python overrides: `RunOverrides.resources.files[<file_id>].write_lock: Optional[bool]`

原因:

- YAML 入口用于声明性配置(可被 schema-only 校验覆盖)
- overrides 入口用于部署/调度层按环境启用(例如生产启用锁,开发关闭锁)
- 默认 false 保持历史语义,避免破坏性变更

### 2) IR 传递: 编译期写入 resource options,运行时解析为 mapping

编译期在 `WorkflowResourceIr(resource_type="csv")` 的 `options` 写入:

- `{"kind": "csv_file", "encoding": "...", "write_lock": <bool>}`

运行时在 `execute._build_workflow_resource_defs`:

- 解析 `write_lock` 并构建 `csv_write_lock_by_id: Dict[str, bool]`
- 传入 `WorkflowResourceManager(..., csv_write_lock=csv_write_lock_by_id)`

原因:

- 复用现有资源 defs → manager 的数据流(与 workbook/sheetbook 一致)
- 让 publish 阶段仅依赖 manager 内的“是否需要锁”映射,保持 publish 逻辑单点

### 3) 执行面: publish 边界按 `final_path` 获取 lockfile,冲突即 fail-fast

在 `_WorkflowResourceManagerBase._publish_staged_outputs` 中,对 `resource_type="csv"` 且 `csv_write_lock[file_id]=True` 的输出:

- `lock_path = _acquire_write_lock(final_path, owner=...)`
- 执行 publish(原子 replace 或 copy-atomic)
- `finally: _release_write_lock(lock_path)`

owner 信息至少包含:

- `workflow_exec_id`
- `resource_type`/`resource_id`
- `workflow_node_id`
- `staged_path`

原因:

- publish 是“真正影响最终文件”的边界,锁持有时间最短
- 冲突从“静默覆盖”变为“显式失败”,便于调度系统重试/报警/人工介入

### 4) standalone sink: close 边界按 `output_path` 获取 lockfile

为 `CSVSink` 与 `ColumnCSVSink` 增加 `write_lock` 参数(默认 `False`),并在 `close()` 的原子 replace 边界:

- `lock_path = _acquire_write_lock(output_path, owner=...)`
- `temp.replace(output_path)`
- `finally: _release_write_lock(lock_path)`

同时在 YAML 输出组合层将 `resources.files.<id>.write_lock` 写入 `OutputSpec.write_lock`,并在创建 CSV sink 时传入该值。

原因:

- 与 Excel sink 的 `write_lock` 一致: 都在最终 replace 边界持锁,对 IO 负载影响最小
- 让 `resources.files` 在 standalone 与 workflow 两条路径语义一致,避免“DSL 看起来支持,但某条运行路径不生效”的分叉

## Risks / Trade-offs

- `write_lock=true` 的场景会把并发覆盖显性化为失败,可能暴露既有调度层的重叠运行问题 → 通过明确错误信息 + 调度侧避免同路径并发来缓解
- lockfile 遗留(进程异常退出)会导致后续 publish fail-fast → 当前依赖错误提示引导人工清理;如需 `stale_after_s/force` 自动清理,另开 change
- 该变更不减少文件 IO 本身;只提供互斥语义。若业务目标是降低 IO,应优先使用内存型 book 或引入新的 memory/stream 输出能力

## Migration Plan

- 无强制迁移: 新字段默认 `false`,旧 YAML 不受影响
- 需要互斥的固定路径输出: 显式设置 `resources.files.<id>.write_lock=true` 或在部署层通过 `RunOverrides` 启用

## Open Questions

- 无(本次确定 fail-fast 语义;如需阻塞等待/串行化 publish,另开 change)
