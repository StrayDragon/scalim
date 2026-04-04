## Context

近期 `validate_unique_field_names` 再次出现“修成 workaround”的症状（修复点依赖调用方记得传某个 flag/参数），根因是 workflow 生命周期分层没有在代码结构上被强约束：runtime-only policy/diagnostics 容易在 parse / preload / compile 阶段被“借道”提前消费。

我们已经落地了 workflow `preflight`（policy-aware 的最早边界），但当前 `run_workflow(...)` 的实现仍然表现为“长入口函数 + 交织多个阶段职责”，并存在长期维护风险：

- 同一语义散落在多处（effective outputs/resources 的口径与触发条件判定容易 drift）
- “阶段边界”更多靠约定与 review，而不是由代码结构强约束
- demand 的 parse/loader 与 runtime-only diagnostics/compile 之间仍然缺少硬边界，未来重构/新增入口时容易回归

本变更采用路线 **B**：demand 解析改为 parser-only；runtime-only diagnostics 只能在 policy-aware 边界（preflight / runtime compile）运行。
同时以“方案 4”为基础引入 workflow lifecycle `pipeline`（阶段对象/结果对象链式推进），让生命周期成为一等公民，提升可读性与可维护性（解析侧性能不作为主要目标）。

## Goals / Non-Goals

**Goals:**
- 将 `run_workflow(...)` 重构为显式的 lifecycle pipeline：`parse -> preload -> merge effective options -> preflight -> execute`。
- demand 侧实现 parser-only：parser/loader 不运行任何 runtime-only diagnostics；runtime-only diagnostics 统一由 diagnostics runner 在 policy-aware 边界执行。
- 收敛 SSOT：effective outputs/resources 的“触发条件判定”抽到单一 helper，供 preflight 与 runtime compile 复用，降低 drift。
- 用代码结构约束开发者：通过阶段上下文对象（最小上下文）与模块依赖方向，降低“在错误阶段顺手加逻辑”的概率。
- 提供可控的测试/调试 harness：可以在单测中构造 pipeline 中间产物来验证边界（而不是只靠端到端回归）。

**Non-Goals:**
- 不追求解析/预加载的极致性能优化（可读性与可维护性优先）。
- 不扩张 preflight 的诊断范围（v1 仍以 `validate_unique_field_names` 为主）；新检查另开变更。
- 不引入新的外部 lint 脚本作为主要约束手段（约束以代码结构 + 单测/内部 gate 为主）。
- 不改动 `scalim-cli yaml-dsl validate` 的 authoring-only 语义（不引入 policy-aware 参数化 validate）。

## Decisions

### 1) 以 lifecycle pipeline 作为 `run_workflow` 的 SSOT

引入一个内部 pipeline/builder，把 workflow 生命周期拆成一组小而清晰的阶段：

- **parse**：读取 workflow YAML，得到 `WorkflowConfig` + runs 列表（不触达 runtime-only policy）
- **preload / compile (structural)**：对每个 run 的 demand 做结构预加载（仅结构信息，用于 outputs/resources/deps wiring），不得运行 runtime-only diagnostics
- **merge effective options**：将 `overrides`、`run_patches_by_id`、workflow resources overlay 合并为 per-run 的 effective `RunOptions` / effective resources（这是 policy-aware 边界的入口）
- **preflight**：运行 inferable runtime-only diagnostics（fail-fast + 直接 raise；独立于 `failure_policy`）
- **execute**：启动 workflow engine 调度与执行（包含 lazy runtime compile / compile-on-ready）

关键原则：每个阶段都产出一个“阶段结果对象”（context/result），下一阶段只能基于上一阶段结果推进。阶段结果对象的字段集合就是“允许的信息面”，用结构限制滥用空间。

补充：阶段的“最小上下文”本身是边界治理手段。例如 structural preload 的结果对象 SHOULD 只包含 `DemandConfig` 等结构信息，不应携带“已合并的 runtime policy”，从而减少“顺手在 preload 阶段加 policy-aware 校验”的概率。

### 2) demand 解析改为 parser-only（路线 B）

将 demand 的“解析/结构化”与“runtime-only diagnostics/compile”彻底分离：

- **parser-only**：只做 YAML->AST/Model 的解析、schema/authoring 侧约束与结构抽取；不得根据 runtime policy 运行 diagnostics。
- **diagnostics runner**：在 policy-aware 边界接收 `(demand结构, effective RunOptions, effective outputs/resources)`，执行 inferable checks（例如 `validate_unique_field_names`）。
- **runtime compile**：在 per-node 编译/物化阶段消费剩余 runtime policy（包含依赖 `$ctx`/init_vars 的逻辑）。

这会带来破坏性重构（内部 API 变化），但能显著降低“parser/loader 偷跑 runtime policy”的回归概率。

### 3) 将 effective outputs/resources 口径与触发判定收敛为 SSOT helper

本类 bug 的高发点通常是“触发条件判定”分散在多个边界：preflight、runtime compile、某些 YAML 层 precheck/legacy 分支。

因此做一个明确的 SSOT helper（名字与位置以实现为准），统一提供：

- “是否会写 header 且 `header_fields_output_by=name`”这类触发判定
- effective resources overlay 的口径计算（workflow resources + overrides + per-run patch）

preflight 与 runtime compile 只消费 SSOT helper 的结果/函数，避免复制粘贴逻辑。

### 4) 用“代码结构”而不是“外部脚本”约束边界（更可维护）

不采用高侵入外部 lint 脚本作为主要治理手段，而是通过以下方式让开发者更难写出越界代码：

- **阶段上下文对象最小化**：早期阶段结果对象不携带 runtime policy；需要 runtime policy 的逻辑只能在 `merge effective options` 之后获取到必要字段。
- **模块依赖方向**：parser/preload 模块不反向依赖 runtime compile/policy 模块；pipeline 模块在顶层负责编排依赖。
- **稳定的内部入口**：在单元测试中直接调用 pipeline 的阶段函数/构造器，形成“最小 harness”，让边界逻辑可以被单测覆盖，而不是只能靠 workflow 端到端回归。
- **轻量“边界回归”单测**：用 Python 级别的 import 约束测试（例如禁止某些模块在 parser 层被导入/调用），作为长期回归兜底（仍属于 repo 内测试，不是外部脚本）。

### 5) preflight 失败语义保持 fail-fast + 直接 raise（独立于 `failure_policy`）

沿用既有约束：

- preflight 发现问题立即 raise 中止整个 workflow
- 不聚合多 run 报告（实现简单、维护成本低）
- `failure_policy` 不影响 preflight 失败语义

### 6) “effective 口径”以 `YAML -> overrides -> workflow overlay -> per-run patch` 的顺序决定（并举例）

本变更的核心之一是：任何 inferable runtime-only diagnostics（例如 `validate_unique_field_names`）的触发条件与输入口径 MUST 以“有效配置”（effective config）为准，而不是以“原始 YAML”为准，否则会出现误报/漏报。

本变更约定的口径为：
- **YAML**：demand/workflow authoring surface（`DemandConfig`/`WorkflowConfig`）
- **overrides**：调用方提供的 runtime overrides（全局 `RunOverrides` + per-run patch 中的 `RunOverrides`）
- **workflow overlay**：workflow YAML 的 `workflow.resources` 作为低优先级 overlay（仅影响 resources；且即使 overrides 被禁用，overlay 仍生效）
- **per-run patch**：`run_patches_by_id` 对对应 run 的最终覆盖（高优先级）

示例 A（避免误报）：  
某 demand YAML 有 duplicate effective field display names，但 runtime overrides 把 outputs 改为“不会写 `header_fields_output_by=name` 的 header”（例如 `header_fields_output_by=id` 或 `include_header=false`）。  
在这种情况下，preflight MUST 按 effective outputs 口径判定“该 check 不触发”，因此 MUST NOT 抛出 duplicate-name 错误。

示例 B（避免漏报）：  
某 demand YAML 本身 outputs 不触发该检查，但 runtime overrides 将 outputs 改为“会写 `header_fields_output_by=name` 的 header”。  
在这种情况下，preflight MUST 按 effective outputs 口径判定“该 check 触发”，并在存在 duplicate names 时 fail-fast 报错。

### 7) 结构预加载必须与 runtime entrypoint 的 YAML 解析设置一致（防止 parse drift）

workflow structural preload 会解析 demand YAML，因此 MUST 与 runtime entrypoint 使用同一组 YAML 预编译/加载设置（例如 template 预编译 sandbox 与渲染长度上限、allowed_yaml_roots 等），避免出现：
- preload 能解析但 runtime compile 解析失败（或相反）
- 预编译策略不一致导致行为漂移

实现上建议由 pipeline 统一持有“解析设置/上下文”，并在 parse/preload/preflight/runtime-compile 等所有会解析 YAML 的阶段复用。

### 8) 文档/生成边界与 drift gate（实现前收敛）

本变更以重构代码为主，不引入新的生成物。

- **手工维护（SSOT）**：`src/scalim/dsl/by_yaml/**`、`tests/**`、`openspec/changes/c22-.../**`
- **禁止手改生成物**：任何 `*.gen.*` 文件与 `BEGIN/END AUTOGEN:*` 注入区块（如需变更，必须修改 SSOT 并运行 `just gen-docs`）
- **漂移/一致性 gate**：
  - OpenSpec 工件：`just openspec-check`
  - 代码质量与回归：`just qa`（含 lint/tests + drift checks）

## Acceptance / Verification

本变更的“集成验收”应覆盖生命周期的每个边界点（而不是只靠一个端到端用例）：

- **Pipeline 阶段验收（单测）**
  - 能在不启动 engine 的情况下执行到 preflight，并拿到 per-run effective options 的阶段产物
  - structural preload 对 duplicate names 不失败（无论 `validate_unique_field_names` 默认值如何）
  - preflight 失败时，必须在 engine 启动前直接 raise（并且 fail-fast 第一个错误）

- **口径一致性验收（单测）**
  - 触发判定使用 SSOT helper；覆盖“示例 A/示例 B”（overrides 关闭/开启触发条件）
  - preflight 与 runtime compile 使用同一套触发判定逻辑（避免 drift）

- **边界回归验收（单测）**
  - structural preload 代码路径不得导入/调用 runtime-only diagnostics runner（import/调用约束）
  - parser-only loader 不提供（或不使用）runtime-only diagnostics 的开关参数（减少误用面）

- **全量门禁**
  - `just qa` 通过
  - `just openspec-check` 通过

## Risks / Trade-offs

- [风险] 破坏性重构牵涉面大，容易引入行为回归。 -> 缓解：以 pipeline 阶段为单位拆解实现与测试；优先稳定语义边界（preload 不抢跑、preflight 口径一致）后再做内部清理。
- [风险] “结构约束”不足以阻止未来越界 import/调用。 -> 缓解：增加轻量边界回归单测（import 约束 + 关键路径的行为断言），并将触发判定收敛到 SSOT helper。
- [风险] SSOT helper 成为新的“万能模块”导致耦合。 -> 缓解：只收敛“effective outputs/resources + 触发判定”这类共享语义；其它逻辑保持在各阶段内部。
- [风险] 新 pipeline 让调试路径变复杂。 -> 缓解：阶段结果对象可序列化/可打印关键摘要；测试中可直接断言阶段产物。

## Migration Plan

1. 新增 lifecycle pipeline 模块与阶段结果对象（先并行实现，不立即删除旧代码）。
2. 将 `run_workflow(...)` 迁移为调用 pipeline（保持外部行为一致）。
3. 重构 demand 解析为 parser-only，并把 runtime-only diagnostics 迁移到 diagnostics runner（preflight/runtime compile 边界）。
4. 抽取 SSOT helper，并替换掉 preflight/runtime compile 内部的重复触发逻辑。
5. 重排与补齐测试：按阶段覆盖（parser-only、preload structural、effective merge、preflight、execute glue）。
6. 删除旧路径/旧工具函数（允许破坏性清理，不做兼容分支）。
7. 运行 `just qa` 与 `just openspec-check` 验收。

回滚策略：若中途发现不可控回归，可先保留 pipeline 与旧入口并行，通过 feature-flag/内部切换回旧路径；待阶段测试补齐后再切换为默认并删除旧代码。

## Open Questions

无（所有关键语义已在 Decisions 与 Acceptance/Verification 中确定化）。 
