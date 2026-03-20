# 核心框架全面扫描：YAML DSL 字段/特性膨胀治理与收敛计划（仅文档）

日期：2026-03-20

> 本文档是一次“统一认知”的扫描与治理提案：**不包含任何代码改动**，也不接入 OpenSpec 工件流程。
> 后续若要落地（真正改 schema/validator/runtime/editor/docs），应另起变更并按本文的门禁与验收清单执行。

## 0. 读者与结论先行

**适用读者**

- YAML DSL 使用方（写配置的人）：需要知道“哪些东西该写在 YAML、哪些不要写”、以及为什么要收敛。
- 集成/平台方（把 YAML 跑进生产的人）：需要更稳定的边界、更少 footgun、更可控的运行时参数入口。
- 库维护者/贡献者（加字段、改语义的人）：需要统一的“新增门禁”，避免持续膨胀与漂移。
- 工具链维护者（编辑器/文档/校验器）：需要 schema/validator/docs 的单一事实来源（SSOT）和可预测的演进方式。

**一句话结论**

YAML DSL 的膨胀不是“字段太多”本身，而是 **意图边界不清 + 多入口同义 + schema/validator/runtime/editor/docs 的漂移成本**。治理的核心是把 YAML authoring surface 收敛为“需求本体”，把“环境/执行装配/调参”迁回 Python/CLI，同时建立强门禁：新增能力必须交付 SSOT、语义边界、回归与文档，并且要“付出复杂度税”（能删/能合并/能关）。

---

## 1. Why Now：我们到底在解决什么

### 1.1 从使用方视角（用户角度）

典型痛点模式：

- **读不懂意图**：同一个意图可能存在多个写法（或被误用的写法），靠约定而不是结构表达（例如把 `where` 当 enabled 开关）。
- **写不出“最小正确”**：为了跑通，不得不理解太多“执行装配细节”（输出、并发、可观测性、workflow 写入等）。
- **排错成本高**：schema 能过但运行时失败；或 validator 报错但编辑器补全无法引导到正确写法。
- **迁移心智负担**：同域能力不断加法，旧写法虽然被拒绝了，但迁移入口不统一、认知不统一。

用户侧理想状态：

- YAML 读起来像“需求说明书”，不是“脚本/调参集合”。
- 最常用 80% 场景只需要掌握很小的稳定 surface；高级能力有清晰的分层与入口。

### 1.2 从库维护者视角（维护者角度）

典型成本来源：

- **SSOT 分裂**：schema（结构）/ validator（语义）/ runtime（编译与执行）/ editor（schema blocks + exact）/ docs（参考与升级）五处都要同步。
- **新增没有删除**：每次“补齐边角需求”都新增一个字段/分支语义，导致整体复杂度单调上升。
- **同域耦合过深**：尤其是 `outputs` 与 `observability`，既是用户 surface，又强耦合执行层内部结构。

维护侧理想状态：

- 新增能力必须能被“系统性地审查”：它属于需求本体还是运行环境？它是否能用 anchors/imports 表达而不新增语法？是否会引入 schema/validator 分裂？
- 每次新增都必须带来“可证明的复杂度下降”（删掉旧入口/合并旧语义/减少漂移点）。

### 1.3 从工具链视角（编辑器/文档）

典型漂移：

- schema hover 文案与 docs 不一致；或者 validator 的错误建议与 editor 的补全路径不一致。
- 前端 schema 复制（`just gen-yaml-dsl-editor-schema`）与后端 schema 生成（`just gen-yaml-dsl-schema`）需要稳定且可维护的演进模型。

工具链理想状态：

- “字段解释/hover 文案”尽可能集中维护（减少多处手写）。
- schema 的结构变化可控、可预测、可分层（基础/高级/专家），避免 editor UI 被频繁打爆。

---

## 2. 环境事实（本仓库内的 SSOT 与入口）

> 本节只列事实锚点：后续任何治理讨论都以这些入口对齐，不再靠“口口相传”。

### 2.1 端到端分层（核心框架视角）

架构分层与主链路说明：

- `ARCH.md`：分层总览、从 YAML 到执行的关键边界。
- `docs/doc/getting-started/reading-guide.md`：从入口文件一路跟到执行结果的阅读路径。

YAML → 执行的关键入口（用于定位“某字段影响哪里”）：

- YAML 入口：`src/scalim/dsl/by_yaml/runtime/entrypoints.py`（`run/compile`）
- YAML 加载/校验：`src/scalim/dsl/by_yaml/config_parsing/loader.py`（`YamlDemandLoader`）
- 语义校验：`src/scalim/dsl/by_yaml/config_parsing/validator.py`（`ConfigValidator`）
- YAML → IR/Request：`src/scalim/dsl/by_yaml/runtime/compiler.py`、`src/scalim/dsl/by_yaml/runtime/conversion.py`
- 执行装配：`src/scalim/execution/run_ir.py`、`src/scalim/execution/output_composition.py`

### 2.2 YAML DSL 的“事实来源”

结构/类型（schema-only）：

- SSOT：`src/scalim/dsl/by_yaml/schema_dsl/models/*.py`（dataclass + 元数据）
- 生成物：`src/scalim/dsl/by_yaml/schema/demand.gen.json`、`src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- 生成入口：`just gen-yaml-dsl-schema`

语义（validator）：

- `scalim-cli yaml-dsl validate ...`（内部 validator，含 unknown fields / 语义约束）
- 代码：`src/scalim/dsl/by_yaml/config_parsing/validator.py` + `validators/`

编辑器（schema 驱动 + 可选 exact）：

- 文档：`docs/doc/yaml-dsl/editor.md`
- schema 同步：`just gen-yaml-dsl-editor-schema` → `frontend/scalim-yaml-dsl-editor/public/schema/*.gen.json`

文档参考（字段集合与 required 边界）：

- 生成参考：`docs/doc/yaml-dsl/schema-reference.gen.md`（来源：`src/scalim/dsl/by_yaml/schema/*.gen.json`）
- 能力边界/映射：`docs/doc/yaml-dsl/capability-matrix.md`
- 升级指南：`docs/doc/yaml-dsl/upgrades/`（由 `artifacts/skills/scalim-yaml-dsl/references/upgrades/` 生成）

### 2.3 示例 SSOT（Marimo notebooks / 对拍）

- Canonical demo（YAML DSL SSOT）：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- Workflow demo：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`（配套 demand YAML 在同目录）
- 示例运行/对拍（集成冒烟）：`just examples`（调用 `notebooks/marimo/run_examples.py`）
- 治理要求（从现在开始按 SSOT 对待）：任何 YAML DSL 变更都必须同步更新该示例套件，并保证 `just examples` 通过；示例不必强行塞进单一 YAML，可按“域/能力”拆分多个 YAML 来避免单文件爆炸

---

## 3. System Surface Map：我们拥有哪些 surface（按“意图域”分组）

> 目的不是穷举字段细节，而是把“域”与“边界”说清楚：哪些属于需求本体，哪些属于执行装配，哪些只是 authoring convenience。

### 3.1 Demand YAML（需求本体 + 少量执行请求）

**需求本体（应稳定）**

- 数据源：`main_source` / `sources` / `relations`
- 字段：源字段（`*.fields`）与派生字段（顶层 `fields`）
- 复用：YAML anchors/alias、`_templates`、`imports/$import`（编译期展开）

**执行请求（应克制，且边界要写死）**

- 输出编排：`outputs` / `meta` / `audit` / `failure_policy` / `include_full_error_message`
- 可观测性：`observability`
- 护栏：`guardrails`
- 批次：`batch_size`
- retry：`retry`（注意它是“执行策略”，但作为常用刚需已进入 YAML）

### 3.2 Workflow YAML（编排本体）

workflow 只负责“编排多 demand + 共享资源 + DAG ctx”：

- `workflow.runs`：`id/demand/depends_on/init_vars/writes`
- `workflow.options`：`max_concurrency/failure_policy/cache_pool/ctx`
- `workflow.resources`：`workbooks/csvs/sheetbooks`

关键边界（必须长期保持一致）：

- workflow YAML **只有 schema-only 校验**（没有 internal validator）。
- `$ctx` 是对象指令节点（compile-on-ready 物化），不是字符串插值。

### 3.3 CLI 与库 API（不要被 YAML 吸走的运行环境参数）

长期默认策略：

- allowlist/安全边界：`allowed_modules/allowed_functions`（必须由调用方/环境提供）
- 并行模式/并发资源：`parallel_mode/max_workers`（环境敏感，默认不进 YAML）
- 自定义 hooks/observers/components：Python 对象注入（不进 YAML）

**原则**：当某能力明显依赖运行环境/组织策略/资源上限时，默认不进 YAML；若必须进，也要提供“最小稳定子集”，并把其余入口留在 Python overrides。

---

## 4. Heatmap：膨胀热点与典型“膨胀机制”

> 我们不只看“字段数”，更看“新增会导致多少处同步与多少种歧义”。

### 4.1 热点一：`outputs`（高耦合 + 高表达力）

症状：

- 同域同时承担：布局、容器、路由、聚合、复用、失败策略、脱敏、workflow 托管临时输出等。
- 容易出现“语义误用”：例如把 `where` 当启用开关，或把复用当继承语义。
- validator 与 schema 都参与约束，且与 execution/output_composition 强耦合。

膨胀机制：

- 为了解决一个局部 case（例如“临时禁用输出/占位”），往往会选择在现有字段上叠加语义，而不是引入清晰的结构字段（导致歧义长期存在）。

### 4.2 热点二：`observability`（选项散落 + 结构不完全同构）

症状：

- 子域很多（logging/performance/relations/viz/trace/row_gap/memory_opt…），默认值与启用逻辑容易分裂。
- 部分字段属于“调参/环境策略”（更适合 Python/CLI），但被写进 YAML 会导致不可复现、难治理。

膨胀机制：

- “为了可用性”不断给每个子域补参数，最终 YAML 变成运行时控制面板。

### 4.3 热点三：复用与导入（anchors / `_templates` / `imports/$import`）

症状：

- 复用路径多，用户不知道应该用哪种；同时错误定位（import 来源）如果不强，会逼迫用户回退到复制粘贴，形成“配置膨胀”。

膨胀机制：

- 复用能力不足/排错不友好 → 用户复制粘贴 → 需求变更时需要更多“语法糖/字段”来减轻痛苦 → surface 继续膨胀。

### 4.4 热点四：安全边界（compute/call_by/allowlist）

症状：

- 任何“让 compute 更强”都在把 DSL 推向脚本语言；安全边界与审计复杂度会指数上升。

膨胀机制：

- 为了少写 Python glue，不断扩大表达式能力；最终把安全问题与运行时不可控引入 DSL。

---

## 5. 收敛原则（统一认知的“规则”）

> 这一节是治理的核心：以后讨论“要不要加一个字段”，先过这些规则。

### 5.1 分类裁决：这项能力应该放在哪里？

把任何新增诉求强制分到以下类别之一（类别决定入口与门禁强度）：

1) **需求本体（YAML/IR）**：描述数据源/字段/关系/输出语义本身；应稳定、可迁移、可回放、可对拍。
2) **执行请求（YAML/ExecutionRequest）**：影响执行策略但与需求强相关且高度通用（例如 retry、基础 guardrails、基础 observability）；必须“最小稳定子集”。
3) **运行环境参数（Python/CLI）**：与机器资源/并发/组织策略/安全策略强相关（例如 allowlist、并发上限、组件注入）；默认不进 YAML。
4) **authoring convenience（优先用 YAML 语法能力）**：能用 anchors/imports/模板解决的，不新增 DSL 字段；避免语法糖堆叠。

**默认判决**：只要它属于 (3)，就拒绝进 YAML；只要它属于 (4)，就优先拒绝新增字段。

### 5.2 一意图一入口（禁止同义/隐式复用）

- **同一意图必须只有一个结构字段表达**：不要依赖约定写法（如 `where: "False"`）来表达“禁用”。
- **字段名要表达语义**：`where` 永远是 row-level predicate/router；启用开关必须显式字段。
- **继承/复用规则必须极少且确定**：例如 `from` 的继承范围要写死；禁止出现多种等价写法同时存在。

### 5.3 新增必须“付复杂度税”（减法优先）

新增任何 YAML 能力，必须同时交付至少一项“复杂度下降”的对冲：

- 删除旧入口/旧别名/旧语义分支；或
- 合并重复配置形态为一个同构结构；或
- 将一组环境调参迁回 Python overrides；或
- 把 validator 的特判收敛进 schema（或反过来：明确“validator 为准”，并减少 schema 花活）。

### 5.4 SSOT 与漂移门禁（交付物完整性）

任何新增/变更（未来真正落地时）必须在同一个变更内完成：

- schema SSOT（`schema_dsl/models`）+ schema 生成物 + schema drift 门禁通过
- validator 语义与错误提示（含 suggestions）
- docs：`schema-reference` / `capability-matrix` / `upgrades` 同步
- editor：schema 同步 +（如涉及）exact 语义校验对齐说明
- 至少 1 个 fixture/测试覆盖该能力的典型路径（避免“文档写对了实现漂”）
- marimo 示例 SSOT 同步更新，`just examples` 对拍通过（`notebooks/marimo/demo_big_data_report/by_yaml_dsl/`）

> 说明：本文档不做这些实现，只把门禁固定下来。

### 5.5 安全边界不可滑坡（compute 不演进为脚本）

- `compute` 继续保持“安全表达式”定位：不引入属性访问/下标/任意调用等会扩大攻击面的能力。
- 复杂逻辑统一走 `call_by` + allowlist（且 allowlist 永远由环境提供，不写死在 YAML）。

### 5.6 LSP-First（schema/补全优先，validator 兜底）

- 设计目标是让“写 YAML”主要靠 JSON Schema（YAML LSP）即可完成：结构约束、枚举、默认值、示例、补全路径尽量在 schema 表达。
- 尽量避免把“可结构表达”的约束留给 runtime/validator 特判；若必须 validator-only，必须在 hover/docs 明确，并保证错误信息可定位到具体节点。
- `aggregate` 保持“聚合函数名作为 key”的 producer 形态（如 `{sum: {field: amount}}`），以获得定向补全与参数提示；避免退化为泛化 `kind: sum` 结构，除非证实对 LSP 更好。
- 对于同名 key 在不同分支含义不同（例如 detail `fields: [..]` vs aggregate `fields: {..}`），短期优先通过 schema `oneOf` 分支/required keys 提升 LSP 判别；若仍不可控，再考虑显式 discriminator（但这属于结构性改造，见第 14 节停车场）。

---

## 6. 分域收敛路线图（方向性，不落地实现）

> 每个域都按同一模板表达：**问题形状 → 目标形状 → 禁止事项 → 下一步切片建议**。

### 6.1 Outputs：把“输出编排”收敛成可读、可验、可演进的最小模型

**问题形状**

- 输出域承载太多概念（容器/布局/路由/聚合/复用/禁用/失败策略/脱敏/临时输出）。
- 容易产生语义误用（`where` 被当开关、复用规则不清等）。

**目标形状（统一认知）**

- （可选）`enabled`：静态开关（避免把 `where` 当开关；若不引入，也必须在 schema/hover 中把误用写死）
- `where`：只做行级路由谓词（永远不承担开关语义）
- `container`：物理承载（workbook/csv），对 workflow-managed 临时输出的特殊形态要“明确标注为仅 workflow 可用”
- `fields` vs `aggregate`：二选一且结构清晰（避免出现混合语义）
- `aggregate.fields` 中每一列的 producer 继续采用“函数名作为 key”的形态（LSP 定向补全友好），并把 `call_by/compute` 明确为高级口子治理（不持续膨胀）
- `from`：继承范围固定、禁止层层继承带来的隐式复杂度

**禁止事项**

- 不再给 `where` 叠加任何“启用/禁用/占位”的语义。
- 不新增新的“快捷 sugar”来绕过结构（优先用 anchors/imports 复用）。

**下一步切片建议（未来落地时）**

- 先收敛语义与文档：明确每个字段的职责边界与反例；把误用写进 upgrades 与 hover。
- 再做结构性减法：把确认为“环境/装配”的配置迁回 Python overrides。

### 6.2 Observability：把“可观测性配置”从控制面板收敛成最小稳定子集

**问题形状**

- 子域多且启用/默认值/输出形态不完全同构；新增一个子域经常带来 schema/validator/editor/docs 多处同步。

**目标形状**

- 每个子域统一成同构结构：`enabled + report + thresholds`（有则有、无则无），避免特殊分支。
- “环境相关调参”迁回 Python overrides：YAML 只保留稳定、可复现、可对拍的最小入口。

**禁止事项**

- 不把“性能调参/并发策略/组件注入”等环境控制项写进 YAML。

### 6.3 Workflow：只做编排，不吞 demand 语义

**问题形状**

- workflow 同时涉及 DAG、ctx、共享缓存、共享输出资源与 writes；任何新增都可能与 demand outputs 概念冲突。

**目标形状**

- workflow 只负责：
  - runs DAG 与并发/失败策略
  - 小体量 ctx 传递（有护栏）
  - 共享资源声明与确定性的写入意图
- 与 demand 的契约固定为：demand 产出 outputs（通常 csv），workflow 消费它写入共享资源。

**禁止事项**

- 不在 workflow 里新增 demand 级别的语义快捷入口（否则会产生两套 DSL）。

### 6.4 Reuse（anchors / imports / templates）：减少“为了复用而新增字段”的诱因

**目标形状**

- 复用优先级写死并在文档中反复强化：
  1) YAML anchors/alias（最稳）
  2) `_templates`（只作为 anchors 容器，语义极少）
  3) `imports/$import`（编译期展开；错误定位必须可读）
  4) 框架自定义语法糖（默认禁止新增）

### 6.5 Security：DSL 不变成脚本语言

**目标形状**

- 继续坚持：YAML 表达需求；Python 表达复杂逻辑；allowlist 由环境给出。

---

## 7. 治理门禁（以后任何“加字段/加特性”的必经流程）

> 本节是“拒绝膨胀”的操作化版本：不给门禁，再好的原则都会被需求压力冲垮。

### 7.1 新增/变更前的三问（必须写在 PR/变更说明里）

1) 这项能力属于 **需求本体 / 执行请求 / 运行环境参数 / authoring convenience** 哪一类？为什么？
2) 是否能用 **anchors/imports** 解决而不新增字段？如果不能，阻碍是什么（表达力/排错/可发现性）？
3) 本次新增带来的“复杂度税”怎么支付？（删/合并/迁回 Python/减少漂移点）

### 7.2 交付物清单（未来落地时的必须项）

- schema SSOT + 生成物 + drift 门禁
- validator 语义校验 + 错误建议 + 与 editor/issues 对齐
- docs：schema reference + capability matrix + upgrades（breaking 必须写迁移清单）
- editor：schema 同步；若影响 exact，必须说明 exact 与 validate 的一致性边界
- tests/fixtures：至少 1 个覆盖样例
- marimo 示例 SSOT 同步更新，`just examples` 对拍通过（`notebooks/marimo/demo_big_data_report/by_yaml_dsl/`）

---

## 8. 验收清单（未来动代码时怎么验：只列清单，不执行）

建议的最小验收门禁（按仓库 just 入口）：

- schema/文档/规范一致性：
  - `just schema-drift-check`
  - `just doc-governance-check`
  - `just docs-drift-check`
- Python 质量门禁：
  - `just quick-check-only-py`（快速）
  - `just check`（全量）
- 前端编辑器门禁（若改到 schema blocks 或 schema 结构）：
  - `just frontend-yaml-dsl-editor-check`
- 示例对拍（集成冒烟）：
  - `just examples`

---

## 9. 本文档的范围声明

- ✅ 做：统一认知、确定原则、给出收敛路线图与治理门禁、列出未来验收清单。
- ❌ 不做：任何代码修改、任何 schema 生成物更新、任何自动升级脚本、任何 OpenSpec 工件接入。

---

## 10. 预研快照（基于仓库现状的“事实证据”）

> 本节把“我们直觉上觉得膨胀”的东西，用可验证的仓库事实固定下来：体量、结构复杂度、耦合面、近期 churn。
> 这不是为了 KPI，而是为了后续做取舍时不靠拍脑袋。

### 10.1 YAML surface 的客观规模（Schema 维度）

**Demand schema（`src/scalim/dsl/by_yaml/schema/demand.gen.json`）**

- 顶层 properties：18 个（`name/imports/$import/_templates/.../observability`）
- definitions：25 个（`source/field/output_* /observability/* /guardrails/* /loader_retry/...`）
- 结构复杂度（粗略统计）：`oneOf=53`、`anyOf=43`、`$ref=30`（union 与组合结构很多，强依赖 editor 的 union 推断与 hover 文案）
- 全量 property-path（含 definitions）约：264 条

**Workflow schema（`src/scalim/dsl/by_yaml/schema/workflow.gen.json`）**

- 顶层 properties：1 个（`workflow`）
- definitions：0 个（workflow schema 目前是“内联大对象”）
- 全量 property-path 约：63 条（其中 `writes` 为 5-way `oneOf` union）

**定义复杂度贡献（按 demand property-path 粗略计数，越大越可能是“认知/实现热点”）**

- `definitions.output_aggregate`：62
- `definitions.source`：36
- `(root)`：21
- `definitions.field`：14
- `definitions.viz`：12
- `definitions.output_container`：11

结论（用于后续优先级裁决）：

- 仅看 schema 结构复杂度：**output_aggregate**（聚合输出）是最大热点；其次是 **source/normalize**；然后才是顶层键数量。
- workflow 的复杂度不在 keys 多，而在 union（writes）+ 资源/并发/ctx 等“编排控制面”的语义密度。

### 10.2 实现热点（LOC + 责任分布）

> 体量不是问题本身，但它是“哪里最容易继续膨胀、最容易引入漂移”的信号。

**Schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/models/`）**

- `outputs.py`：约 1092 行（聚合/排名/post fields/文案集中）
- `observability.py`：约 486 行
- `source.py`：约 397 行

**Config parsing（`src/scalim/dsl/by_yaml/config_parsing/`）**

- parsers：
  - `parsers/outputs.py`：约 1141 行（outputs 的主要语义/校验/依赖提取都在这里）
  - `parsers/sources.py`：约 304 行
  - `parsers/fields.py`：约 283 行
- validators：
  - `validators/sources.py`：约 867 行（source 语义/约束非常密集）

**Runtime（`src/scalim/dsl/by_yaml/runtime/`）**

- `workflow_entrypoints.py`：约 1632 行
- `workflow_resources.py`：约 1203 行
- `output_composition_yaml.py`：约 592 行（YAML outputs → execution spec 的“第二语义层”）
- `_internal/conversion_sources.py`：约 587 行

**Workflow config（`src/scalim/dsl/by_yaml/workflow.py`）**

- `workflow.py`：约 1148 行（workflow YAML 的加载/语义校验/错误定位也很重）

结论：

- “膨胀热点”不是抽象概念，**outputs / workflow / sources** 在 schema + parsing + runtime 三层都有明显的高体量与高耦合。

### 10.3 关键耦合面（一个域的改动会波及哪些层）

> 后续每个“收敛切片”必须显式列出这些触点，否则容易只改到 1-2 层导致漂移。

**outputs（demand）**

- schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`
- parsing/语义：`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
- runtime 编译：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
- execution：`src/scalim/execution/output_composition.py` + sinks（workbook/csv）
- docs：`docs/doc/yaml-dsl/syntax.md`、`docs/doc/yaml-dsl/user-guide.md`、`docs/doc/yaml-dsl/upgrades/*outputs*.gen.md`、`docs/doc/yaml-dsl/schema-reference.gen.md`
- editor：schema 同步（`just gen-yaml-dsl-editor-schema`）+ schema blocks（union 推断依赖 `oneOf` 结构稳定）
- tests：`tests/test_yaml_loader_outputs.py`、`tests/test_yaml_dsl_fields_and_output.py` 等（未来落地需补齐聚合/禁用/继承等组合覆盖）

**workflow**

- schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/builder.py::build_workflow_schema`（注意：**不是 dataclass 驱动**）
- parsing/语义：`src/scalim/dsl/by_yaml/workflow.py`（包含大量语义校验）
- runtime：`src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`、`workflow_resources.py`
- docs：`docs/doc/yaml-dsl/workflow.md`、`docs/doc/yaml-dsl/upgrades/2026-03-18-yaml-workflow-dag-ctx-resources.gen.md`
- editor：同上（workflow schema 同步 + union blocks）
- tests：`tests/test_yaml_dsl_workflow.py`、`tests/test_workflow_config_validation_coverage.py`

**sources/normalize/params**

- schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/models/source.py` + `schema_dsl/constants.py`（normalize/enum/hover）
- parsing：`src/scalim/dsl/by_yaml/config_parsing/parsers/sources.py`
- validator：`src/scalim/dsl/by_yaml/config_parsing/validators/sources.py`
- runtime conversion：`src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- docs/upgrades：`*normalize*`、`*params-template*`、`*field-extract*`

### 10.4 近期 churn 信号（“我们为什么总在加字段”的证据）

最近的 YAML DSL upgrades（`docs/doc/yaml-dsl/upgrades/*.gen.md`）在 2026-03-10 ~ 2026-03-18 期间共有 11 个条目，其中：

- outputs：3
- workflow：2
- normalize：2
- 其余（extract/params/breaking/derived-outputs…）：4

结论：

- outputs 与 workflow 是近期迭代最密集的域；这通常意味着“认知未收敛”，继续加法会进一步放大漂移成本。

### 10.5 规范漂移风险（仅作为治理提示）

仓库内 OpenSpec specs 作为“约束性描述”存在，但部分 spec 与当前实现/文档已经出现明显漂移迹象（例如历史上以 `output` 为中心的描述与现行 `outputs` surface 不一致，relation 引用规则也经历过收敛）。

治理建议（不等于立即接入 OpenSpec 流程）：

- 后续真正落地收敛时，要么同步更新相关 spec，要么明确“spec 仅作参考，不作为 SSOT”，避免团队在争议点上失去共同裁判。

---

## 11. 更可执行的“收敛推进路线图”（预研版）

> 目标：把第 6 节的方向性路线图，收敛成“可切片、可验收、可并行”的推进顺序。
> 注意：这里仍然只做规划，不落地实现。

### 11.1 Phase 0：建立治理基线（先止血）

产出/动作（仍是文档/流程层）：

- 以 `demand.gen.json` / `workflow.gen.json` 为准，固化一份“域 → keys → 语义归属（DemandIr/ExecutionRequest/validator-only）→ 触点清单”的表（可直接内嵌在本文件或单独表格）。
- 把 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 固化为“YAML DSL 能力展示 SSOT 套件”：维护 capability coverage matrix（schema key/definition → 覆盖 YAML/章节），并把 `just examples` 作为对拍门禁。
- 明确“新增必须付复杂度税”的执行方式：PR 模板/Review Checklist（可复用第 7 节三问 + 交付物清单）。
- 明确“什么不进 YAML”：allowlist/并发/组件注入/调参类控制面（第 3.3 与第 5.1 作为默认裁决）。

验收标准：

- 新增任何 YAML 能力前，评审能快速回答：它属于哪类、为什么不能用 anchors/imports、复杂度税怎么付。

### 11.2 Phase 1：outputs 收敛（先解决最大误用与最大结构复杂度）

优先目标（收敛语义）：

- 先止损 `where` 误用：在 schema/hover/docs/upgrades 中明确 `where` 只能是行级谓词；必要时再引入显式静态开关（如 `enabled`），避免把开关语义塞进 `where`。
- 明确 `from` 的继承边界（只继承哪些字段，不继承哪些字段），并减少隐式规则。
- 对 `aggregate.fields` 的生产者 union 做分层（保持“聚合函数名作为 key”的 producer 形态）：
  - **core stable**：最常用且可强补全的 producer（count/sum/min/max 等）
  - **advanced/escape hatch**：`call_by/compute` 这类“强表达力但高漂移/高安全/高审计成本”的入口，明确为高级口子并限制其文档与 editor 展示层级

预研结论（为何这么排）：

- schema 结构复杂度最大的是 `output_aggregate`，而实现层面 outputs parsing/runtime 也都极重；先收敛 outputs 能最大化降低后续继续膨胀的边际成本。

### 11.3 Phase 2：sources/normalize/params 收敛（减少“为了形状适配而加字段”的压力）

优先目标：

- 明确 “normalize 是 whole-result reshape，extract 是 field-level 取值” 的边界，避免两者语义重叠继续扩张。
- 对 normalize kinds/steps 做“少而清晰”的收敛：宁可减少一种 fancy step，也不要保留多种等价形态。
- 对 params 模板（`$keys/$rows/$init_var`）的语义边界写死：哪些场景允许、哪些场景必须 fail-fast、错误信息必须给出可复制替代片段。

### 11.4 Phase 3：workflow 收敛（对齐 outputs 与资源/写入模型）

优先目标：

- 固化 demand outputs 与 workflow writes 的契约：哪个产物可被 writes 消费、何时允许 pathless 输出、错误信息如何引导。
- 统一资源命名/冲突策略/写入确定性（避免“资源层再引入另一套 outputs 语义”）。
- 评估 workflow schema 的 SSOT 形态：当前 workflow schema 在 `SchemaBuilder` 内联维护，未来是否需要迁移为 dataclass-driven（以降低 schema/实现重复成本）。

### 11.5 Phase 4：observability 收敛（把控制面做薄）

优先目标：

- 子域结构同构化（enabled/report/thresholds），减少 special cases。
- 明确哪些“调参/环境策略”迁回 Python overrides（YAML 只保留最小稳定子集）。

---

## 12. 下一步需要你拍板的 3 个高影响决策（建议默认值已给出）

> 下面 3 个点不先对齐，后续很容易陷入“每个需求都能加字段”的无底洞。

1) **outputs.aggregate 的定位**：它是长期 stable surface，还是明确为“高级/实验性面”？
   - 建议默认：核心聚合能力 stable；`call_by/compute` 作为高级口子并限制展示与扩展（避免持续膨胀）。
> 最新反馈：这个能力我们一定要有；`outputs` 里出现 `fields` 概念本身没问题，主要问题是当前 schema 设计整体不够一致。你希望尽可能靠 YAML LSP 的 schema 校验/补全来治理，并且 aggregate 继续保持“聚合函数名作为 key”的形态；当前阶段不推进大的 YAML 结构性重设计。

2) **workflow schema 的 SSOT 形态**：是否要中期迁移为 dataclass-driven（对齐 demand 的 schema 生成治理），还是继续接受内联 schema？
   - 建议默认：先不动 SSOT 形态，先收敛语义与契约；当 workflow 继续扩张时再迁移（避免一次性大工程）。
> 你指的“并行池子/调度参数”主要是在 `workflow.options` 这块（如 `max_concurrency/failure_policy/ctx/cache_pool/...`），不是 demand 内部执行的 `parallel_mode/max_workers`。workflow 结构未来可能仍需重构，但你更希望先把 options 的语义/默认值/边界与 schema/LSP 体验梳理清楚。
   
3) **OpenSpec 的裁判地位**：未来落地收敛时，spec 是否必须同步（作为约束性 SSOT），还是允许“实现+docs”为先，spec 慢补？
   - 建议默认：对关键边界（安全/执行确定性/输出契约）要求 spec 同步；其余允许滞后但必须明确标注，避免口径冲突。
> 你的策略：不要求硬同步；必要时可以从具体实现反向重写 spec。

---

## 13. 决策记录与下一步预研方向（基于你的反馈）

> 这节把你对第 12 节的反馈固化成“决策记录 + 可执行的预研拆解”，用于指导后续真正的重构切片。

### 13.1 outputs.aggregate：能力必须有；短期以“schema 一致性 + LSP 友好”治理膨胀（不做大 YAML 改造）

你最新反馈的关键点：

- `outputs` 中出现 `fields` 概念本身可以接受；你更担心的是 **schema 设计整体不一致**（导致 LSP 校验/补全与认知边界不稳定）。
- 希望尽可能靠 **YAML LSP + JSON Schema** 完成校验与补全（减少 internal validator 的“第二套规则”）。
- `aggregate` 继续保持“聚合函数名作为 key”的 producer 形态（便于定向补全参数），不希望改成泛化 `kind:` 风格。
- 当前阶段不推进大的 YAML 结构性重设计（先把现有 surface 收敛到可控、可维护）。

基于仓库现状的佐证：

- schema 复杂度贡献最大的是 `definitions.output_aggregate`（结构复杂度与膨胀风险最高的区域）。
- outputs 相关 parsing/runtime 体量很高（`parsers/outputs.py`、`output_composition_yaml.py`），任何新增分支都会放大漂移成本。

可执行的预研拆解（不改 YAML 结构的前提）：

1) **把 `definitions.output_aggregate` 当作首要治理对象**：按 “core stable producers / advanced escape hatches” 分层（保持函数-key），并在 schema hover/docs/editor 层做展示分级（默认展示 core）。
2) **统一 outputs 的 schema 一致性**（尽量让 LSP 自己能判别）：
   - 对 union 的分支做“可预测判别”（required keys / oneOf 分层），避免同一位置出现多个近似形态导致补全噪声。
   - 把 min/max/enum/required/default/examples 写进 schema；把 validator-only 约束标注清楚（语义层/运行时层）。
3) **把 LSP 体验当作验收项**：对 `outputs[*].aggregate.fields.<out_field_id>` 等典型位置做补全回归，确保新增 producer 不会把补全打爆。
4) **示例覆盖补齐**：在 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 补齐至少 1 个“高级口子”示例（`call_by/compute` 等），并确保 `just examples` 对拍通过。

> 停车场：如果未来证实仅靠 schema 分层仍不足以治理（或 GUI 成为刚需），再考虑把聚合/派生能力从 outputs 中进一步解耦（见第 14 节候选）。

### 13.2 workflow.options：你说的“并行池子”控制面在这里（优先梳理语义与 schema）

你给出的关键信号：

- 你主要指的是 `workflow.options` 里的调度/失败/ctx/cache_pool 这块控制面（`max_concurrency/failure_policy/ctx/cache_pool/...`），而不是 demand 内部执行的 `parallel_mode/max_workers`。
- 你当前“不理解、无法掌控”的一部分来源，是 options 参数缺少统一语义说明与示例覆盖（尤其在 marimo demo 中未完整展示）。

可执行的预研拆解（不改 YAML 结构的前提）：

1) **为 `workflow.options` 做“参数字典”**：每个参数写清：默认值、取值边界、对调度/资源/失败的具体影响、以及与 demand 内部并发参数的关系与优先级。
2) **workflow schema-only 的现实约束**：workflow YAML 目前没有 internal validator，因此能写进 schema 的约束要尽量写满（enum/min/max/default/examples），把“跑起来才炸”的概率降到最低。
3) **把 options 变成可对拍的示例套件**：在 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 增加一个专门的 workflow options 示例 YAML（或扩展现有 demo），覆盖：
   - `max_concurrency`
   - `failure_policy`
   - `ctx`（`max_value_bytes/max_bytes`）
   - `cache_pool`（`conflict_policy/release_policy/budget/over_budget_policy`）
4) **中长期候选（停车场）**：若未来 workflow 节点类型继续扩张或需要 GUI，再评估 `workflow.nodes + kind discriminator` 等 v2 结构（见第 14 节），但不纳入当前阶段的默认路线图。

### 13.3 OpenSpec：不要求硬同步，必要时可从实现反向重写 spec

你给出的策略：

- spec 不作为硬门禁；当 spec 与实现冲突时，优先以实现/文档为准。
- 需要时可以从实现反向重写 spec（把 spec 当作“总结/沉淀”，而非每次变更的强约束入口）。

### 13.4 Marimo：把 notebooks/marimo 作为 YAML DSL 能力 SSOT 与对拍门禁

你提出的新约束：

- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 的示例目前没有覆盖全部 YAML DSL 能力点。
- 你希望 `notebooks/marimo/` 永远保留一份“合适的交互式笔记 + YAML DSL 全能力展示 + 对拍验证（集成测试）”，以后任何 DSL 调整都必须同步维护这里。

落到可执行的治理规则（本文件先定口径）：

- SSOT 套件：以 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 为核心，但允许按域拆分多个 YAML（避免单文件爆炸）；由 `demo_main.py`/`run_examples.py` 负责把它们串起来跑通。
- 对拍门禁：任何 YAML DSL 变更必须保证 `just examples` 通过，并在 capability coverage matrix 中标注“新增/变化能力”的覆盖位置。
- 覆盖矩阵：以 `demand.gen.json`/`workflow.gen.json` 为基准，维护 “schema key/definition → 覆盖 YAML 文件/章节/断言” 的映射（先手工，后续可考虑半自动生成）。

当前已发现的覆盖缺口（初步，来自对 `by_yaml_dsl/` 的快速扫查）：

- demand 顶层能力：`retry`、`guardrails`、`failure_policy`、`include_full_error_message` 尚未在 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 出现。
- observability 子域：`viz`、`trace`、`row_gap`、`memory_opt` 尚未在 canonical demo 中覆盖（目前覆盖了 `performance` 与 `relations`）。

---

## 14. 中长期候选（停车场）：结构性重构想法（明确：当前不推进）

> 你已明确：当前阶段不建议推进大的 YAML 结构性设计/重构；因此本节只做“候选记账”，不进入第 11 节的近期路线图。
> 触发条件建议：当仅靠 schema 分层/hover/validator 已无法保持 LSP 体验，或 GUI/图形化成为刚需时，再回到这里选型。

### 14.1 术语与文案（先在 docs/hover 统一，不强制改 YAML key）

- **field_id**：demand 行上下文字段（`main_source.fields` / `sources.*.fields` / 顶层派生 `fields`）。
- **out_field_id / column**：输出层列（outputs/workflow 产物的“列”）。文档/hover 可以优先用 column 说法来降低歧义，但 YAML key 不必立即改名。
- **metric**：聚合输出中的指标列（属于输出列的一种来源/角色）。

短期目标：

- 不强行消灭 `outputs.*.fields`；而是让 schema-reference/hover 明确区分 `field_id` vs `out_field_id`，并保证 LSP 补全与错误提示一致。
- 如果未来确认“同名 key 类型重载”确实伤害 LSP，再进入 14.2 选择是否引入 discriminator 或更名。

### 14.2 outputs 的结构性候选（仅在需要时考虑）

#### 草案 A：引入显式 discriminator（最小结构性调整，优先为 LSP 判别服务）

核心变化（概念层面）：

- 增加 `outputs[*].kind: detail|aggregate|...` 作为显式 discriminator，降低 `oneOf` 分支靠“猜 required keys”的不确定性。
- 不强制更名 `fields`：让不同 kind 下的 `fields` 形态固定（detail: list；aggregate: mapping），并继续保持 producer 为“聚合函数名作为 key”。

示例（仅示意）：

```yaml
outputs:
  - name: detail
    kind: detail
    container: {type: csv, path: ./out/detail.csv}
    fields: [order_id, user_id, amount]

  - name: summary
    kind: aggregate
    container: {type: csv, path: ./out/summary.csv}
    where: "channel == 'direct'"
    aggregate:
      group_by: [channel]
      fields:
        order_cnt: {count: {}}
        sum_amount: {sum: {field: amount}}
    layout: [channel, order_cnt, sum_amount]
```

优点：

- 对 YAML LSP/编辑器 union 判别最直接；对 schema 的可维护性也更好（分支更清晰）。
- 不要求立即改名 `fields`，迁移成本更可控。

缺点：

- 仍是结构性变更（需要 upgrades + 示例套件全量升级 + `just examples` 对拍门禁保障）。

#### 草案 B：把聚合/派生输出提升为顶层域（更清晰，但迁移更大）

核心变化（概念层面）：

- 新增顶层 `derived_outputs`（或 `aggregations`）映射：专门定义聚合/排名/后置派生产物（输出层字段/列定义）。
- `outputs[*]` 只负责容器/路由/启用/布局，并通过 ref 引用某个 derived_output。

示例（仅示意）：

```yaml
derived_outputs:
  summary_direct:
    kind: aggregate
    where: "channel == 'direct'"
    group_by: [channel]
    fields:
      order_cnt: {count: {}}
      sum_amount: {sum: {field: amount}}

outputs:
  - name: detail
    kind: detail
    container: {type: csv, path: ./out/detail.csv}
    fields: [order_id, user_id, amount]

  - name: summary
    kind: derived
    ref: summary_direct
    container: {type: csv, path: ./out/summary.csv}
    layout: [channel, order_cnt, sum_amount]
```

优点：

- outputs 域更“薄”，聚合能力作为第一类域更清晰，也更利于复用与 GUI/图形化。
- derived_outputs 可承接更多派生能力，而不继续把 outputs 变成万能容器。

缺点：

- 引入跨引用（ref），错误定位与 LSP 提示必须更强，否则用户体验可能下降。
- 迁移幅度更大，对示例套件与升级文档要求更高。

### 14.3 workflow 的结构性候选（仅在需要 GUI/扩展时考虑）

当前阻碍（总结）：

- `writes` 采用“单键 intent object” + `oneOf`，扩展成本高、GUI 难表达。
- 写入意图语义上是 DAG node，但语法上嵌套在 run 内。

候选方向（概念层面）：

1) 将 `runs` 与 `writes` 收敛为 **workflow.nodes**（DAG 第一类节点）
2) 节点使用显式 `kind` discriminator（如 `demand` / `write_sheet` / `append_sheet` / ...）
3) 将调度器/并行池（若确实要扩展）收敛成 `workflow.options.scheduler` 的可扩展结构，并允许 Python overrides 覆盖

示例（仅示意）：

```yaml
workflow:
  nodes:
    - id: orders
      kind: demand
      demand: ./orders.yaml

    - id: write_detail
      kind: write_sheet
      depends_on: [orders]
      input: {node: orders, output: detail}
      to: {resource_type: sheetbook, resource_id: report, sheet: Detail, on_conflict: error}

  options:
    scheduler: {kind: thread_pool, max_concurrency: 4}
    failure_policy: primary_only
    cache_pool: ...
    ctx: ...

  resources:
    sheetbooks:
      report: {budget: {max_sheets: 16, max_total_cells: 2000000}, export_xlsx: {path: ./out/report.xlsx}}
```

备注（与现状契约对齐点）：

- 现状 writes 仅支持消费 CSV 输出（runtime 明确 fail-fast）；若做 v2，需要把这个限制写成明确的 schema hover + 语义错误提示，并为未来扩展（workbook/arrow/parquet）预留 kind 分支。
