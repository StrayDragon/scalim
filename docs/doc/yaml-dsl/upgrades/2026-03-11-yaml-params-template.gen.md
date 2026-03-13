<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- artifacts/skills/scalim-yaml-dsl/references/upgrades/2026-03-11-yaml-params-template.md
-->
# 2026-03-11: yaml-params-template

## 变更摘要

这次升级把 loader 的调用参数语义收敛到一个入口: `params` kwargs 模板(支持在任意嵌套位置注入运行时值),并引入 `runtime_vars` 作为编译期注入来源。

- `main_source.params` / `sources.<id>.params` 统一视为“kwargs 模板”
- 新增模板指令节点:
  - `{$keys: {as: set|list}}`: 注入 lookup keys
  - `{$rows: {cache_mode: batch|none}}`: 注入 batch rows(并影响调度与复用语义)
- 新增 `runtime_vars` 注入与 `{$runtime: <name>}` 指令节点(编译期解析;不做子串插值)
- **BREAKING**: `bind` / `to_bind` 已从稳定 YAML authoring surface 移除(出现即 fail-fast)
- **BREAKING**: `cache_mode: preload_forever` 的预加载语义收敛:
  - 若 `sources.<id>.params` 非空: 预加载透传渲染后的 kwargs
  - 若为空: 预加载保持零参调用

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
- `openspec/changes/archive/2026-03-11-yaml-loader-params-template/`

对应主规范(节选):
- `openspec/specs/demand-dsl/spec.md`
- `openspec/specs/source-relations/spec.md`
- `openspec/specs/yaml-dsl-schema/spec.md`

## 破坏性变更(Breaking)

### 1) `bind` / `to_bind` 不再允许

旧写法(不再允许,出现即 fail-fast):

```yaml
sources:
  customers:
    bind:
      use_keys:
        param: ids
```

或:

```yaml
relations:
  r1:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        to_bind:
          use_keys:
            param: ids
```

新写法(推荐):

```yaml
sources:
  customers:
    params:
      ids: {$keys: {as: set}}
```

### 2) `preload_forever` 开始透传 `sources.<id>.params`

如果你以前写了:

```yaml
sources:
  promotions:
    cache_mode: preload_forever
    params:
      field_keys: [promotion_id, promotion_name]
```

旧行为是“预加载不透传 params”(params 被忽略)。

新行为是“只要 params 非空就透传 kwargs”,因此你的 loader 必须接受对应参数名(例如 `field_keys=...`)。

## 迁移步骤

### Step 0: 先跑校验定位问题

- `uv run scalim-cli yaml-dsl schema validate <file.yaml> --strict`
- `uv run scalim-cli yaml-dsl validate <file.yaml> --strict`

### Step 1: 把 `bind/to_bind` 迁移为 `params` 模板指令

`keys` 模式:

```yaml
params:
  ids: {$keys: {as: list}}
```

`rows` 模式(注意 barrier 语义):

```yaml
params:
  rows: {$rows: {cache_mode: batch}}
```

提示:

- `$keys.as=list` 会输出稳定顺序列表; composite key 注入为 tuple 元素
- `$rows` 会触发 rows barrier: `parallel_mode="adaptive"` 下该层 LoadRef 串行执行
- `$rows.cache_mode=none` 会禁用批次内 relation 复用(每个字段各自调用 loader)

### Step 2: 用 `runtime_vars` 注入运行期变量

YAML:

```yaml
main_source:
  params:
    end_dt: {$runtime: end_dt}
```

Python:

```python
from datetime import datetime
from scalim.dsl.by_yaml import run

result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    runtime_vars={"end_dt": datetime(2024, 1, 31)},
)
```

提示:

- 仅解析 `{$runtime: <name>}` 指令节点(单键映射);不做子串插值
- 缺失 runtime var 会在编译期 fail-fast,错误信息包含配置路径(例如 `sources.foo.params.params.end_dt`)

## 常见报错与修复

- `Legacy YAML syntax is not supported: 'sources.<id>.bind'` / `...to_bind...`
  - 修复: 按错误中的示例把绑定迁移到 `sources.<id>.params` 的 `$keys/$rows` 指令节点
- `Missing runtime var: <name> (path=...)`
  - 修复: `run(..., runtime_vars={...})` 补齐该 key,或把 YAML 中的占位符改为普通字面值
