## Why

`extensions` 一旦落地,多个子系统(validator/parser/compiler/executor/CLI)都需要读取同一份“扩展视图”。
如果每处各自解析/合并,会造成:

- 行为漂移(校验/编译/执行对扩展的理解不一致)
- 错误上下文不一致,排障困难
- 产物无法对拍(同一 YAML 在不同入口得到不同摘要)

因此需要一个编译期 SSOT: `ExtensionHost`。

## What Changes

本 change 提供 extensions 的“宿主与合并”核心能力(不引入各扩展点的具体运行语义):

- 定义 `ExtensionBundle`/`ExtensionHost` 的 runtime contract(贡献 registries + transformers/analyzers/components + summary/provenance)
- 统一 `ref + config` 的解析/实例化/调用约定(兼容函数/类/工厂;支持可选 ctx)
- 复用 `SecurePythonReferenceResolver` + allowlist 解析扩展引用(含相对引用;错误带 `yaml_path/ref/stage`)
- 将 direct config 与 `extensions.bundles` 的贡献按确定性顺序合并,并实现可配置的冲突策略(默认 error)
- 支持从 YAML `extensions.components` 装配额外 components(Observer/Hook),并复用 `split_components` 做 fail-fast 类型校验

示例(这里只描述 host 能解析并形成扩展视图;compute/output/aggregate 等如何“生效”由后续 changes 接入):

```yaml
extensions:
  enabled: true
  api: 1
  compute:
    functions:
      safe_div: myapp.scalim_ext.compute:safe_div
  bundles:
    - ref: myapp.scalim_ext:bundle_v1
      config: {profile: dev}
```

## Capabilities

### New Capabilities

- `yaml-dsl-extensions` (core host + bundles merge + components injection)

## Dependencies

- 依赖 `yaml-dsl-extensions-schema`: schema/loader 需要先能承载 `extensions`(避免 schema-only 与 runtime loader 直接失败)

## Impact

- 影响 YAML compile pipeline 的装配边界: `src/scalim/dsl/by_yaml/**`
- 不改变无 `extensions` YAML 的行为
- 不要求本 change 立即落地 compute/output/aggregate/transform/analyze 的完整运行语义(由后续 changes wire-up)
