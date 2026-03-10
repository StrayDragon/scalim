## ADDED Requirements

### Requirement: `params` hover documents `$runtime.*` and preload params behavior
Schema 生成器 MUST 在 `main_source.params` 与 `sources.*.params` 的 hover/markdownDescription 中清晰说明:
- `main_source.params` 作为 kwargs 直接透传给 main source loader
- `sources.<id>.params` 作为 loader kwargs 模板,在对应 loader 被调用时透传(包含 preload_forever 的预加载调用)
- `$runtime.<name>` 可用于引用运行期变量,并在编译期被解析为调用方提供的 `runtime_vars[<name>]`

#### Scenario: schema hover 不再声称 preload_forever 零参调用
- **WHEN** 生成 `demand.gen.json`
- **THEN** `sources.*.params` 的 markdownDescription MUST 不再包含“preload_forever 预加载调用为无参”的旧描述

