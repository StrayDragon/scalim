## Context

当前 Scalim 执行层已具备:

- `output-composition`: 多输出目标、同一 workbook 多 sheet、failure_policy、meta/audit/fingerprint 等标准产物
- `derived-outputs`: 在同一份明细流上派生汇总(增量聚合 + finalize 输出)

但 YAML authoring surface 仍是单输出模型(`output`),导致业务侧在“同一份明细分发多 sheet / 同次运行派生汇总 / 一键开 meta/audit”这类常见交付形态上必须写 Python glue(自定义 sink 或手拼 `OutputCompositionSpec`),且 where/predicate 只能写 Python callable,难以复用与沉淀。

本变更的目标是把既有执行语义暴露为 YAML DSL 的一等语法(`outputs`),并补齐 `where` 的安全边界与依赖注入,让“分发/汇总编排”从 Python glue 下沉到 YAML。

参考:
- 提案: `proposal.md`
- 最小脱敏可运行样例(当前 baseline 仍靠最薄 Python sink 兜 multi-sheet): `acceptance/mvp_demo/README.md`
- 规范: `specs/yaml-dsl-schema/spec.md`

## Goals / Non-Goals

**Goals:**
- 在 demand YAML 顶层新增 `outputs` 入口,可在同一次运行中声明多个输出目标:
  - 多 sheet 分发(通过 `where` 过滤)写入同一 workbook
  - 派生汇总输出(通过 `aggregate`)写入汇总 sheet
- 支持 `outputs.*.from` 复用另一个 output 的字段集合与容器配置,并允许覆盖 `where`/sheet/aggregate 等。
- `where` 使用受限安全表达式引擎(拒绝任意导入执行),并在编译期静态分析依赖字段,显式注入到执行层(required fields)以保证口径确定性。
- YAML 侧显式暴露 `failure_policy`/error_message 脱敏策略以及 workbook 容器选项(`allow_formulas`/`write_lock`),与现有执行语义对齐(不改语义)。
- 落地到运行时装配: `outputs` → 等价的 `OutputCompositionSpec` +(如适用) `DerivedOutputs` 配置。

**Non-Goals:**
- 不在本变更中新增/扩展派生聚合算子能力(例如 distinct/dedup/two-stage 等更复杂聚合),仅暴露当前执行层已支持的能力;后续可在独立 change 中扩展并增量暴露到 YAML。
- 不允许 `where` 使用任意 Python callable / 动态 import;只支持受限表达式。
- 不为旧写法保留兼容层: 默认将仓内所有 demand YAML 从 `output` 一步升级为 `outputs`(如需兼容需另行显式提出)。

## Decisions

### 1) YAML 形态: `outputs` 采用有序列表 + `name`

- `outputs` 设计为 **list[object]** 而不是 mapping:
  - 保留声明顺序,用于稳定确定 “默认 primary 输出 / workbook sheet 顺序 / meta/audit 写入顺序” 等行为
  - 避免在 Python 3.6 下对 dict 顺序语义产生隐式依赖
- 每个 output 必须有唯一 `name`,并可被 `from` 引用:
- `outputs.*.fields`(MVP) 仅支持字段 ID 的字符串列表: `fields: [field_id, ...]`。
  - 不复用旧 `output.fields` 的“对象/alias”模型,避免在 MVP 中引入额外复杂度;后续若需要字段级覆盖/alias 复用,再独立扩展。

示意(非最终 schema,以实现为准):

```yaml
outputs:
  - name: detail
    container: {type: workbook, path: demo.xlsx, sheet: 订单明细}
    fields: [order_id, user_id, channel]

  - name: direct_detail
    from: detail
    where: "channel == 'direct'"
    container: {type: workbook, path: demo.xlsx, sheet: 直客明细}

  - name: by_cs
    from: detail
    aggregate:
      group_by: [cs_id, cs_name]
      metrics:
        order_cnt: {op: count, field: order_id}
        sum_amount: {op: sum, field: amount_yuan}
    container: {type: workbook, path: demo.xlsx, sheet: 客服汇总}
```

### 2) `from` 继承规则(复用 + 覆盖)

- `from` 仅允许引用同一 YAML 内已经声明(或可解析)的 output `name`。
- 继承项:
  - `fields`(仅明细输出): 如果当前 output 未声明 `fields`,从 `from` 继承
  - `container`: 如果当前 output 未声明 `container`,从 `from` 继承
  - 其他与输出策略强相关的选项(如 include_header 等)可按实现需要纳入继承(建议: “显式覆盖优先,未声明则继承”)
- 不继承项:
  - `where`: 默认不继承,避免隐式叠加导致语义难以读懂;需要复用时建议通过 `from` 继承字段/容器并显式声明自身 `where`
  - `aggregate`: 不继承;派生汇总应显式声明

### 3) 明细输出 vs 派生输出的判定

- 当 output 含 `aggregate` 时,视为 **派生输出**(进入 `OutputCompositionSpec.derived_targets`)。
- 否则视为 **明细输出**(进入 `OutputCompositionSpec.targets`)。
- 派生输出的导出 layout 由 `aggregate` 决定(默认: `group_by` + 各 metric 的 out_field_id [+ 可选 rank 字段])。

### 4) 容器模型: `container` 映射到 `OutputSpec`

YAML 侧引入一个显式 `container` 结构,用于表达“同 workbook 多 sheet”这一 authoring 意图,并直接映射到 `OutputSpec`:

- `type: workbook` → `format: excel`
  - `path`: workbook 文件路径(相对路径以进程 CWD 为基准,与现有 `OutputSpec.path` 语义一致)
  - `sheet`: 对应 `OutputSpec.sheet_name`
  - `allow_formulas` → `OutputSpec.excel_allow_formulas`
  - `write_lock` → `OutputSpec.write_lock`
- `type: csv`(可选,如需要支持同一次运行多 CSV) → `format: csv`
  - 复用现有 CSV 输出语义(encoding/include_header/streaming 等),但需满足 composed outputs 的限制(仅 streaming row sink)

约束:
- composed outputs 中 `path` 必填(执行层已要求)。
- 若多个 outputs 共享同一 excel `path`,则这些 outputs 必须显式给出 `sheet`(执行层已要求)。
- composed outputs 仅支持 `streaming=true`(执行层已要求);YAML 侧应在编译期 fail-fast 并给出明确错误。

### 5) `failure_policy` / error message 脱敏策略

- YAML 侧显式暴露:
  - `failure_policy`: `all_fail` / `primary_only` → `OutputCompositionSpec.failure_policy`
  - `include_full_error_message`: bool → `OutputCompositionSpec.include_full_error_message`
- `primary_only` 的可用性依赖“primary 输出”的确定:
  - MVP: primary 由 outputs 列表顺序决定(默认第一个明细/派生 output 为 primary;与执行层 `_ensure_primary_route` 一致)
  - 若未来需要“顺序与 primary 解耦”(例如保持展示顺序但指定另一个为 primary),再新增显式 `outputs.*.primary` 字段并做唯一性校验。

### 6) `meta/audit/fingerprint` 标准产物

- YAML 侧提供一键开关(例如 `meta: true` / `audit: true` 或对象形式),由编译器物化:
  - `OutputCompositionSpec.meta_sheet`
  - `OutputCompositionSpec.audit_sheet`
- 默认写入同一 workbook(与业务对拍习惯一致),并提供默认 sheet 名(例如 `__meta__` / `__audit__`),同时允许覆盖。
- `fingerprint` 来源沿用执行层现有计算(不引入新语义)。

### 7) `where` 安全表达式 + 依赖字段注入

- `where` 仅接受 string 表达式,使用现有 `SecureComputeEngine` 进行校验与编译:
  - 禁止任意 import / attribute access / keyword args 等非受控行为(由引擎保障)
  - 表达式中的非 builtin 名称视为字段依赖(字段名 = field_id)
- 编译期行为:
  - 静态提取依赖字段 `deps`
  - 校验每个依赖字段都能在 demand 的字段空间中解析(包含 main/source/derived)
  - 将 `deps` 显式注入到对应 target 的 `requires`(即 `OutputTargetSpec.requires` / `DerivedOutputTargetSpec.requires`),确保执行计划会计算这些字段,避免“未在输出字段集合中导致取值 None”造成口径偏差
  - 若依赖字段无法解析,编译期 MUST fail-fast 并提示补齐字段定义/引用

### 8) 编译管线与职责边界(含生成物治理)

- **Schema/authoring 层**(`src/scalim/dsl/by_yaml/schema_dsl/**`):
  - 定义 `outputs` 的结构、约束与文档说明
  - 生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json`(生成物,禁止手改)
- **Parsing/validation 层**(`src/scalim/dsl/by_yaml/config_parsing/**`):
  - 解析 `outputs` 并做语义校验: name 唯一性、from 引用解析、container/path/sheet 约束、where 表达式安全校验与依赖提取等
- **Runtime compilation 层**(`src/scalim/dsl/by_yaml/runtime/**`):
  - 将解析后的 outputs 装配为 `OutputCompositionSpec` 并写入 `ExecutionRequest.output_composition`
  - 保持执行层语义不变: 仅把既有能力暴露到 YAML

文档/生成物边界:
- `demand.gen.json` 属于生成物;必须通过 schema_dsl SSOT 变更并运行生成命令刷新,不得手改。
- docs 站点与 injected blocks(含 `.gen.` 文件与 `BEGIN/END AUTOGEN:*` 区块)同理,通过 `just gen-docs` 刷新,由 `just qa`/CI drift gate 兜底。

## Risks / Trade-offs

- **破坏性变更风险**: 移除 `output` 并升级为 `outputs` 会影响所有既有 YAML 与示例;需配套迁移与清晰错误提示。
- **表达式能力边界**: `where` 受限表达式可能无法覆盖所有业务想法;需要通过“新增受控函数/算子”方式演进,而不是放开任意 Python。
- **依赖注入的可见性**: 自动把 where 依赖注入 required fields 可能让用户在输出字段中“看不到”依赖字段;需要在诊断信息与文档中明确说明(例如校验报告里显示注入字段列表)。
- **Excel 并发写**: 多 sheet 共享 workbook 时需要 `write_lock` 护栏;默认策略与性能影响需要在文档中明确。

## Migration Plan

1. Schema:
   - 在 schema_dsl 中新增 `outputs` 相关模型与 JSONSchema 定义
   - 从 DemandConfig 中移除/替换旧 `output` 字段(不做兼容层)
   - 通过既有生成入口刷新 `demand.gen.json`(生成物)
2. Parsing & validation:
   - 实现 `outputs` 解析、`from` 继承解析、语义校验与错误路径定位
   - 集成 `where` 的安全校验/编译与依赖注入
3. Runtime wiring:
   - 在 YAML runtime 编译阶段装配 `OutputCompositionSpec` / derived targets
   - 确保 `required_demand_fields` 覆盖输出字段与 where/aggregate 依赖字段
4. Tests / acceptance:
   - 将 `acceptance/mvp_demo` 的需求表达转为 fixtures/回归用例(脱敏),覆盖多 sheet 分发、派生汇总、meta/audit/fingerprint 开关等
5. Demos / docs:
   - 升级 canonical demo YAML(例如 notebooks 下的 ecommerce_report)以覆盖新语义
   - 运行 `just gen-docs` 刷新文档站生成物与注入区块
6. Gate:
   - 变更完成后运行 `just qa` 与 `just openspec-check` 确保无 drift 与 OpenSpec 校验通过

## Open Questions

- `meta/audit` 默认 sheet 名是否应强制使用保留前缀(例如 `__meta__`),以及与用户自定义 sheet 冲突时的策略?
