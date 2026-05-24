---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate workflow-preflight-runtime-only-diagnostics --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "workflow-preflight-runtime-only-diagnostics"
purpose: "为 `run_workflow(...)` 增加一个 engine 执行前的 preflight 阶段,用于运行一组“runtime-only 但可推理”的诊断（v1 仅覆盖 `validate_unique_field_names`）,并以 fail-fast 的方式把错误提前暴露为 workflow compile/config error。"
requirements[4]{req_id,title,statement}:
  r1,workflow preflight MUST run after effective policy merge but before workflow eng,"系统 MUST 在进入 workflow engine 调度前运行 workflow preflight: - **MUST** 在 workflow compile/preload（结构预加载）完成之后运行 - **MUST** 在 per-run patches 与 overrides 合并完成、具备 effective policy/outputs/resources 口径之后运行 - **MUST** 在 workflow engine（调度/执行）启动之前运行"
  r2,preflight v1 MUST reject duplicate effective field display names when validate_u,"当满足以下条件时,系统 MUST 在 preflight 阶段拒绝 duplicate effective field display names: - `validate_unique_field_names=True`（runtime policy / per-run patch 的 effective 值） - effective outputs 中存在需要 `header_fields_output_by=name` 且会写 header 的输出"
  r3,preflight checks MUST be managed as an explicit registry of inferable diagnostic,"为避免 scope creep 与入口遗漏，系统 MUST 将 workflow preflight 的检查项管理为显式 registry（SSOT 清单），并保证其中每个检查都满足“可推理子集”约束： - check MUST NOT 依赖 `$ctx` 或 init_vars 渲染结果 - check MUST NOT 依赖外部运行态（例如文件是否存在、sheet 是否存在） - check MUST 仅消费 structural preload 的结果 + per-run effective policy/outputs/resources 口径"
  r4,preflight MUST consume structural preload results and MUST NOT reload demand YAM,为减少入口分歧与避免“preload/compile 与 preflight 各自重新解析 demand YAML”带来的 drift，系统 MUST 让 preflight 消费 structural preload 的结果（例如已解析的 `DemandConfig`），并且 MUST NOT 在 preflight 阶段再次读取/解析 demand YAML 文件。
scenarios[9]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"preflight-failure-stops-workflow-before-engine",workflow 存在某个可推理的 preflight 失败,用户调用 `run_workflow(...)`,系统 MUST 直接 raise 并中止整个 workflow
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"duplicate-effective-field-display-names-fail-fast-in-preflig",某个 workflow run 的 demand fields 存在 duplicate effective field display names,用户调用 `run_workflow(...)`,"系统 MUST 在进入 engine 调度前 fail-fast 抛出错误"
  r2,"validate-unique-field-names-disabled-by-per-run-patch-skips-",workflow run A 的 demand fields 存在 duplicate effective field display names,用户调用 `run_workflow(...)`,系统 MUST NOT 因该诊断在 preflight 阶段失败
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"only-checks-in-the-registry-are-executed-during-preflight",workflow preflight 存在一个显式的 checks registry（清单）,用户调用 `run_workflow(...)` 且触发 preflight,系统 MUST 仅执行 registry 中登记的 checks
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"preflight-does-not-perform-demand-yaml-io",workflow structural preload 已获得某个 run 的 demand 结构信息,系统进入 preflight 阶段,preflight MUST 仅消费 preload 结果与 effective policy/overrides 口径
```
