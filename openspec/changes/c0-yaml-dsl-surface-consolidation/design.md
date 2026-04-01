## Context

本变更聚焦“YAML 配置面收敛”，目标不是解释 DSL 如何使用，而是从 **维护负担** 与 **稳定承诺** 角度，系统性审查当前 demand/workflow 两侧 YAML 可写配置面，并提出一次可破坏性的大重构方案（允许渐进落地）。

本轮分析的事实来源优先级（均来自当前仓库内容）：
1. 最新生成 JSON Schema：
   - `src/scalim/dsl/by_yaml/schema/demand.gen.json`
   - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
2. 用户侧 Python API / facade / 可导入入口：
   - `src/scalim/dsl/by_yaml/__init__.py`（官方入口与 typed overrides/options）
   - `src/scalim/dsl/by_yaml/tools.py`
   - `src/scalim/dsl/by_yaml/workflow.py`、`src/scalim/dsl/by_yaml/workflow_types.py`
   - notebooks/docs/packages 中真实 import 用法（见下文）
3. 当前 YAML 文档、示例、fixtures、canonical examples（notebooks/fixtures）
4. validator / runtime / CLI 行为（用于解释 schema 未覆盖或与 schema 不一致的地方）

### 0) 配置面规模与热点（基于当前 `.gen.json`）

为避免“旧扫描结果复用”，本 change 已基于当前 schema 生成了全量配置清单附录：
- demand：`appendices/schema-inventory-demand.tsv`（**424** 条 schema 路径，不含表头）
- workflow：`appendices/schema-inventory-workflow.tsv`（**81** 条 schema 路径，不含表头）

按路径数量（含嵌套）统计的 demand 热点区域：
- `outputs[*]`：94
- `observability`：70
- `sources`：69
- `resources`：44
- `main_source`：42
- `guardrails`：21

workflow 热点区域：
- `workflow.resources`：44
- `workflow.options`：27

### 1) P0 漂移示例：workflow schema 暴露 `$import`，但 runtime parser 不支持

- workflow runtime 解析对 `workflow.resources` 做了强 unknown-keys 拒绝，仅允许 `books/files`（不支持 `$import`）：
  - `src/scalim/dsl/by_yaml/workflow_config/_parse.py:453`
- 但 workflow schema 由于复用 `ResourcesConfig` 定义，**在多个资源子对象上暴露了 `$import`**：
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json:389` 等
- 另外 workflow 的 `validate_workflow_yaml_text_json` 并不做 jsonschema 校验（依赖手写 parser）：
  - `src/scalim/dsl/by_yaml/workflow_config/_load.py:54`

结论：**schema / runtime / 校验器** 三者对 workflow 的真实“允许配置面”存在结构性不一致；这类不一致本身就是维护债务与用户踩坑源。

### 2) P0 schema typing 债务：多处数值阈值缺少 `type:number`

在 demand schema 中存在多处字段带 `minimum/maximum` 但未声明 `type:number`（示例：retry 秒数、sampling_rate、score_by_rank base/step、count_true_gte.threshold 等），导致 schema 校验对非 number 输入会“静默放行”（约束不生效）。

这会带来：
- 编辑器/LSP 误导（以为被 schema 管住，实际没有）
- runtime/CLI 另写校验逻辑（双份负担）

## Goals / Non-Goals

**Goals:**
- 把 YAML DSL 的“可写配置面”从“控制面 + 业务面混杂”收敛为 **业务建模核心面** 为主，策略/诊断/治理尽量下沉到 Python/CLI/profile。
- demand/workflow 对同概念配置的重复建模收敛（尤其 resources/write policy/import/overrides）。
- 明确后续演进 SSOT：
  - 什么属于 YAML authoring
  - 什么属于 runtime control plane
  - schema/runtime/docs 的生成与 drift gate 策略
- 提供可执行的迁移方案（允许破坏性，但要可渐进落地、可回滚/可验收）。

**Non-Goals:**
- 不在本变更内重新设计 IR/执行引擎/计算语言本体（除非为收敛配置面必须改动）。
- 不追求“保留所有现有开关”；除非强理由，否则默认以长期维护成本为优先。

---

## YAML 配置面收敛审查（用于架构决策）

> 注：完整配置清单在 TSV 附录；本节聚焦“合理性判断 + 收敛动作”。

### 1. 执行摘要

- **总体判断：偏宽且混杂**。demand 的 424 条配置路径中，按 inventory 标记约有：
  - authoring 面：304
  - runtime control 面：92
  - observability/debug/gov 面：107
  说明 demand YAML 既是 declarative DSL，又承担了相当一部分 runtime 控制面职责。
- **最大 10 个维护热点（按“漂移风险 + 组合爆炸 + 重复建模”综合）**：
  1) `observability.*`（70 路径、13+ boolean、多个 format/policy/paths；同时可被 Python overrides/viz_config 替代）
  2) `$import` 的“全域渗透”（demand 含 `$import` 路径 92 条；workflow 也暴露但 runtime 不支持）
  3) `resources.*` 与 `outputs[*].write` 的双入口写策略（同语义多处可配）
  4) `retry` / `main_source.retry` / `sources.*.retry` + `_templates.retry`（三层 + 模板；且 CLI 额外校验 enabled/should_retry）
  5) `guardrails.*`（mode + 多处细粒度阈值；与 `RunOptions.guardrails` 重叠）
  6) workflow：`workflow.resources` 的 schema/runtime 漂移（见 P0）
  7) schema typing holes（数值阈值缺 `type:number`，导致 schema 失效）
  8) `meta` 与 `audit` 两套几乎同形配置组（重复 + 低价值差异）
  9) demand/workflow 同名/同枚举的 `failure_policy`（语义层级不同但命名相同）
  10) “同一能力 YAML 可配 + Python 可配 + runtime fallback” 三入口（例如 resources / outputs / viz）
- **最值得优先收敛的区域（按 ROI）**：
  - P0：workflow `$import` 暴露不一致；schema 数值类型洞；retry enabled/should_retry 模式
  - P1：observability 下沉；guardrails 下沉；resources/write 策略合并；meta/audit 合并
  - P2：imports/$import 范围收敛；main_source 与 sources 关系重构（若收益足够）

### 2. 配置面总览

#### demand 配置面概览（按区域）

- **核心业务建模**（DSL 成立所需）：
  - `sources`、`main_source`、`fields`、`relations`
  - `outputs`（可选，但属于 DSL 的主要表达之一；也可被 `RunOverrides.outputs` 替代）
- **IO/资源**：
  - `resources.books/files`（与 workflow 同构；与 `RunOverrides.resources` 重叠）
  - `outputs[*].to` + `outputs[*].write`（与 `resources.books.*.write_defaults` 重叠）
- **运行时策略**：
  - `batch_size`、`retry`（及 per-source/per-main_source 的 retry）、`failure_policy`
- **观测/调试/治理**：
  - `observability.*`、`include_full_error_message`、`meta`、`audit`、`validate_unique_field_names`
- **收敛债务/组合语义**：
  - `_templates.retry.*`、全域 `$import`

类型分布（按 schema 路径粗略统计）：
- string / enum / boolean 占比高；object 组多且深；`oneOf/union` 较多（尤其 `$import` 与 `{$init_var: ...}`）。

#### workflow 配置面概览（按区域）

- `workflow.runs[*]`：编排 DAG（id/demand/depends_on/init_vars）
- `workflow.options`：并发/失败策略/cache_pool/ctx/resources_wait/output_staging（大量运行时策略）
- `workflow.resources`：books/files IO 资源（与 demand.resources 同构）

复杂度偏高区域：
- `workflow.resources`（因为复用 resources 定义导致 `$import` 暴露与 runtime 漂移）
- `workflow.options`（包含多处 diagnostics/staging 类运行时控制面配置）

### 3. 详细审查表（重要配置项/配置组）

表格说明：
- **角色**：核心 / 扩展 / 运行时 / 观测 / 债务
- **建议动作**：keep / simplify / merge / move-to-python / hide / remove-candidate

| 配置路径（模式） | 类型 | 默认值/隐式行为 | 角色 | 用户价值 | 维护成本 | 重叠项/耦合项 | 建议动作 | 理由 |
|---|---|---|---|---|---|---|---|---|
| `observability.*` | object 组 + 多 bool/enum/string | 多数默认关闭；logging 默认 enabled | 观测/调试 | 排错/性能诊断 | **极高**（70 路径、组合爆炸、与 Python overrides 重叠） | `RunOverrides.viz_config`、components/Observer、CLI 行为 | move-to-python + hide | 让 YAML 变控制面；应由运行入口决定（环境/组织策略差异更大）。 |
| `guardrails.*` | object + enum + 阈值 | `enabled=false`；`mode=fast_fail` | 运行时 | 防止脏数据/类型错 | 高 | `RunOptions.guardrails`、runtime-guardrails 能力 | move-to-python（保留最小 profile 引用） | 护栏属于运行策略；YAML 暴露细粒度阈值会造成长期维护负担。 |
| `retry`/`main_source.retry`/`sources.*.retry` | object + bool + 阈值 | `enabled=false`；max_attempts 默认 3 | 运行时 | 弱网/不稳定 loader | 高（多层重复 + CLI 额外校验） | `RunOptions.loader_retry`、CLI 注入 should_retry | move-to-python + remove-candidate（YAML 侧） | enabled+should_retry 是典型“表面简单但维护代价高”；建议只保留 Python/CLI policy。 |
| `_templates.retry.*` | object 模板 | 提供 YAML 复用 | 债务 | 复用 | 中-高 | `$import`、YAML anchors | remove-candidate | 复用机制重复（$import/anchor/overrides）；模板只覆盖 retry 过窄，收益不抵复杂度。 |
| `imports` + 全域 `$import` | object + union | 文件入口先展开再校验；文本入口拒绝 | 扩展/债务 | 片段复用 | **极高**（92 条 $import 路径，语义渗透） | YAML anchors、Python overrides、workflow 不一致 | simplify（限定范围） | import/overlay 语义扩散会放大 drift；建议限定到少数稳定节点或改成 profile/preset。 |
| `resources.books/files`（demand + workflow） | object 映射 | path 相对 YAML 目录；workflow 会 merge 到 overrides | 扩展/运行时 | 开箱即用 IO | 高 | `RunOverrides.resources`、workflow 层资源覆盖 | keep 但 simplify + unify-layering | 需要保留开箱即用；但必须明确“声明 vs 覆盖”的 SSOT 与优先级，避免双入口。 |
| `resources.books.*.write_defaults` vs `outputs[*].write` | enum/string/bool | 多处默认；同语义多处可配 | 债务 | 调整写入策略 | **高** | `RunOverrides.*WriteDefaultsOverride` | merge | 同语义多入口导致文档/测试/实现倍增；建议确定单一 SSOT（资源级 defaults）+ 输出级少量 override。 |
| `meta` + `audit` | union<bool|object> | `true`=启用默认配置 | 观测/治理 | 运行元信息/审计 | 中 | resources books 的 allow_formulas/write_lock；输出 write | merge 或 move-to-python | 两套几乎同形结构；建议收敛为 `extras` 或通过 Python 统一启用。 |
| `include_full_error_message` | bool | 默认 false | 观测/治理 | 排错 | 低-中 | CLI 输出、错误治理策略 | move-to-python | 属于运行环境策略，不应写入可复用 YAML。 |
| `validate_unique_field_names` | bool | 默认 true | 治理 | 提前发现表头冲突 | 中（与输出写策略耦合） | header_fields_output_by、write.include_header | hide（强制开启）或 move-to-python | 更像组织治理策略；建议默认强制开启，必要时由 CLI/driver 暂时关闭。 |
| `batch_size` | int | 默认 1000（nullable） | 运行时 | 性能/内存折中 | 中 | `RunOptions.batch_size` | move-to-python | runtime knob 与环境强相关；写入 YAML 会导致“复制粘贴配置”扩散。 |
| demand `failure_policy` | enum | 默认 all_fail | 运行时 | 多输出容错 | 中 | workflow.options.failure_policy（同名不同层级） | simplify/rename 或 move-to-python | 同名跨层级易混淆；建议改名/下沉，避免 “policy” 泛滥。 |
| workflow `options.resources_wait.*` / `output_staging.*` | number/bool/string | 多为 diagnostics | 观测/运行时 | 排错/稳定性 | 中-高 | Python `run_workflow(...)` 参数 | move-to-python | workflow YAML 应更 declarative；diagnostics 更适合 driver 配置。 |
| workflow `options.cache_pool.*` | object + enum + budget/pin | 默认无 cache_pool | 必要扩展 | 性能/共享缓存 | 中 | `workflow-cache-pool` spec | keep（但减少旁枝配置） | 价值明确；但要控制枚举/预算/冲突策略的语义稳定性与文档成本。 |

### 4. 用户侧 Python API 对齐分析

#### facade 是否足够清晰

- 推荐入口清晰：`scalim.dsl.by_yaml` 导出 `compile/run/run_workflow` 与 typed `RunOverrides/RunOptions`（`src/scalim/dsl/by_yaml/__init__.py`）。
- workflow 也提供稳定导入路径：`scalim.dsl.by_yaml.workflow`、`workflow_types`（re-export，避免用户依赖内部实现）。

#### YAML 配置与 Python API 的重复建模

重复建模最明显的三块：
1) **resources**：YAML `resources.*` 与 `RunOverrides.resources` 语义重叠，workflow 甚至把 YAML resources 转成 overrides 再 merge（`workflow_entrypoints.py`）。
2) **observability/viz**：YAML `observability.viz.*` 与 `RunOverrides.viz_config`/components 重叠。
3) **guardrails/retry/batch_size**：YAML 的 policy 与 `RunOptions.guardrails/loader_retry/batch_size` 重叠；CLI 还额外实现了条件校验（例如 retry.enabled 需要 should_retry）。

结论：当前体系呈现为“YAML 与 Python 两套控制面并存”，导致：
- 文档与推荐入口难统一（用户不知道该在 YAML 还是 Python 配）
- schema 与 runtime 更易漂移（两套实现都要维护）

#### 哪些配置更适合收敛到 typed Python API

优先下沉到 Python/CLI/profile 的候选：
- `observability.*`、`include_full_error_message`
- `guardrails.*`
- `retry.*`（含 `_templates.retry`、per-source retry）
- diagnostics/staging/wait 类 workflow options（更像运行时控制台）

#### 哪些用户材料在误导深层导入

docs/notebooks 多数已使用 facade；但 `packages/scalim-misc` 的 skill 生成器仍依赖内部模块：
- `scalim.dsl.by_yaml._internal.config_parsing.imports`
- `scalim.dsl.by_yaml._internal.config_parsing.validator`

建议：为“工具链/生成器”提供稳定的公开 helper（例如扩展 `scalim.dsl.by_yaml.tools`），逐步替换内部导入，减少对内部包结构的耦合。

### 5. 收敛建议（按优先级，可用于决策）

#### P0（先止血：漂移与校验失效）

1) **workflow `$import` 不一致修复**
   - 收敛面：`workflow.resources.*.$import`（schema 暴露） vs parser（不支持）
   - 方式：二选一（建议偏“删功能”以降复杂度）
     - A) **hide/remove-candidate**：workflow 侧明确不支持 `$import`，schema 删除/禁止；并在 docs/示例中统一口径
     - B) keep：为 workflow 引入与 demand 同级别的 imports expansion（成本高，且会扩大控制面）
   - 影响：schema validate/LSP 行为变化；可能 breaking（若已有用户依赖 workflow `$import`）。

2) **schema 数值类型洞补齐**
   - 收敛面：所有带 `minimum/maximum` 但缺 `type:number` 的字段（retry seconds / sampling_rate / score_by_rank base/step / count_true_gte.threshold 等）
   - 方式：simplify（补齐 type）+ 加 drift test
   - 影响：对“原本传了字符串/非法类型但 schema 放行”的 YAML 属于 breaking（但这是修 bug）。

3) **retry.enabled + should_retry 组合语义收敛**
   - 收敛面：`retry.enabled/should_retry` 在 demand/main_source/sources 三处重复
   - 方式：move-to-python（推荐）或至少 simplify（删除 enabled，presence 即启用；should_retry 改为必填或改为标准 policy id）
   - 影响：breaking（现有 YAML 需要迁移）。

#### P1（大头降复杂度：把控制面从 YAML 拿掉）

4) **observability 下沉**
   - 收敛面：`observability.*`（70 路径）
   - 方式：move-to-python + hide（YAML 不再直接配置；通过 `RunOptions.components` / `RunOverrides.viz_config` / CLI flags 控制）
   - 用户影响：调试型 YAML 需要迁移为运行入口参数；breaking 候选（但收益巨大）。

5) **guardrails 下沉**
   - 收敛面：`guardrails.*`
   - 方式：move-to-python（`RunOptions.guardrails`）+ profile（可选，为 YAML-only 场景提供有限 preset）
   - 影响：breaking（YAML 写法迁移）。

6) **写策略 SSOT 化（write_defaults vs output.write）**
   - 收敛面：`resources.books.*.write_defaults` 与 `outputs[*].write`
   - 方式：merge（确定单一 SSOT：资源级 defaults；输出级只允许少量 override）
   - 影响：可能 breaking（某些 output.write 字段迁移到资源 defaults 或 overrides）。

7) **meta/audit 合并**
   - 收敛面：`meta` + `audit`
   - 方式：merge（例如 `extras: {meta: ..., audit: ...}`）或 move-to-python（统一由 driver 开启）
   - 影响：轻度 breaking；但减少重复与文档负担。

#### P2（结构性长期收益，但实现量较大）

8) **main_source 与 sources 关系重构（去重）**
   - 收敛面：`main_source.*` 与 `sources.*` 的重复字段/语义
   - 方式：simplify（main_source 只引用 source_id；把 main_source.fields/params 等合并到 sources）
   - 影响：breaking 较大，但能显著减少 schema 与 parser 的重复面。

9) **imports/$import 范围收敛**
   - 收敛面：92 条 `$import` 路径（观测/资源/输出/护栏/重试等）
   - 方式：simplify（只保留少数稳定节点，或引入 profile/preset 取代）
   - 影响：breaking（但长期收益：减少 overlay 语义扩散）。

### 6. Top candidates

**Top 10 最值得收敛/移除/下沉（按综合收益排序）**
1) `observability.*`（move-to-python, hide）
2) `guardrails.*`（move-to-python）
3) `retry.*` + `main_source.retry` + `sources.*.retry`（move-to-python；删除 enabled/模板）
4) `_templates.retry.*`（remove-candidate）
5) workflow `workflow.resources.*.$import`（hide/remove-candidate 或补齐实现二选一；建议 hide）
6) demand 全域 `$import`（简化范围；减少可替代入口）
7) `resources.books.*.{allow_formulas,write_lock,export_xlsx,...}`（收敛为更少治理入口/默认安全）
8) `resources.books.*.write_defaults` vs `outputs[*].write`（合并 SSOT）
9) `meta` + `audit`（merge）
10) `include_full_error_message` / `validate_unique_field_names`（move-to-python 或 hide 并强制默认）

**Top 5 最值得强化或保留（并说明原因）**
1) `sources` / `main_source`（核心建模：数据入口与键策略是 DSL 基础）
2) `fields`（核心建模：派生字段是 DSL 的表达核心）
3) `relations`（核心建模：跨源关联是该 DSL 的差异化能力）
4) `outputs`（核心建模：输出编排是 DSL 的主要交付物；但建议简化 write 与 policy 面）
5) `workflow.runs[*]` + `depends_on` + `init_vars`（workflow 的 declarative DAG 编排价值明确，应保持清晰与稳定）

---

## Decisions

### Decision 1: YAML vNext 组织原则采用 KV-first（list 仅用于顺序语义）

**选择**：KV-first。
- mapping 用于：需要稳定 ID/引用/复用的结构（sources/fields/relations/resources）
- list 用于：顺序语义不可替代或允许重复的结构（outputs、relation.steps、workflow.runs）

**理由**：KV-first 更利于 diff/merge、引用稳定性与 schema 表达；并减少“列表项缺少稳定标识”带来的维护负担。

### Decision 2: 以 “YAML=建模；Python/CLI=策略” 作为长期边界（控制面下沉）

**选择**：把运行时策略（retry/guardrails/observability/diagnostics 等）从 demand YAML 收敛到 `RunOptions/RunOverrides` 与 CLI/profile。

**理由**：
- 运行时策略与环境/组织治理绑定，写进可复用 YAML 会造成复制扩散与跨环境不一致。
- 当前已存在 typed Python 契约（`RunOptions/RunOverrides`），继续在 YAML 上增加同类配置只会导致重复建模与漂移。

### Decision 3: workflow 侧不扩张 `$import`（先对齐/收敛，再决定是否实现）

**选择（建议）**：workflow schema 删除/禁止 `$import`（与 runtime 一致），以降低控制面扩张。

**替代方案**：为 workflow 引入 imports expansion 与统一 overlay 规则（成本高；会扩大长期维护面）。

### Decision 4: 写策略 SSOT 统一到资源 defaults；输出仅允许最小 override

**选择**：以 `resources.books.*.write_defaults` 为 SSOT；`outputs[*].write` 仅保留少量与“输出本体”强相关的 override（例如 sheet 模式/表头）。

**理由**：减少同语义多处可配，降低组合爆炸；并更贴近“资源级”策略（工作簿写策略通常跨 outputs 复用）。

### Decision 5: 文档/生成边界与 drift gate

**SSOT/生成物边界（必须明确）**：
- schema 生成 SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`
- 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（禁止手改）
- docs 注入块：`docs/**` 内 `BEGIN/END AUTOGEN:*`（禁止手改区块内部；用 `just gen-docs`）

**drift gate（建议新增/强化）**：
- schema vs runtime：对 workflow 资源与关键枚举/默认值做一致性自检（类似 `tests/test_yaml_schema_generation.py` 的 drift 方式扩展到 workflow parser）。
- schema typing：对带数值约束字段强制要求 `type:number`（生成期/测试期 fail-fast）。

## Risks / Trade-offs

- [破坏性迁移] → 提供 vNext 并行、CLI upgrade、lint/compat、清晰 deprecation 时间线。
- [高级用户能力“看似减少”] → 通过 typed Python API/profile 保留能力，但不再鼓励写进 YAML。
- [imports 收敛可能影响现有复用方式] → 提供 profile/preset 替代路径；并限制 `$import` 范围而非一刀切。

## Migration Plan

1) P0 止血：先对齐 workflow schema/runtime、补齐 schema 数值类型洞、修复 retry 组合语义（并加 drift tests）。
2) 引入 vNext schema + parser（并行）：提供 `--dsl-version` 或显式 schema 路径选择；默认仍为 v1。
3) 迁移工具：`scalim-cli yaml-dsl upgrade --to vnext` + `render effective`（输出不含 imports 的最终 YAML）。
4) Deprecation：v1 的 policy/observability keys 发出告警并从 docs 示例移除；最终移除。

## Open Questions

- vNext 的版本选择机制：显式 `dsl_version` 字段 vs CLI/schema 路径选择 vs 通过 modeline 推断？
- 对 imports/$import 的最终策略：限定范围 vs profile/preset 全替代？
- 是否要为 workflow 引入 imports expansion（若下游强需求）？

