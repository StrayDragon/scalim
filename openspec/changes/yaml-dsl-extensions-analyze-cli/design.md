## Context

该 change 解决 “analyzer + CLI 开关” 的治理问题:
- 默认 validate 不执行用户代码
- 显式 resolve 后提供可对拍的扩展摘要与 analyzers issues

umbrella 设计见:

- `openspec/changes/yaml-dsl-extensibility-preproposal/design.md` 的 Decision 10/10.1/10.2

## Decisions

1) 默认行为:
- `yaml-dsl validate` 默认不解析/导入/执行 extensions
- 当 YAML 出现扩展语法但未 resolve 时,输出可行动提示(如何开启 + allowlist)

2) 显式 resolve:
- `--resolve-extensions` 启用扩展解析/执行
- allowlist 必须显式提供;`--trusted` 作为快捷通配符并输出风险提示

3) analyzer 执行阶段:

- 至少支持 `raw` 阶段(imports 展开后、validator 前)执行 analyzers,用于 lint/模板检查/禁用模式检查等
- 可选支持 `compiled` 阶段(已有 `DemandConfig/DemandIr/ExecutionRequest` 后)执行 analyzers,用于“计划/输出/依赖”的一致性检查与建议
- analyzers 仅在 `--resolve-extensions` 模式下执行

4) analyzer contract:

- analyzer 通过 Python 引用加载(受 allowlist 约束)
- analyzer MUST 为只读(不得修改 raw/config/IR/request 的最终语义)
- analyzer 输出为结构化 issues(可选携带 meta),供 CLI/CI/IDE 消费
- analyzer 执行失败时:
  - 默认建议 fail-fast 并给出可行动错误(含 ref + stage)
  - 可通过 `extensions.conflicts.analyzer_failure`(或等价配置)降级为 warning(由 host-core/schema 提供容器,本 change 定义语义)

5) issues shape(一次性定型):

为保证 CLI/CI/IDE 稳定消费,issues 结构建议固定为:
- `severity`: `error|warning`
- `message`: string
- `path`: 可选,指向 YAML logical path(若可得)
- `ref`: analyzer ref
- `stage`: `raw|compiled`(或等价稳定字符串)
- `code`: 可选,稳定错误码(便于 CI ignorelist/统计)

CLI JSON 输出 MUST 新增字段(不破坏现有 `errors/warnings`):
- `extensions_errors: Issue[]`
- `extensions_warnings: Issue[]`
- 可选: `extensions_summary: object`

## Non-Goals

- 不在本 change 中落地 output registry/custom aggregates 等具体运行扩展(由其它 changes 处理)
