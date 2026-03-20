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

> 说明：本文档不做这些实现，只把门禁固定下来。

### 5.5 安全边界不可滑坡（compute 不演进为脚本）

- `compute` 继续保持“安全表达式”定位：不引入属性访问/下标/任意调用等会扩大攻击面的能力。
- 复杂逻辑统一走 `call_by` + allowlist（且 allowlist 永远由环境提供，不写死在 YAML）。

---

## 6. 分域收敛路线图（方向性，不落地实现）

> 每个域都按同一模板表达：**问题形状 → 目标形状 → 禁止事项 → 下一步切片建议**。

### 6.1 Outputs：把“输出编排”收敛成可读、可验、可演进的最小模型

**问题形状**

- 输出域承载太多概念（容器/布局/路由/聚合/复用/禁用/失败策略/脱敏/临时输出）。
- 容易产生语义误用（`where` 被当开关、复用规则不清等）。

**目标形状（统一认知）**

- `enabled`：静态开关（替代“where=false”这类误用）
- `where`：只做行级路由谓词（永远不承担开关语义）
- `container`：物理承载（workbook/csv），对 workflow-managed 临时输出的特殊形态要“明确标注为仅 workflow 可用”
- `fields` vs `aggregate`：二选一且结构清晰（避免出现混合语义）
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

---

## 9. 本文档的范围声明

- ✅ 做：统一认知、确定原则、给出收敛路线图与治理门禁、列出未来验收清单。
- ❌ 不做：任何代码修改、任何 schema 生成物更新、任何自动升级脚本、任何 OpenSpec 工件接入。

