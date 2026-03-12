# Plan F: Split into `template` (static spec) + `run` (runtime overrides)

## One-liner

把“可复用的报表模板(结构/血缘/字段)”与“每次运行的参数/输出/可观测性开关”拆开,减少 `$runtime.*` 与 overrides 的心智负担,同时更贴近真实使用方式(同一模板多次运行)。

## Proposed shape (schema-level)

```yaml
template:
  name: <str>
  description: <str?>
  batch_size: <int|null?>
  sources/joins/derive/...: <static>
  output:
    format: csv|excel
    select: [...]

run:
  vars: {<k>: <v>}                # runtime_vars
  output:
    path: <str?>                  # per-run output path
    encoding/streaming/...: <optional overrides>
  observability/guardrails/retry: <optional per-run toggles>
```

## What becomes simpler

- 模板部分不需要写 `$runtime.*`(也不需要解释 `$runtime.*` 到底是“模板语法”还是“字符串魔法”)
- “把 YAML 当模板 + Python 调用侧 overrides.output.*”的最佳实践被语言层面固化
- 对 agent 的交付更清晰: “我改了 template 还是改了 run”

## Trade-offs

- 对只跑一次的小 YAML 会显得更长
- schema/validator 需要把 template/run 合并成一次运行的 execution request(实现复杂度上升)

