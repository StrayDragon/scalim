## Context

当前 YAML DSL 的 `sources.<id>.normalize` 仅支持 `kind: index_by_key`:

- 当 loader 返回 `list[row]` 时可归一化为 `mapping[key -> row]`
- 当 loader 已返回 `mapping` 时会被直接透传

但在业务报表迁移里,lookup 小表/维表的返回值形状经常不是理想的 `mapping[key -> row]`,典型包括:

- `mapping[key -> list[row]]`: 需要 `take_first`/`on_empty` 等策略才能稳定落地为单条 row
- `mapping[key -> nested_dict]`: 需要对 values 做拍平/投影/重命名,且中间 key 可能是 `int/enum` 值(点路径无法表达)

缺少这些能力导致业务侧被迫写大量 Python wrapper,阻碍“脚本变薄”和 normalize 片段复用(尤其是 `preload_forever` 小表的通用 normalize).

约束/边界:

- 运行时必须兼容 Python 3.6
- YAML 引用解析需复用既有 allowlist 安全边界
- schema/hover/validate 必须通过结构化 schema 体现(并遵守生成物与 injected-block 的治理规则)

## Goals / Non-Goals

**Goals:**

- 扩展 `sources.<id>.normalize` 语义,覆盖提案中的常见“非理想形状”:
  - `take_first`: 将 `mapping[key -> list[row]]` 归一化为 `mapping[key -> row]`(并定义 `on_empty`)
  - `map_values`: 对 `mapping` 的 values 批量应用 normalize pipeline
  - `project_fields`: 对 row 或 nested mapping 做投影与重命名,并复用既有 `extract` 路径语法定位(支持 int/enum key)
- 提供受控扩展点 `normalize.call_by`(可选),复用 allowlist 与引用归一化能力,并固定 `Mapping -> Mapping` contract
- fail-fast + 可诊断: 对形状不符合预期的 loader 返回值与 normalize 配置给出清晰错误信息
- 明确文档/生成边界与 drift gate(避免手改生成物导致漂移)

**Non-Goals:**

- 不引入“任意表达式语言”来做通用 transform(避免不可控与难以审计)
- 不改变 loader 的调用模型/绑定机制(仍由既有 `$keys/$rows` params 模板驱动)
- 不在本变更中覆盖 outputs/workbook、聚合指标等其它 DSL 能力

## Decisions

### 1) Normalize 的运行时契约

- `normalize` 发生在 loader 调用之后、guardrails/字段抽取之前.
- 无论 `normalize.kind` 如何扩展,最终 `normalize.apply(...)` 的返回值都 MUST 为 `Mapping[lookup_key, value]`,以满足 lookup 执行器的基本契约.
- 对于无法在 declarative normalize 中表达的形状,允许在 `normalize.call_by` 中补齐,但强制 `Mapping -> Mapping` 以避免形状漂移.

### 2) YAML authoring surface(面向用户的写法)

#### 2.1 `normalize.kind=take_first`

用于将 “多条候选” 归一化为 “单条”:

- **输入形状**: `mapping[key -> list[row]]` → 输出 `mapping[key -> row]`

建议配置:

```yaml
normalize:
  kind: take_first
  on_empty: miss  # miss|null|error
```

语义:

- 输入 MUST 为 `Mapping`,且每个 value MUST 为 `list/tuple`:
  - value 非空: 取第 1 条作为 row
  - value 为空: `on_empty=miss` 则该 key 视为 lookup miss(从结果映射中移除); `null` 则写入 `None`; `error` 则抛错

> 决策: 顶层 `list[row]` **不**由 `take_first` 处理. list→keyed mapping 统一使用既有 `index_by_key` + `on_conflict`,避免职责重叠与二义性.

#### 2.2 `normalize.kind=project_fields`

用于对 row 或 nested mapping 做投影与重命名,并支持 int key:

```yaml
normalize:
  kind: project_fields
  on_missing: error  # error|null
  fields:
    order_id: {from_key: true}
    customer_level: {extract: "[1].clearn_reason_level"}
    operation_level: {extract: "[2].clearn_reason_level"}
    review_status: {extract: "review_status"}
```

语义:

- `fields` 的 key 为输出字段名(天然完成 rename)
- `from_key: true` 表示取 lookup key(外层 mapping 的 key)写入该字段
- `extract` 复用既有字段 `fields.<id>.extract` 的路径语法,从而可表达 “中间 key 为 int/enum” 的嵌套定位(例如 `"[1].clearn_reason_level"`)
- `on_missing`:
  - `error`: 任一路径缺失则报错(更早暴露数据形状漂移)
  - `null`: 缺失则填 `None`(更宽松,适合灰度迁移)

> 决策: `project_fields` 保持“纯投影/重命名”(可注入 `from_key`),不引入常量/表达式赋值;常量/派生逻辑使用既有字段 `compute/call_by` 或 `normalize.call_by`.

#### 2.3 `normalize.kind=map_values`

当需要对 `mapping` 的 values 进行多步归一化时使用:

```yaml
normalize:
  kind: map_values
  steps:
    - kind: take_first
      on_empty: miss
    - kind: project_fields
      on_missing: error
      fields:
        order_id: {from_key: true}
        review_status: {extract: "review_status"}
```

语义:

- 输入 MUST 为 `Mapping`
- 对每个 `(key, value)` 依次执行 `steps` 中的 normalize 步骤
- 每个步骤可读取当前 `(key, value)` 上下文(用于 `from_key`)

### 3) `normalize.call_by` 的受控扩展点

为覆盖 declarative normalize 无法表达的场景,提供可选字段:

```yaml
normalize:
  kind: map_values
  steps: [...]
  call_by: myapp.normalizes:normalize_source_x
```

约束:

- 引用解析与 loader/compute 相同:
  - 支持绝对/相对引用
  - 受 allowlist(allowed_modules/allowed_functions) 约束
- 固定 contract: `Mapping -> Mapping`(whole-result)
  - 若输入不是 `Mapping`,或返回值不是 `Mapping`,则 fail-fast 并指出 contract 违反
- `call_by` 仅允许 top-level 使用,不作为 `map_values.steps` 的一步;需要 value-level 自定义时,在 `call_by` 内部自行遍历 `result.items()` 处理

调用建议签名(可选 ctx,便于诊断):

- `fn(result, ctx) -> Mapping`
  - `ctx.source_id`
  - `ctx.kind` / `ctx.config_path`(用于错误定位)

### 4) 文档/生成边界与 drift gate

- `src/scalim/dsl/by_yaml/schema_dsl/**` 为 schema SSOT,生成物(例如 `src/scalim/dsl/by_yaml/schema/*.gen.*`)禁止手改
- 本变更涉及 schema 描述与 examples 时:
  - 仅改 SSOT(model/constants)
  - 通过既有生成入口刷新产物(例如 `just gen-docs`/对应 generator)
- 变更完成后使用 `just openspec-check`/CI 漂移门禁确保:
  - OpenSpec 工件可被校验
  - schema 生成物与注入块无漂移

## Risks / Trade-offs

- **配置复杂度上升** → 通过 schema hover/examples + 语义校验兜底;将 `map_values` 定位为“需要多步时才用”
- **`on_empty`/`on_missing` 选择影响口径** → 文档明确 `miss` vs `null` 的执行差异,并在测试中覆盖
- **`call_by` 可引入不确定性** → 通过 allowlist + Mapping contract + 明确错误信息降低风险;建议仅在必要时使用

## Migration Plan

1. 扩展 schema SSOT:
   - `normalize.kind` 枚举新增 `take_first/map_values/project_fields`
   - 新增对应配置对象 schema 与 markdownDescription/examples
2. 运行生成入口刷新 schema 产物,并通过 drift gate(避免手改生成物)
3. 逐步将现有 Python wrapper 场景迁移为 declarative normalize(可按 demand 逐步落地)
4. 若线上出现风险,可在 YAML 中回退到旧写法(移除 normalize 或改回 `index_by_key`),并保留 wrapper 作为临时兜底
