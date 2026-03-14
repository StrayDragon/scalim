# notebooks/marimo Coverage Matrix (SSOT)

本文件用于将“能力点”明确映射到可运行的示例/回归入口,避免示例与门禁碎片化.

## Public API (re-export) 覆盖

| Public module | Notebook | SSOT runner | Pytest |
| --- | --- | --- | --- |
| `scalim.dsl.by_yaml` | `notebooks/marimo/example_public_api/dsl_by_yaml.py` | `packages/scalim-misc/src/scalim_misc/examples/public_api/dsl_by_yaml.py` | `tests/test_example_public_api_suite.py` |
| `scalim.spec.ir` | `notebooks/marimo/example_public_api/spec_ir.py` | `packages/scalim-misc/src/scalim_misc/examples/public_api/spec_ir.py` | `tests/test_example_public_api_suite.py` |
| `scalim.planning` | `notebooks/marimo/example_public_api/planning.py` | `packages/scalim-misc/src/scalim_misc/examples/public_api/planning.py` | `tests/test_example_public_api_suite.py` |
| `scalim.execution` | `notebooks/marimo/example_public_api/execution.py` | `packages/scalim-misc/src/scalim_misc/examples/public_api/execution.py` | `tests/test_example_public_api_suite.py` |
| `scalim.ob` | `notebooks/marimo/example_public_api/ob.py` | `packages/scalim-misc/src/scalim_misc/examples/public_api/ob.py` | `tests/test_example_public_api_suite.py` |

## YAML DSL 能力点覆盖(示例/回归)

| Capability / change | Coverage entry |
| --- | --- |
| `yaml-dsl-outputs` | `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` + `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/output_composition.py` |
| `yaml-dsl-workflow` | `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture.yaml` + `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/workflow_yaml.py` + `packages/scalim-misc/src/scalim_misc/examples/public_api/dsl_by_yaml.py` |
| `yaml-source-normalize-shapes` | `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`(normalize 片段) + `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/yaml_dsl.py` |
| `derived-outputs-set-aggregations` | `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/derived_set_aggregations.py` + `packages/scalim-misc/src/scalim_misc/demo_big_data_report/derived_set_aggregations_demo.py` |
| `yaml-dsl-micro-tunes` | `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`(runtime_vars/指令节点相关) |
| `yaml-dsl-output-fields-alias` | `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` + `tests/test_yaml_dsl_output_fields_alias.py` |
