## Context

当前 `demand` YAML 顶层存在两个“更像 runtime policy”的字段:

- `include_full_error_message`: 控制 output composition 的 meta/audit 等输出是否写入完整异常信息(可能包含敏感内容)。
- `validate_unique_field_names`: 控制“字段有效展示名(effective display name)全局唯一”的预检查开关;默认启用,用于在 `header_fields_output_by: name` 且会输出表头时 fail-fast。

这两个字段一旦被下游复制进业务 YAML,会把“环境/安全/治理策略”混进需求本体,并与现有 runtime policy 边界(`failure_policy`/`guardrails`/`retry`/`batch_size` 等已迁出)不一致。

## Goals / Non-Goals

**Goals:**
- 将 `include_full_error_message` / `validate_unique_field_names` 从 YAML stable authoring surface 迁出到 Python/CLI runtime entrypoints,并提供默认值。
- 对仍出现在 YAML 中的字段 fail-fast,并提供明确迁移提示(避免静默忽略或暗箱覆盖)。
- `run demand` 与 `run workflow` 复用同一套 demand runtime-policy typed surface,避免两条入口演进分叉。
- 同步更新 OpenSpec / docs / examples / tests,确保 schema 与文档一致且无 drift。

**Non-Goals:**
- 不引入新的 YAML 语法短写(例如 `$keys/$rows` 或 `lookup_cast` 的 scalar 短写)。
- 不改变 error redaction/unique name validation 的核心业务语义(仅迁移配置入口与默认值承诺)。
- 不提供长期兼容/双写期;本变更为明确的 authoring surface 收敛(破坏性变更)。

## Decisions

### 1) 以 runtime entrypoints 为唯一策略入口

决策: 在 runtime typed surface 中新增/收敛两个策略开关:
- `include_full_error_message: bool = False`
- `validate_unique_field_names: bool = True`

并由 `scalim.dsl.by_yaml.runtime.entrypoints.run` 与 `scalim.dsl.by_yaml.workflow_entrypoints.run_workflow` 的公共 `RunOptions`(或其组合对象)统一承载与传递。

理由:
- 与 `failure_policy`/`meta`/`audit` 等已迁出字段保持一致。
- 让策略可按环境装配/注入(例如 CI/公开环境强制脱敏,本地排障允许全文)。
- 避免 YAML 被复制粘贴后“策略失控”。

替代方案:
- 继续允许 YAML 字段并做 deprecate/warn: 不满足治理目标,且会形成长期双入口维护成本。
- 把字段挪到 YAML 的某个 `policy:` 子对象: 仍然在 authoring 文件中,无法解决复制传播问题。

### 2) YAML 侧 fail-fast,并给出迁移提示

决策: loader/validator 在解析到这两个顶层键时直接报错(含 path),错误信息包含:
- 该字段已迁出 YAML mainline
- 推荐的 runtime entrypoint 参数名/用法

理由:
- 避免“看似生效但实际被 runtime 覆盖/忽略”的灰色行为。
- 让迁移成本一次性显式暴露,便于下游批量修复。

### 3) Schema / docs 以生成 SSOT 驱动

决策:
- 从 `src/scalim/dsl/by_yaml/schema_dsl/models/demand.py` 的 schema SSOT 中移除这两个字段(或标记为 `schema_omit()` 并在 loader 层拒绝)。
- `src/scalim/dsl/by_yaml/schema/*.gen.json`、`docs/doc/yaml-dsl/schema-reference.gen.md` 等生成物不手改,通过 `just gen-docs` 刷新。

理由:
- 维持 doc governance 与 drift gate 规则。
- 保证 LSP/schema hover 与真实实现一致。

## Risks / Trade-offs

- [破坏性变更] 下游 YAML 若包含这两个字段将无法通过 validate/运行。
  - 缓解: 提供清晰的 fail-fast 文案 + 更新 docs/examples + 给出 Python/CLI 参数迁移示例。
- [入口 API 变更] runtime entrypoints 增加参数/typed config,需要同步维护 `run` 与 `run_workflow`。
  - 缓解: 以 `RunOptions` 为单一传递通道;workflow 复用 base_options 自动继承。
- [规范一致性] 现有 `yaml-dsl-schema` spec 明确要求暴露 `validate_unique_field_names`。
  - 缓解: 同步修改 `openspec/specs/yaml-dsl-schema/spec.md` 与 `openspec/specs/yaml-dsl-runtime-policy-boundary/spec.md` 以反映新边界。

## Migration Plan

1. 实现 runtime entrypoints 新策略开关(typed surface + 注入到编译/输出组合路径)。
2. loader/validator 增加 fail-fast: YAML 出现旧字段时报错并指向迁移方式。
3. 更新 OpenSpec(边界 + schema 要求)并运行 `just openspec-check`。
4. 更新 docs/examples/notebooks/tests,并通过 `just gen-docs` 刷新所有生成物。
5. 运行 `just qa` 通过质量门禁。

## Open Questions

### Resolved

- runtime 参数形态: 以单个 typed 参数承载两个开关,并保持字段名与原 YAML key 对齐:
  - `demand_diagnostics: DemandDiagnosticsPolicy`
    - `include_full_error_message`
    - `validate_unique_field_names`
  - `run_workflow` 不新增额外“补丁入口参数”,而是通过既有 `run_patches_by_id: Mapping[str, WorkflowRunPatch]` 承载 per-run 覆盖。
    - 具体做法: 扩展 `WorkflowRunPatch` 字段并在 `_apply_workflow_run_patch` 中注入到 `RunOptions`。
    - 为避免 per-run patch 意外覆盖全局设置,需要支持字段级别的三态 merge(UNSET=继承)。
- `validate_unique_field_names` 行为: 维持旧行为,仅改变配置入口。
  - 默认值继续为 `true`
  - 校验触发条件仍由既有统一 write 语义决定(仅当会输出表头且 `header_fields_output_by=name` 时才会触发检查)
  - `validate_unique_field_names=false` 的语义保持为“跳过该预检查”(不新增额外限制/收紧)
