## Why

workflow 的共享输出资源（csv/xlsx）在并发或平台调度场景下,若直接写入“最终导出路径”,很容易出现:

- 中间过程污染最终路径（部分写入/半成品/临时文件残留）
- 出错后排障困难（最终路径已被覆盖,而 staging 信息缺失）
- 依赖 lock file 的互斥/治理会引入额外风险（锁文件遗留/误回收/跨文件系统语义差异等）

在我们常见的运行模型下,workflow 通常是“单进程内线程并发”为主,并且默认 `max_concurrency=1`；更合理的根治方案是:

- **每次 workflow run 先写入唯一路径的 staging**
- workflow 成功后再把 staging 的产物 **覆盖发布** 到用户配置的最终导出路径

从而把“输出一致性/清理/可排障”收敛为 workflow-level SSOT,避免在资源层堆叠锁治理复杂度。

## What Changes

- 新增 workflow 级配置面 `workflow.options.output_staging`：
  - `dir_name`：staging 目录名（默认 `.scalim-staging`）
  - `keep_on_success`：成功时是否保留 staging（默认 `false`）
  - `keep_on_failure`：失败时是否保留 staging（默认 `true`）
- workflow 共享输出的落盘策略变为“两阶段”：
  1) commit 阶段写入 staging（唯一路径）
  2) workflow 成功结束后,覆盖发布到最终导出路径（原子 replace）
- workflow runtime 不再对共享输出使用 write lock file（锁语义不再作为 v1 的默认/推荐路径）。

## Capabilities

### Modified Capabilities
- `yaml-dsl-workflow`: 扩展 workflow YAML 的 `workflow.options`,新增 `output_staging` 并纳入 schema-only 校验。
- `workflow-ir`: 扩展 `WorkflowOptionsIr`,把 `output_staging` 作为编译边界的一部分携带到 runtime。
- `workflow-shared-output-containers`: 调整共享输出的 commit/publish 语义: staging → publish,并定义清理策略。

## Impact

- 受影响代码（SSOT）：
  - `src/scalim/workflow/resources_base.py`、`src/scalim/workflow/resources_*.py`（staging/publish + 移除 workflow write lock）
  - `src/scalim/workflow/execute.py`（把 output_staging 传入资源管理器）
  - `src/scalim/dsl/by_yaml/workflow_config/*`、`src/scalim/dsl/by_yaml/schema_dsl/*`（YAML 解析 + schema）
  - `src/scalim/spec/ir/_workflow.py`、`src/scalim/dsl/by_yaml/workflow_compile.py`（IR 边界）
- 受影响测试：staging publish/cleanup 行为、keep_on_success/keep_on_failure 覆盖。
- 文档与生成物边界（SSOT vs generated）：
  - SSOT 文档：`docs/doc/yaml-dsl/workflow.md`
  - SSOT schema：`src/scalim/dsl/by_yaml/schema_dsl/builder.py`；生成物 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`

