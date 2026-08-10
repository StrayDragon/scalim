# Tasks: yaml-dsl-ensure-keys

> **范围**：仅 `outputs[*].ensure_keys`。field-level `default` 任务已由 `2026-04-18-c0-yaml-dsl-ref-miss-default-cases` 完成，不在此勾选。

## 1. Schema SSOT & Authoring

- [ ] 1.1 在 `OutputTargetConfig` SSOT 增加 `ensure_keys`（`src/scalim/dsl/yaml_dsl/schema_dsl/models/outputs.py`）（DoD: schema 暴露 `outputs[*].ensure_keys`；仅与 `aggregate` 同出有意义）
- [ ] 1.2 补齐 hover/md：aggregate-only、`from`/`on`/`defaults` 边界（DoD: 文案与 proposal 一致）
- [ ] 1.3 `just gen-yaml-dsl-schema`（DoD: `demand.gen.json` / `workflow.gen.json` drift 干净；禁止手改 gen）

## 2. Parse & Strict Validation

- [ ] 2.1 解析 `outputs[*].ensure_keys`（demand loader / output parser）（DoD: 配置进入 typed config）
- [ ] 2.2 严格校验（DoD fail-fast）：
  - 无 `aggregate` 却写 `ensure_keys`
  - `from` 非已声明 source
  - `on` 若出现则与 `aggregate.group_by` 完全一致
  - `defaults` 的 key ⊆ 该 output 输出字段（group_by + aggregate.fields + 编排 fields）
- [ ] 2.3 校验测试（DoD: 上列负例稳定报错）

## 3. Compile → Runtime Spec

- [ ] 3.1 YAML→IR/composition：derived target 携带 ensure_keys（`output_composition_yaml.py` 等）（DoD: 运行时可取到 from/on/defaults）
- [ ] 3.2 维度键提供：从 `from` source mapping 取 keys；规范化口径与该 derived output 的 key_normalization 一致（DoD: int/str 对齐不误补）
- [ ] 3.3 **preload 契约**：`SourceCache.preload_forever` / YAML `cache_mode: preload_forever` 时 MUST 走 PreloadCache，同 run 不二次 loader；多 output 同 `from` 应 memoize keys（DoD: 测试断言 loader 调用次数）

## 4. Finalize 补全实现

- [ ] 4.1 在 `AggregatingRowSink.close` / aggregator finalize 后应用补全（建议 `derived_outputs.py` 包装或等价插入点）（DoD: 缺失 group 出现补全行）
- [ ] 4.2 填充优先级：`defaults` > producer identity（count/sum/…→0；min/max→None）> `None`（含 rank/post）（DoD: 单测覆盖）
- [ ] 4.3 顺序：无 rank → group_by 稳定 merge；有 rank → 原序不变 + 补全行确定性 append（DoD: 对拍稳定）
- [ ] 4.4 诊断：`filled_count` / ratio 进 `aggregator.diagnostics()` → router meta/audit（高比例可 audit）（DoD: meta 可见）

## 5. Tests & Docs

- [ ] 5.1 单键 / 复合键 / defaults 覆盖 / key_normalization / rank 末尾追加 / preload 不重复加载（DoD: 全绿）
- [ ] 5.2 非生成示例 demand YAML（仅 ensure_keys；可与已有 `default` 示例并列但不混为本 change 范围）（DoD: 可复制复现）
- [ ] 5.3 若触及 injected docs：`just gen-docs`（DoD: 不手改 AUTOGEN）

## 6. Quality Gates

- [ ] 6.1 `just qa`（DoD: 无本 change 回归）
- [ ] 6.2 `just llmanspec-check`（DoD: sanitize/validate 干净；转正后用 llman SDD 门禁）
