## Context

这次 `compile_workflow_ir._load_demands()` 抢跑 `validate_unique_field_names`，暴露出当前验证体系的一个结构性缺口：我们已经有“字段从 YAML 主线迁出到 runtime entrypoint”的设计原则，但缺少一套稳定、系统、可复用的验收框架，去保证这些 runtime-only policy 不会在 parse / preload / compile 阶段被提前消费。

现状问题不在于单个测试缺失，而在于缺少统一分层：

- schema / parse 层负责 authoring surface 与迁移提示
- compile / preload 层负责结构分析
- runtime compile 层才负责消费 effective runtime policy
- workflow per-run patch 层负责在具备 run context 时合并 override
- user-entry 层负责验证 notebook / public API 等真实入口没有绕过上述边界

本 change 目标不是立即实现新的测试，而是先把 review 文档和验收口径整理清楚，避免后续补测试时又落回“想到一个补一个”的局部修修补补。

## 当前落地状态(截至 2026-04-04)

- 已抽取并实现一个独立变更：`c21-workflow-preflight-runtime-only-diagnostics`（已归档）。
- 已在 `run_workflow(...)` 中落地一个 policy-aware `preflight` 阶段，并以 `fail-fast + 直接 raise` 的语义处理预检查失败（独立于 `failure_policy`）。
- 已把关键边界语义同步到主规范：
  - `openspec/specs/yaml-dsl-workflow/spec.md`（workflow 生命周期 + preflight 失败语义）
  - `openspec/specs/yaml-dsl-runtime-policy-boundary/spec.md`（runtime policy boundary + “不得在 preload 阶段抢跑”）
  - `openspec/specs/workflow-preflight-runtime-only-diagnostics/spec.md`（preflight 能力本身）

## Goals / Non-Goals

**Goals:**
- 定义 runtime policy boundary 的统一测试分层与责任边界。
- 列出哪些 runtime-only policy 必须进入该验证框架。
- 明确 notebook / public API smoke gate 在这类问题上的职责。
- 输出可 review 的后续任务拆解，供之后逐步实施。

**Non-Goals:**
- 本 change 自身不直接新增任何测试、gate 或 CI 实现；需要落地时应拆分为独立 change（例如已完成的 `c21`）。
- 不在此阶段调整已有 `just qa` 结构或 benchmark 组织方式。
- 不重新设计 YAML 主线 / runtime policy 的语义边界，只做验证体系收敛。

## Decisions

### 1. 用“分层矩阵”而不是零散 case 管理这类问题

后续 review 与实施应以固定矩阵思考，而不是围绕某一个 bug 写单点回归。矩阵建议至少包括：

- **Schema / parse 层**: 迁出的字段仍写在 YAML 时必须 fail-fast，并给 migration guidance。
- **Compile / preload 层**: 只允许消费结构信息，不允许消费 runtime-only policy。
- **Runtime policy merge 层**: 在 workflow 入口内形成 per-run effective `RunOptions`（合并 overrides + run patches + workflow resources overlay）。
- **Workflow preflight 层**: 在 engine 调度前运行“runtime-only 但可推理”的诊断（fail-fast + 直接 raise）。
- **Runtime compile 层**: per-run demand compile/build_request 期间消费 effective runtime policy（包含需要 `$ctx`/init_vars 的逻辑）。
- **Workflow per-run patch 层**: `run_patches_by_id` 的 override 仅在 runtime policy merge 边界之后才生效（不得在 preload 阶段抢跑）。
- **User-entry 层**: notebook / public API / integration smoke 证明真实入口没有绕过上述分层。

补充说明：这里把 `workflow preflight` 作为一个单独层次，是为了让“可推理子集”有一个统一的、可控的最早生效边界；否则很容易在 workflow lazy compile 里反复出现“延迟到执行才报错”的用户体验问题。

### 2. 首批纳入 checklist 的对象必须是“已迁出 YAML 主线”的 policy

优先范围建议收敛到已经明确定义为 runtime-only 的能力，包括但不限于：

- `demand_diagnostics`
- `guardrails`
- `loader_retry`
- `batch_size`
- `demand_failure_policy`
- 其它未来被标注为 “moved out of YAML mainline” 的字段

这样可以让 checklist 直接对齐现有 spec，而不是泛化到所有运行参数。

### 3. Notebook / public API gate 作为用户侧 smoke，而不是唯一回归层

真实入口 smoke gate 很重要，但不应承担全部验证责任。正确的职责分工应该是：

- 单元 / internal coverage：打中具体分支与合并逻辑
- workflow/integration：验证 global / per-run / default 行为
- notebook/public API：证明用户侧示例入口没有出现“底层已修，但真实入口仍坏”的问题

### 4. 评审阶段先形成文档，再决定落地位置

这套 checklist 最终可能落到：

- `tests/yaml_dsl/`
- `tests/workflow/`
- `tests/public_api/`
- `tests/integration/`
- PR / OpenSpec review checklist

但本阶段先不锁死具体目录与命令，只把验收要求写清楚，避免过早绑定实现细节。

### 5. 明确 workflow 生命周期与 boundary 插入点(SSOT)

本类问题之所以容易“修成 workaround”，根因在于生命周期分层不够显式，导致 runtime-only diagnostics 可能被“借道”到更早阶段触发。
因此 checklist 需要把 workflow 的真实生命周期当作 SSOT 写清楚，并在每层明确允许/禁止的动作。

建议以 `run_workflow()` 的真实执行路径为准，按以下层次理解并做验收映射：

- **Authoring / validate 层(可选入口)**: `scalim-cli yaml-dsl validate --yaml-type workflow` 会校验 workflow YAML 并逐个校验 demand YAML；该入口没有 effective runtime policy 合并概念，应在文档里明确其语义与限制(是否允许参数化 policy 见 Open Questions)。
  - 入口：`src/scalim/cli/yaml_dsl.py:_run_validate()`。
- **Workflow compile / preload 层(结构预加载)**: `run_workflow()` 会先加载并编译 workflow YAML -> workflow IR，并在该阶段“预加载 demand YAML 结构信息”。
  - 入口：`src/scalim/dsl/by_yaml/workflow_entrypoints.py:run_workflow()` -> `compile_workflow_ir(...)`。
  - 注意：该阶段必须禁止消费 runtime-only diagnostics(例如 `validate_unique_field_names`)；当前已通过 `YamlDemandLoader.load(..., validate_unique_field_names=False)` 显式避免抢跑：
    - `_load_demands()`：`src/scalim/dsl/by_yaml/workflow_compile.py:_load_demands()`。
    - `derive_cache_pool_consumers()`：`src/scalim/dsl/by_yaml/workflow_compile.py:derive_cache_pool_consumers()`。
- **Runtime policy merge 层(effective options)**: 仍在 `run_workflow()` 内部，会把全局 options、`run_patches_by_id`、以及 workflow-level resources overlay 合并成每个 run 的 effective runtime policy。
  - 入口：`src/scalim/dsl/by_yaml/workflow_entrypoints.py:_apply_workflow_run_patch(...)`、`_merge_node_overrides(...)`。
- **Engine execute 层(lazy compile + run)**: workflow 引擎会在 node ready 时才 compile 单个 demand(并在该阶段解析 `$ctx`、合并 per-run init_vars)，因此任何依赖 `$ctx`/init_vars 的检查都不能作为“全局 preflight”。
  - 入口：`src/scalim/workflow/execute.py:run_workflow_ir()`。

### 6. 对“可推理”的 runtime-only diagnostics 引入 policy-aware preflight(fail-fast)

这次 bug 的用户体感问题之一是：workflow 引擎采用 lazy compile-demand，导致某些“本应属于编译期”的错误会在执行/调度到具体节点时才出现。
对于能在不依赖 `$ctx`/init_vars/外部运行态的前提下推导的 diagnostics，建议引入一个统一的 preflight：在进入引擎前基于每个 run 的 effective policy 进行校验，并 **fail-fast 直接 raise，使整个 workflow 失败**。

该策略的关键是：

- **不破坏 boundary**：compile/preload 阶段仍不得消费 runtime-only policy；preflight 必须发生在 runtime policy merge 之后、engine execute 之前。
- **口径必须与 runtime compile 一致**：preflight 的判定输入应遵循 “YAML -> overrides -> effective config” 的顺序，避免误报/漏报。
  - 例如 `validate_unique_field_names` 是否需要触发，不仅取决于字段 display name 是否重复，还取决于 effective outputs 是否会用 `header_fields_output_by=name` 写 header，以及在 workbook append 模式下 `header_policy` 是否为 `never`。
- **fail-fast**：遇到第一个 run 的第一个触发错误，立即 raise；不做跨 run 聚合报告(实现简单、维护成本低)。

首批 preflight 只建议覆盖一个具体对象：`DemandDiagnosticsPolicy.validate_unique_field_names`。

### 7. preflight 采用“小框架”(context + check registry)，避免散落 if/flag

为了长期可维护(避免未来新增 runtime-only policy 后再次出现“漏了某个入口”的回归)，preflight 不应以“在某处手动传 False / 某处加一个 if”方式扩散。
建议将其抽象为一层小框架：

- `WorkflowPreflightContext`：包含 workflow path/config/IR、预加载的 `DemandConfig`(保证不抢跑 diagnostics)、以及可生成 per-run effective options 的必要信息(base options、`run_patches_by_id`、workflow resources overlay)。
- `WorkflowPreflightCheck`：每个 check 具备
  - `is_triggered(...)`：快速判定是否需要检查(短路)；
  - `run(...)`：执行检查并在失败时 raise。
- `preflight_checks: List[WorkflowPreflightCheck]`：集中注册，形成“runtime-only diagnostics 可推理子集”的显式清单。

该框架的一个硬性边界约束是：check 必须可在不解析 `$ctx`、不依赖 init_vars 的前提下完成；否则只能保留在 per-node runtime compile 阶段。

### 8. “可推理子集”清单(SSOT)必须显式列出,并控制扩张

为了避免 scope creep，本类 preflight check 必须以“显式清单”管理（registry 即 SSOT），并遵循以下约束：

- **可推理**：不依赖 `$ctx`、不依赖 init_vars、也不依赖外部运行态（例如输出文件是否已存在、sheet 是否已存在）。
- **口径一致**：必须按 “YAML → overrides → per-run patch → effective outputs/resources” 的口径判断触发条件，避免误报/漏报。
- **最小化**：只覆盖 runtime-only 且用户体验明显受益（否则就留在 runtime compile，不要强行前移）。

v1（已在 `c21` 落地）：
- `validate_unique_field_names`：当 effective outputs 会写 `header_fields_output_by=name` 的 header 时，拒绝 duplicate effective field display names。

候选（仅列清单，后续若要落地必须单开 change 并补齐测试）：
- `loader_retry` 纯配置一致性：例如 `enabled=true` 时必须提供 `should_retry`（不依赖 demand YAML）。
- `batch_size` 纯配置一致性：例如 `batch_size` 为负数/零时 fail-fast（不依赖 demand YAML）。
- `guardrails` 纯配置一致性：例如互斥项/缺省项的可读错误（不依赖 demand YAML）。

说明：上述候选属于“run options 自身的不变量校验”，原则上可以在 workflow 入口更早失败；是否纳入 preflight 框架还是入口直校验,以“可维护 + 不引入重复校验点”为准。

### 9. `scalim-cli yaml-dsl validate` 的口径: 保持 authoring-only,不做 policy-aware 参数化

结论：
- `scalim-cli yaml-dsl validate --yaml-type workflow` 保持 authoring-only（schema/parse + 结构校验）语义。
- 该入口不引入“runtime policy 参数化”（不接入 overrides / run patches / effective merge），因此不会运行 workflow preflight。

原因：
- CLI validate 若引入 policy-aware 参数化，必然需要一套新的、强类型的 overrides/run-patches 表达与解析；这属于独立产品面与 UX 设计问题，应该单开 change 收敛，而不是在 checklist 里顺手加开口子。
- workflow 的最早 policy-aware 诊断边界已由 `run_workflow(...)` 的 preflight 覆盖；用户在真实入口运行时能够 fail-fast 拿到清晰错误信息。

## Risks / Trade-offs

- [风险] checklist 写得过泛，后续无法落地。 -> 缓解：要求每条规范都映射到明确测试层与至少一个候选入口。
- [风险] notebook gate 变多后运行时间上升。 -> 缓解：文档里明确 smoke gate 必须保持最小 fixture、最小 oracle。
- [风险] 把所有运行参数都塞进同一框架，范围失控。 -> 缓解：首批仅覆盖“已迁出 YAML 主线”的 runtime-only policy。
- [风险] review 只停留在文档，不进入实施。 -> 缓解：`tasks.md` 预先拆出可逐步落地的任务序列。
- [风险] preflight 过度扩张，开始依赖 `$ctx`/init_vars/外部运行态。 -> 缓解：框架层面规定“可推理子集”原则；不满足的检查仅保留在 per-node runtime compile。
- [风险] preflight 引入额外的 YAML load/解析开销。 -> 缓解：仅在“存在被启用的可推理 preflight 配置”时触发；并尽量复用 compile/preload 阶段已加载的 `DemandConfig`。

## Migration Plan

建议后续实施按以下顺序推进：

1. 先 review 并冻结 checklist 文档。
2. 选定首批 policy（建议从 `demand_diagnostics` 开始）做完整矩阵试点。
3. 将 notebook/public API smoke 明确成固定 gate。
4. 再把 checklist 扩展到其它 runtime-only policy。

## Next Proposals (TBD, 不在本 change 落地)

- 若要把更多 diagnostics 前移到 preflight：应为每个候选单开 change，并提供一份明确的“触发条件/口径/失败语义/测试覆盖”设计与验证。
- 若要提供 policy-aware CLI validate：建议新增一个独立入口（例如 `scalim-cli yaml-dsl workflow preflight` 或等价命令），避免污染 authoring-only validate 的稳定预期。
