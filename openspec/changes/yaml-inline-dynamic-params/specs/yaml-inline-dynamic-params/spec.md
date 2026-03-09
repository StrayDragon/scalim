## ADDED Requirements

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

`$rows` 的存在 MUST 保持与现有 `use_rows` 等价的语义信号(例如 rows barrier、批次内复用语义).

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
- **THEN** 系统 MUST 将该 ref loader 视为不可批次复用的 rows 绑定(等价于 legacy `use_rows.cache_mode=none`)

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

