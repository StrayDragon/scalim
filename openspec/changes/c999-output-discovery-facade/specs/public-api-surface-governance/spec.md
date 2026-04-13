# public-api-surface-governance (delta) Specification

## MODIFIED Requirements

### Requirement: stable public entrypoints MUST be explicitly cataloged

系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让“当前能 import 的路径”自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.yaml_dsl` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`
- `scalim.dsl.yaml_dsl.tools`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）
- `scalim.events`（事件 envelope、事件类型常量与事件目录查询入口；typed payload 不作为公共导入契约）
- `scalim.sinks`（sink 契约与常用 sinks；内部 helper 不作为公共导入契约）
- `scalim.shortcuts.resources`（资源类 shortcut 稳定入口 package）
- `scalim.shortcuts.resources.outputs`（输出发现/最新产物定位 facade；隐藏底层 D-2 落盘协议细节）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.yaml_dsl.runtime.*`
- `scalim.dsl.yaml_dsl._internal.*`
- `scalim.dsl.yaml_dsl.schema_dsl.*`
- `scalim.dsl.by_yaml.*`（旧路径：本轮收敛后不得再作为用户侧稳定契约）
- `scalim.events._*`
- `scalim.sinks._internal.*`
- `scalim.execution.versioned_outputs`（底层落盘协议工具；不作为推荐 public facade）

#### Scenario: curated public entrypoints are import-smoke covered
- **WHEN** 维护者执行 public-surface import smoke gate
- **THEN** 目录中的稳定公开入口 MUST 全部可导入
- **AND** gate MUST 以显式白名单为准,而不是扫描整个包树自动放大公共表面
