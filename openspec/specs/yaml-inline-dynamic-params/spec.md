# yaml-inline-dynamic-params Specification

**状态: ✅ 已实现**
## Purpose
为 YAML DSL 的 ref loader 参数构造提供“kwargs 模板 + 内联动态节点”的稳定入口:在 `sources.<id>.params` 中用 `$keys/$rows` 指令节点注入运行时上下文,支持任意嵌套位置注入,并保留 rows barrier 与批次内复用语义,以替代 legacy `bind/to_bind` 与 wrapper 方案.

## Context
旧版 YAML DSL 将 loader 入参拆为:
- `params`: 静态 kwargs
- `bind/to_bind`: 动态注入 lookup keys 或 batch_rows

其中 `bind.use_keys.param` 仅支持顶层 kwarg 注入,难以表达 `kwargs["params"]["..."]` 的 nested params 形态,导致大量 loader 需要额外薄 wrapper 才能复用.

本 spec 通过限制指令集合与 fail-fast 校验,在不引入任意 Python builder 的前提下提供 declarative 的 nested 注入能力.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/params_template.py` (typed template IR + compile/render)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/sources.py` (directives 语义校验与 path 定位)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/_internal/conversion_sources.py` (template -> BindingIr 元数据/params_builder)
- `src/IMPL_ROOT/execution/executor/operators/load_ref/loader.py` (`rows` barrier 与 cache_mode 语义)
- `src/IMPL_ROOT/utils/relation_signature.py` (relation signature / 复用语义)
- `src/IMPL_ROOT/spec/ir/binding/__init__.py` (`build_stable_lookup_key_list`)
## Requirements
### Requirement: `$keys` directive node injects ref lookup keys into loader params templates
系统 SHALL 支持在 loader kwargs 模板中使用 `$keys` 指令节点,用于注入当前 `LoadRef(keys)` 调用的 lookup keys,并允许在任意嵌套位置注入.

指令节点形态 MUST 满足:
- YAML 值 MUST 为 mapping 且仅包含单个 key: `$keys`
- `$keys` 的 value(options) MUST 为 mapping 或 null
- `options.as` 仅允许 `set|list`,缺省为 `set`

#### Scenario: nested params 注入 keys(set)
- **WHEN** `sources.orders_eval.params` 包含:
  ```yaml
  params:
    params:
      order_id_set:
        $keys: {as: set}
  ```
- **THEN** ref loader 调用 MUST 收到 `kwargs["params"]["order_id_set"] == set(lookup_keys)`

#### Scenario: `$keys` 指令节点额外键 fail-fast
- **WHEN** 模板中出现 `{"$keys": {...}, "other": 1}` 这种包含额外键的 mapping
- **THEN** 编译或校验 MUST 失败
- **AND** 错误 MUST 指向该指令节点的配置路径

#### Scenario: composite lookup keys are preserved as tuples
- **WHEN** 目标 source 使用复合 key(例如 `key: [region_id, store_id]`)
- **AND** 模板中使用 `$keys`
- **THEN** 注入到 loader 的 set/list 元素 MUST 保持为归一化后的 tuple lookup keys
- **AND** 系统 MUST NOT 在本变更中隐式拆开 tuple 的各个分量

### Requirement: `$keys.as=list` produces stable ordering
系统 SHALL 在 `$keys.as=list` 路径输出稳定顺序的 keys 列表,不得受集合迭代顺序或 `PYTHONHASHSEED` 影响.

#### Scenario: 不同 hash seed 下 keys(list) 顺序一致
- **WHEN** `$keys.as=list` 且输入 lookup_keys 集合相同
- **THEN** 传递给 loader 的 keys 列表顺序必须一致

### Requirement: `$rows` directive node injects batch rows and preserves rows semantics
系统 SHALL 支持在 loader kwargs 模板中使用 `$rows` 指令节点,用于注入当前 `LoadRef(rows)` 调用的批次行上下文(batch rows).

指令节点形态 MUST 满足:
- YAML 值 MUST 为 mapping 且仅包含单个 key: `$rows`
- `$rows` 的 value(options) MUST 为 mapping 或 null
- `options.cache_mode` 仅允许 `batch|none`,缺省为 `batch`

`$rows` 的存在 MUST 保持与现有 rows 绑定等价的语义信号(例如 rows barrier、批次内复用语义).

#### Scenario: `$rows` 注入 batch rows
- **WHEN** `sources.customers.params` 中出现:
  ```yaml
  params:
    rows:
      $rows: {cache_mode: batch}
  ```
- **THEN** ref loader 调用 MUST 收到 `kwargs["rows"] == batch_rows`

#### Scenario: `$rows.cache_mode=none` 禁用批次内复用
- **WHEN** `$rows.cache_mode=none`
- **THEN** 系统 MUST 将该 ref loader 视为不可批次复用的 rows 绑定

### Requirement: directives are composable with dict/list nesting
系统 MUST 支持 `$keys/$rows` 指令节点出现在 dict/list 的任意嵌套位置,并在渲染后保持其它静态结构不变.

#### Scenario: list nesting 注入 keys
- **WHEN** 模板中出现:
  ```yaml
  params:
    ids:
      - 1
      - {$keys: {as: list}}
      - 3
  ```
- **THEN** 渲染后 `kwargs["ids"]` MUST 为包含 lookup keys(list) 的列表结构(其它静态项保持原样)

### Requirement: params template rendering is pure and alias-safe
系统 MUST 将模板渲染视为纯函数:
- MUST NOT 原地修改解析后的 YAML 对象(避免 anchor/alias 共享对象被污染)
- 同一模板在不同运行时上下文下渲染 MUST 互不影响

#### Scenario: 多次渲染不串值
- **GIVEN** 同一份配置模板(可能包含 YAML alias 复用)
- **WHEN** 在两个不同批次/不同 lookup_keys 下分别渲染
- **THEN** 两次渲染得到的 kwargs MUST 不共享可变子对象引用
- **AND** 渲染结果 MUST 与各自上下文一致

### Requirement: `$keys/$rows` are only valid in ref loader call contexts
系统 MUST 限定 `$keys/$rows` 仅在 ref loader 调用上下文中可用:
- main source loader 与 preload loader 上下文 MUST 禁止使用 `$keys/$rows`
- 当目标 source 为 `preload_forever` 且其 preload callsite 会触发模板渲染时,模板 MUST 不得包含 `$keys/$rows`

#### Scenario: main_source.params 使用 `$keys` 被拒绝
- **WHEN** `main_source.params` 中出现 `$keys` 或 `$rows`
- **THEN** 编译或校验 MUST 失败并报告配置路径

### Requirement: `$keys` and `$rows` are mutually exclusive within a single template
系统 MUST 禁止在同一份 loader kwargs 模板中同时出现 `$keys` 与 `$rows`,以保持绑定模式与调度语义清晰且无歧义.

#### Scenario: 同时出现 `$keys` 与 `$rows` fail-fast
- **WHEN** 同一模板中同时出现 `$keys` 与 `$rows`
- **THEN** 编译或校验 MUST 失败并报告冲突位置

