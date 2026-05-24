---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate yaml-dsl-demo-scenarios-suite --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "yaml-dsl-demo-scenarios-suite"
purpose: "维护一组 YAML DSL 场景库（fixtures），覆盖电商/广告/客服三类域，并纳入自动化回归测试范围，确保 DSL 能力与实现持续对齐。"
requirements[3]{req_id,title,statement}:
  r1,YAML DSL 场景库必须覆盖电商/广告/客服三类域,"系统 MUST 在场景库目录下维护一组 YAML DSL 场景库（fixtures），第一版至少包含三类域： - 电商（ecommerce）：以 canonical demand YAML 为核心（路径由其它规范约束保持稳定） - 广告（ads）：至少 1 份 demand YAML（可选 workflow） - 客服（support）：至少 1 份 demand YAML（可选 workflow） 场景库的 YAML MUST 以最新 schema 为基准编写，并在文件头部包含 YAML LSP schema modeline。"
  r2,场景库 YAML 必须纳入 examples gate 并通过校验,"系统 MUST 将场景库 YAML 纳入 examples gate 的确定性回归范围，并满足： - demand YAML：通过 DSL CLI 校验 - workflow YAML：通过 schema-only 校验（显式指定 workflow schema）"
  r3,capability coverage matrix 必须可审计并以 schema 为准,"系统 MUST 提供一个可检查的 capability coverage matrix 文件，用于将最新 schema 的关键能力点映射到： - 覆盖该能力点的 YAML 文件路径 - 覆盖该能力点的章节/对拍断言入口 该矩阵 MUST 以 demand/workflow schema 为唯一基准。"
scenarios[6]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"ads-support-场景-yaml-存在",场景库目录已初始化,维护者检查 ads 与 support 子目录,每个目录 MUST 至少存在 1 个 `*.yaml` demand 文件
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"场景库-yaml-在-gate-中可校验通过",场景库 YAML 已就位,开发者运行 examples gate,runner MUST 执行对场景库 YAML 的校验/运行对拍
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"coverage-matrix-文件存在",场景库目录已初始化,维护者检查场景库根目录,MUST 存在一份 coverage matrix 文件且内容可读
```
