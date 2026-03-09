## 1. Runtime Vars Injection (`$runtime.*`)

- [ ] 1.1 扩展 by_yaml runtime API: 为 `RunOptions` 与 `run/compile` 增加可选 `runtime_vars`,并保持官方入口 `scalim.dsl.by_yaml` 的稳定 re-export 不破坏.
- [ ] 1.2 在共享 params template compiler 中实现 `$runtime.<name>` 占位符解析: 仅对 exact-match string 做替换,并将结果编译为 opaque literal nodes
- [ ] 1.3 缺失 runtime var 时 fail-fast: 错误信息包含配置路径(例如 `sources.foo.params.params.bar`),并补回归测试覆盖典型缺失路径.
- [ ] 1.4 增加保留键冲突回归测试: `runtime_vars` 注入的 dict/list 中即使出现 `"$keys"`/`"$rows"` 结构,也必须按普通 literal 透传

## 2. preload_forever Params Semantic Convergence

- [ ] 2.1 为 source/main_source 引入共享 compiled params template representation,避免 preload/ref-load 分别维护 raw params 副本.
- [ ] 2.2 更新 preload 执行路径: `Pipeline._preload_cached_sources()` 通过共享 template render kwargs(为空时保持零参调用),并确保 instrumentation 记录的 params 与真实调用一致.
- [ ] 2.3 增加回归测试: `cache_mode=preload_forever` + `sources.<id>.params` 时 loader 确实收到 kwargs,且缓存命中路径不重复调用.

## 3. Schema + Docs Drift Fix

- [ ] 3.1 更新 `params` 的 schema hover 文案: 移除“preload_forever 不透传 params”的旧描述,补充 `$runtime.*` 说明;运行 `just gen-yaml-dsl-schema` 并通过 drift 测试.
- [ ] 3.2 更新 DSL reference 文档(例如 `artifacts/skills/scalim-yaml-dsl/references/dsl-reference.md`)补充 `runtime_vars` 与 `$runtime.*` 示例,并同步 preload params 行为说明.
- [ ] 3.3 运行 `openspec validate --all --strict --no-interactive` 与 `just openspec-check` 确认规范与脱敏规则通过.
