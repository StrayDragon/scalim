## Context

workflow 入口 `scalim.dsl.by_yaml.run_workflow(...)` 当前只能接受一组全局运行期参数(例如 `batch_size/components/overrides/guardrails/loader_retry/...`),并将其注入到整张 DAG 的所有 demand runs。

在多 demand 扇入/扇出型报表场景中,per-run 差异化运行策略是现实需求:

- 部分 runs 适合更小 `batch_size` 以降低峰值内存
- 部分 runs 适合更大 `batch_size` 以提升吞吐
- 某些 runs 需要更重的可观测性/guardrails(排障/灰度),而其它 runs 需要轻量路径

同时,按既有 “runtime policy 迁出 YAML 主线” 的原则,这些 knobs 不应回流到 demand/workflow YAML；因此需要一个 Python 入口侧的 per-run patch 机制,既保持 authoring 分层,又能在未来扩展(例如分页衔接/checkpoint 等新 runtime knobs)。

本变更聚焦于: **以 `workflow.runs[*].id` 为 key,为每个 demand run 注入一个 typed 的 runtime patch**。

## Goals / Non-Goals

**Goals:**

- `run_workflow(..., run_patches_by_id=...)` 支持对不同 run id 注入不同的运行期策略
- patch 语义可扩展,避免为每个新 knob 引入新的 `node_xxx_by_id` 参数
- patch MUST 支持明确的“继承/禁用/覆盖/追加”语义,避免 `None` 与 “未设置” 混淆
- fail-fast:
  - unknown run id 直接报错并列出合法 ids
  - patch 仅允许覆盖 runtime/perf/control-plane knobs,禁止触及 allowlist 等安全边界参数
- 运行时仍需兼容 Python 3.6,且入口模块 import 不引入可选依赖

**Non-Goals:**

- 不修改 workflow YAML schema,不在 YAML 中新增 runtime policy 字段
- 不对非 demand runs(例如派生的 write/append/condition/selector 节点)提供 patch 入口
- 不重新设计 `RunOverrides`/output model
- 不在本 change 中引入分页衔接/checkpoint 等新 knobs(但设计需允许未来增量加入)

补充说明:

- `run_patches_by_id` 的 scope 是 **demand runs**(即 `workflow.runs[*]`) 的运行期参数构造;它不会改变 workflow 编译出来的内部派生节点(例如 `__wf__write.*`). 因此它不是“按 demand 定制 workflow-managed book 导出路径”的入口;该类共享资源应通过 workflow YAML `workflow.resources` 与全局 `run_workflow(..., overrides=RunOverrides(resources=...))` 管理。

## Decisions

### 1) 入口参数: `run_patches_by_id` 仅绑定 `workflow.runs[*].id`

选择 `workflow.runs[*].id` 作为 key:

- 与 workflow 内部 `workflow_node_id` 一致,并且与 `$ctx`/`book_sheet_rows.ref.node` 语义一致
- 不依赖 demand YAML `name` 或文件路径,避免“demand 文件替换但策略丢失/错配”
- 不与未来可能出现的“非 demand authoring 节点”耦合

参数命名选择 `run_patches_by_id`(而非 `node_*`),强调其 scope 是 runs authoring surface。

### 2) patch 为 typed dataclasses,并复用 `UNSET` 三态语义

为保持开发者体验与可维护性,patch 采用 typed dataclasses,并复用现有的 `UNSET` sentinel:

- `UNSET` = 继承 `run_workflow()` 的全局参数
- `None` = 显式禁用(当该字段支持禁用语义时)
- 其它值 = 覆盖

这样可避免 `None` 被错误地解释为 “未设置”。

### 3) 列表/合并语义使用 tagged union,而不是字符串开关

针对 `components` 这类需要表达 replace/extend/disable 的字段,使用 tagged union 以保持意图显式且可通过 `isinstance()` 分发:

- `ComponentsInherit()`：继承全局
- `ComponentsReplace(items=[...])`：替换(含 `[]` 表示显式禁用)
- `ComponentsExtend(items=[...])`：在全局基础上追加

同理,`RunOverrides` 在 per-run patch 中采用显式的 “继承/禁用/替换” 语义:

- `inherit`: 继承 `run_workflow(...)` 传入的全局 `overrides`
- `disable`: 对该 run 禁用 overrides(视为 `None`)
- `replace`: 为该 run 提供一个新的 `RunOverrides`,并以其替换全局 overrides

该 change 不内置 “merge-on-top-of-global overrides” 的特殊语义;当调用方需要“保留全局 overrides,仅变更其中一小部分”时,应在用户侧显式构造最终 `RunOverrides` 对象并用 `replace` 语义注入。

**注意:** `disable` 仅禁用用户侧的全局/per-run `RunOverrides`；workflow YAML 的 `workflow.resources` 仍会在 `_merge_node_overrides` 阶段作为低优先级 overlay 被应用,以保证 IO 资源声明不会被 runtime patch 意外抹掉。

### 4) 优先级与合并顺序

对每个 run id,计算 effective options 的推荐顺序:

1. 以 `run_workflow(...)` 的全局参数构造 base options
2. 应用 workflow YAML 的 per-run `init_vars` 合并(现有行为保持)
3. 若启用了 workflow bundle viz 注入,先生成 node 侧默认 viz 配置(现有行为保持)
4. 应用 `run_patches_by_id[run_id]`(若存在):
   - patch 覆盖 base options,并允许覆盖 bundle viz 的默认注入结果
5. 合并 workflow resources overlay(现有 `_merge_node_overrides` 路径保持):
   - `workflow.resources` 为低优先级 overlay
   - global/per-run `RunOverrides.resources` 为高优先级 overlay

该顺序确保:

- patch 为每个 run 的最高优先级(在 runtime knobs 维度)
- workflow resources overlay 不会因 patch replace overrides 而被丢失
- Python 入口传入的 overrides 仍可覆盖 workflow YAML 资源声明(符合 overlay 语义)

### 5) 安全边界: patch 不允许覆盖 allowlist 等参数

`allowed_modules/allowed_functions/resolver_trusted_mode` 等安全边界参数保持为 `run_workflow()` 全局参数,patch 模型不提供对应字段。

实现上:

- 类型系统层面: patch dataclass 不暴露这些字段
- 运行时层面: 对 patch 中被认定为 forbidden 的字段(若以非预期方式注入)fail-fast

## Risks / Trade-offs

- [API 复杂度] patch dataclasses + union types 增加学习成本 → 提供 2-3 个简洁示例(仅 batch_size; batch_size+components; 禁用全局 guardrails)并在错误信息中提示最小写法
- [components 并发契约] workflow 并发模式下全局 components 可能被并发复用 → 文档强调 thread-safe/无状态要求,并建议对 stateful 组件使用 `ComponentsReplace`
- [merge 语义难以直觉化] overrides/resources 合并规则复杂 → 限制 merge 的范围(例如仅 resources deep-merge),其余保持 replace,并在 spec 中写清 precedence

## Migration Plan

- 纯新增 API,不要求迁移既有 YAML/workflow
- 为常见需求提供推荐写法:
  - “大部分 runs 2000,少数 5000”
  - “全局轻量 perf,单 run 追加 debug hook”
  - “单 run 禁用全局 guardrails”

## CLI Scope

本 change **仅覆盖 Python 入口** `run_workflow(...)` 的能力扩展;不在本 change 中为 CLI workflow 入口引入同等能力(例如从外部文件加载 patches)。
