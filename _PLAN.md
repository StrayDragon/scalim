• 总览（从可维护/可持续角度）

  - 这 13 个 changes 本质上分成 4 条“长期演进线”：① YAML DSL 安全边界收敛（c2/c20/c25/c80）② 文档/技能的 SSOT 与漂移门禁（c30）③ outputs 体系的 SSOT + 可测试分层（c40/c45/c50）④
    runtime 的诊断/模块化/性能（c35/c55/c60/c70/c75）。
  - 建议优先把“安全默认值 + 强诊断 + SSOT 护栏”立住，再做大重构/性能（否则后期回归定位成本会指数增长）。

  架构级方向（建议作为后续实现的统一口径）

  - 把“信任边界”做成显式 policy，而不是散落的 bool：现在 YAML 相关会同时触达 resolver（src/scalim/dsl/by_yaml/runtime/references.py:35）、模板预编译（src/scalim/dsl/by_yaml/
    config_parsing/template_precompile.py:10）、imports 路径（src/scalim/dsl/by_yaml/config_parsing/imports.py:71）、workflow demand 路径（src/scalim/dsl/by_yaml/
    workflow.py:250）。推荐未来用一个 YamlDslSecurityOptions/YamlPathPolicy 之类的“单点对象”承载并做统一校验（至少保证错误信息与默认值一致），避免 RunOptions 继续膨胀（src/
    scalim/dsl/by_yaml/runtime/contracts.py:60）。
  - 安全默认值 + 显式放宽 + 强告警（必要时二次确认）：c2/c20 都是典型脚枪，最佳实践是“默认 fail-fast 或默认 sandbox；要放宽必须显式 opt-in，并且有稳定 warning（日志/
    warnings.warn）”。
  - SSOT 先行 + 测试护栏先行：c40/c45/c50/c55 都是“漂移/复杂度治理”。可持续做法是：先用测试把现状固化成护栏，再拆分/重构，最后移除重复实现。
  - wants-gated 必须推进到调用点：只在 emit_* 里短路不够（例如 LoadRef 仍做 O(rows) 循环：src/scalim/execution/executor/operators/load_ref/executor.py:75）。

  建议的实施节奏（不一定等同于目录编号，但能最省维护成本）

  - Phase 0（安全基线 + 排障能力）：c2 → c20 → c25，并尽早穿插 c35（默认可见实验性提示）与 c75（PreloadCache 卡死诊断）。
  - Phase 1（outputs 可持续演进底座）：c40 → c45 → c50。
  - Phase 2（workflow 结构治理）：c55（建议在 c20/c25 之后做，避免同一位置反复改）。
  - Phase 3（性能 A→B→C）：c60（建议拆成 3 次独立可验收的落地节奏，哪怕仍归在一个 change 里）。
  - c30：建议在 Phase 0~1 之间尽早落地（越早把 docs/skill 片段改成注入与生成，后续越省心）。
  - c70/c80：偏“边界说明/特性扩展”，建议在安全边界（c25）稳定后再推进。