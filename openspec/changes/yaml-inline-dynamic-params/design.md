## Context

当前 YAML DSL 将 loader 入参拆为两部分:

- `params`: 静态 kwargs 映射
- `bind/to_bind`: 运行时动态入参注入(lookup keys / batch_rows)与其附带的调度/复用语义

实现上,`bind` 会在编译阶段生成 `BindingIr.params_builder(ctx) -> (args, kwargs)` 的闭包,在运行时由执行器调用并把结果传给 loader。由于现有 `use_keys.param` 只能注入到顶层 kwarg,无法表达将 keys 注入到 `kwargs["params"]["..."]` 这种 nested params 写法,导致下游大量 loader 需要再包一层“整形入参”的 wrapper 才能复用。

同时,`bind/use_rows` 不仅是“传参方式”,还承担了执行语义信号:

- `rows` 作为 adaptive 调度并行屏障
- `rows.cache_mode` 影响批次内复用与 cache key
- `keys.as=list` 需要稳定顺序保证

因此本设计必须在不开放任意 Python builder 的前提下,提供 declarative 的 nested 注入能力,并保留上述语义。

## Goals / Non-Goals

**Goals:**

- 允许在 `main_source.params` / `sources.<id>.params` 任意嵌套位置注入运行时 keys/rows,以模板方式完整描述 loader kwargs。
- 保持现有执行边界与语义: rows barrier、cache_mode、keys list 的稳定顺序、relation signature/批次复用。
- 将 `params` 模板编译为单一 canonical representation,并在 preload/ref-load 两侧复用,避免出现两套 params 语义。
- 提供清晰且可定位的 fail-fast 校验错误(包含配置 path),避免静默退化为 wrapper 地狱。
- YAML 友好: 支持 anchor/alias 复用(并避免 alias 引用对象被运行时渲染修改导致串源污染)。

**Non-Goals:**

- 不支持任意 Python 表达式、任意函数调用、属性访问或字符串子串插值。
- 不尝试在本变更中落地多输出/多 sheet 或其它 DSL 扩展。
- 不引入新的外部依赖(保持 PyYAML 解析与现有安全边界)。
- v1 不提供 composite key 的按分量投影语法(例如 `$keys.foo`/`$keys[0]`);复合 key 先整体以 tuple 形式注入.

## Decisions

### 1) 指令语法采用“对象节点”而非字符串占位

采用如下形式:

```yaml
params:
  params:
    order_id_set:
      $keys: {as: set}
```

理由:

- YAML anchor/alias 可直接复用整个指令节点。
- 避免 `$keys` 出现在 SQL/文本中的误伤;也避免复杂的插值/转义规则。
- JSON schema 对 `params` 已允许 `additionalProperties: true`,不需要引入新的 schema 结构才能通过基础结构校验。

约束:

- 指令节点 MUST 是仅包含一个保留 key 的 mapping(例如只含 `$keys` 或只含 `$rows`)。
- 指令 options MUST 是 mapping 或 null;未知 option MUST fail-fast。

### 2) 编译为单一 params template IR,并由 preload/ref-load 共用

实现上先将 `main_source.params` / `sources.<id>.params` 编译为 typed template IR(例如 `LoaderKwargsTemplateIr`),再由不同 callsite 复用:

- ref loader 仍走 `BindingIr + call_loader_with_binding(...)` 路径,以确保:
  - instrumentation 能拿到“最终传入 kwargs”
  - relation signature 能继续把 binding 作为分组/复用信号
  - adaptive 调度仍可通过 `binding.mode == "rows"` 识别 barrier
- preload loader 使用同一份 template IR 渲染最终 kwargs,不得再维护一套独立的 raw `params` 透传逻辑

typed template IR 的最小节点形态:

- `LiteralNode(value)`
- `MappingNode(items...)`
- `ListNode(items...)`
- `KeysDirectiveNode(as=set|list)`
- `RowsDirectiveNode(cache_mode=batch|none)`

其中:

- `$runtime.*` 在模板编译阶段被解析并落成 `LiteralNode(value)`
- 一旦某个值被解析为 `LiteralNode`,后续渲染阶段 MUST 不再按结构扫描其中的 `"$keys"`/`"$rows"` 键
- 这意味着 runtime 注入进来的 `dict/list/object` 都视为 opaque leaves,不会被误判为动态指令节点

具体规则:

- 模板中出现 `$rows` 时,该 loader 的 binding.mode 设为 `"rows"`,并从 `$rows.cache_mode` 读取 `batch|none`(默认 `batch`)。
- 否则,模板中出现 `$keys` 时,mode 为 `"keys"`,并从 `$keys.as` 读取 `set|list`(默认 `set`)。
- 若模板未出现任何动态指令,仍保留同一份 template IR 作为 canonical representation:
  - ref loader 可通过“静态 binding”适配现有执行路径,但 MUST 复用同一份 template IR
  - preload loader 直接渲染同一份 template IR
  - 不允许 preload 与 ref-load 各自重新编译一份 params 逻辑

### 3) `$keys` / `$rows` 互斥,并保持 composite key 的整体形态

为保持调度语义清晰:

- 同一份模板中 `$keys` 与 `$rows` MUST 互斥;若同时出现,校验阶段直接报错
- `$keys` 注入的是“完整 lookup key 集合/列表”:
  - 单 key source: 元素为普通标量 key
  - composite key source: 元素为 tuple key,保持归一化后的 tuple 结构
- v1 不提供 `$keys` 的按分量投影语法;若业务需要拆解 composite key,应在 loader 内处理或后续单独扩展语法

指令的运行时来源来自 `LoaderCallContextIr`:

- `$keys`: ref loader 的 lookup keys
- `$rows`: ref loader 的 batch rows 上下文

非法场景 fail-fast:

- preload callsite 或非 ref loader 上下文出现 `$keys/$rows`
- `$rows.cache_mode=none|batch` 之外的取值
- `$keys.as=set|list` 之外的取值

### 4) 深拷贝渲染,避免 alias 共享对象被污染

PyYAML 的 anchor/alias 会产生共享对象引用。模板渲染必须视为纯函数:

- 输入的配置对象不得被原地修改
- 每次 render 生成一份新的 kwargs 树(递归 copy)

### 5) `bind/to_bind` 从 YAML authoring surface 中移除

为避免语义分裂与双轨维护:

- 最终规范中,`sources.<id>.bind` 与 `relations.*.steps[].to_bind` 不再作为 loader 入参构造的稳定 YAML 入口
- validator/schema/docs/examples MUST 以 `params` 模板为唯一 authoring surface
- 遇到旧写法时,校验错误应明确给出迁移提示,指向新的 `params` 模板写法

## Risks / Trade-offs

- [复杂性上升] 引入模板渲染与语义校验 → 通过限制指令集合与 fail-fast 规则控制复杂度,并为每类指令补齐回归测试。
- [行为变化风险] 过去某些 source loader 可能依赖零参调用 → 通过“仅在配置了 params/指令时才构造静态 binding”降低误伤;并在 Migration Plan 中要求升级配置。
- [rows 屏障误用] 用户把 `$rows` 用作“方便拿上下文”会导致并发退化 → 文档与 skill 必须强调 `$rows` 会触发 barrier,并提供替代(优先 `$keys`)。
- [模板节点难以 schema 化] JSON schema 难以在 `params` 深处做结构提示 → 通过 hover 文档与 CLI validate 的语义校验补齐可用性。
- [移除旧语法的破坏性] `bind/to_bind` 从 YAML surface 移除会影响存量 YAML → 需要 migration guidance、明确错误文案与一轮仓内配置升级。

## Migration Plan

1. 在 DSL 编译器中新增 typed params template IR/渲染器,并让 preload/ref-load 共用该 representation。
2. 从 template IR 派生 binding metadata(`mode/as/cache_mode`),并补齐单元测试。
3. 升级仓库内 YAML 示例与文档: 将 `bind/use_keys.param` + wrapper 方案替换为 `$keys/$rows` 内联模板。
3. 升级 `artifacts/skills/scalim-yaml-dsl/**`:
   - authoring 示例使用新语法
   - upgrade-legacy playbook 明确给出迁移规则与常见错误诊断
4. 更新 validator/schema,使 `bind/to_bind` 退出稳定 YAML authoring surface,并在 CLI validate 输出明确迁移提示。

## Open Questions

- 是否需要额外提供 `$batch_row_nth` 等非 ref 场景变量,或直接禁止并强制用户显式 loader?
- composite key 是否需要 follow-up 提供按分量投影语法(例如 `$keys.fields` / `$keys.parts`),还是继续保持“整体 tuple 注入”的最小语义?
- old YAML 的自动迁移是否需要脚本辅助,还是仅靠手工迁移与示例牵引?
