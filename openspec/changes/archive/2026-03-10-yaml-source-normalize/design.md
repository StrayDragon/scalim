## Context

当前 lookup source 的 YAML surface 没有 whole-result normalization 入口。

仓库内部虽然有 `LoaderIr.extractor`,但它的语义是:

- 输入: `(lookup_key, loader_result_mapping)`
- 输出: 当前 key 对应的单条 row data

也就是说它是“per-key extraction”,不是“对整个 loader 返回值先做一次归一化”。与此同时,执行链路会很早把 loader 原始返回值收敛到 `LoaderResultMapping`:

- preload 路径在 `Pipeline._preload_cached_sources()` 中直接 `coerce_loader_result_mapping(...)`
- ref load 路径在 loader helper 中直接 `coerce_loader_result_mapping(...)`

这使得像 `list[row] -> key -> row` 这样的整体结果整形无法 declarative 下沉到 YAML,业务方只能继续包一层 Python wrapper。

## Goals / Non-Goals

**Goals:**

- 在 `sources.<id>` 上提供 declarative `normalize`,用于 whole-result normalization。
- 初版先覆盖最常见的 `list[row] -> key -> row` 归一化,减少为 ET / report loader 编写薄 wrapper 的需求。
- 明确 `normalize` 与字段级 `extract` 的边界: `normalize` 处理整个 source 返回值,`extract` 处理单个字段如何从 row 中读取。
- 让 preload/cache 与非缓存路径都观察到同样的 normalized result 形状。
- 为未来 `normalize_fn` 预留稳定命名空间。

**Non-Goals:**

- v1 不支持 `main_source.normalize`;主数据源 contract 仍保持“按行 iterable”.
- v1 不开放任意 Python normalize 函数。
- v1 不处理 nested envelope 中的列表提取、project_fields、multi-step transforms;这些留给后续 preset 或 wrapper。

## Decisions

### 1) Scope `normalize` to `sources.<id>` only

`normalize` 初版仅允许出现在 lookup source(`sources.<id>`)下,不允许出现在 `main_source`.

理由:

- 当前 main source contract 是 `Iterable[RowData]`,不是 `LookupKey -> RowValue` 映射;
- 当前 whole-result normalization 需求和内部可复用点都集中在 lookup source;
- 若同时打开 main_source.normalize,就会把“iterable 级 reshaping”与“mapping 级 normalization”混成一层,导致实现和文档都失焦。

备选方案:

- 同时支持 `main_source.normalize`

拒绝原因:

- 现有 main source 执行路径与 source loader 路径完全不同,会显著扩大实现和认知范围。

### 2) v1 only ships a declarative `index_by_key` preset

公开 YAML 形态:

```yaml
sources:
  order_recommends:
    loader: "..."
    key: order_id
    normalize:
      kind: index_by_key
      key_field: order_id
      on_conflict: error
```

语义:

- 输入是 `list[row]`
- 输出是 `mapping[lookup_key, row]`
- `key_field` 用于从每个 row 提取 lookup key
- `on_conflict` 允许 `error|first|last`,默认 `error`

选择 `index_by_key` 而不是旧的 `list_by_key`,是因为它更准确表达“建立索引”,不会被误解为 `key -> list[rows]` 分组。

### 3) Whole-result normalize needs a dedicated IR slot; do not overload `LoaderIr.extractor`

YAML `normalize` 不应直接复用 `LoaderIr.extractor`.

原因:

- `LoaderIr.extractor` 是 per-key,签名和调用时机都不对;
- whole-result normalize 必须在 `coerce_loader_result_mapping(...)` 之前执行;
- preload/cache 路径也需要消费同一能力。

因此实现上应新增独立的 source-level normalizer 表示(例如 `result_normalizer` / `normalize_spec`),并让所有 lookup source loader callsite 在同一位置应用:

1. 调 loader 得到 raw result
2. 若声明 `normalize`,先把 raw result 归一化为 `LoaderResultMapping`
3. 再进入 `coerce_loader_result_mapping(...)` / cache write / field extraction

### 4) Cache stores normalized mappings, not raw loader outputs

`preload_forever` 必须缓存 normalize 后的结果,并确保 cache hit path 与非 cache path 对字段读取看到同样的形状。

这意味着:

- normalize 发生在 preload 写缓存之前
- instrumentation 对外暴露的结果形状应与实际缓存/读取形状一致
- source-cache 语义围绕 normalized mapping 建立,避免一边缓存 raw list、一边运行时再重复 normalize

### 5) Schema/docs/editor/skill must explain the `normalize` vs `extract` boundary

这次改动最容易失败的地方不是代码,而是认知混淆:

- `normalize`: 整个 source 返回值先整形
- `extract`: 当前 row value 内单字段取值

因此:

- schema `description` / `markdownDescription` 必须给出输入输出形状示例
- editor hover 必须沿用同样解释
- `scalim-yaml-dsl` skill 必须明确什么时候该用 `normalize`,什么时候只需要 `extract`

## Risks / Trade-offs

- [preset 过少仍需 wrapper] → v1 只做 `index_by_key`,其余 whole-result reshape 继续允许保留最薄 wrapper,后续再扩 preset。
- [duplicate key 语义不清] → 用 `on_conflict` 显式收口,默认 `error` 避免静默覆盖。
- [cache/raw instrumentation 认知变化] → 明确对外统一展示 normalized shape,并在文档中说明这是“执行期实际看到的结果”。
- [与 field-level extract 混淆] → 在 schema/docs/skill 中反复强调边界,并把两个 change 分开建模。

## Migration Plan

1. 在 source schema/model/parser/validator 中新增 `normalize` 配置,并限制其只出现在 `sources.*`.
2. 新增 source-level result normalizer 表示,不要直接塞进现有 `LoaderIr.extractor`.
3. 在 lookup source 的普通加载与 preload 缓存路径统一应用 normalize,确保缓存与非缓存行为一致。
4. 更新 schema / editor / docs / skill,加入 `index_by_key` 示例与 `normalize vs extract` 边界说明。

## Open Questions

- `normalize_fn` 未来是否直接采用受 allowlist 约束的 Python 引用,还是继续优先 declarative preset?
- v2 是否需要支持 `from_path` 这类“先从 envelope 里取出 list 再 index”的扩展,还是继续鼓励最薄 wrapper?
