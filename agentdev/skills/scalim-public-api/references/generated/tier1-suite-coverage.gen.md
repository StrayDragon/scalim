# Tier1 Coverage Map (examples ↔ pytest)

此文档由 `scripts/gen-public-api-skill.py` 自动生成.

## Commands
- Suite drift gate: `just check-public-api-suite-coverage`
- Run examples: `just examples`
- Run pytest public_api suite: `pytest -q tests/public_api/ --no-cov`
- Full gate: `just qa`

## Pytest Selected Chapters (8):
- `ch130_public_api_dsl_by_yaml`
- `ch150_public_api_planning`
- `ch160_public_api_execution`
- `ch165_public_api_resources`
- `ch170_public_api_ob`
- `ch180_public_api_hooks_events`
- `ch182_public_api_event_type_groups`
- `ch184_public_api_sinks_pandas`

## Tier1 Modules Coverage (17)

### `scalim.dsl.yaml_dsl`
- examples chapters (4): `ch130_public_api_dsl_by_yaml`, `ch135_public_api_key_normalization`, `ch163_public_api_output_write_layout_books`, `ch165_public_api_resources`
- pytest chapters (2): `ch130_public_api_dsl_by_yaml`, `ch165_public_api_resources`

### `scalim.dsl.yaml_dsl.tools`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.dsl.yaml_dsl.workflow`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.dsl.yaml_dsl.workflow_types`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.dsl.yaml_dsl.workflow_paths`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.spec.ir`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.workflow.loaders`
- examples chapters (1): `ch130_public_api_dsl_by_yaml`
- pytest chapters (1): `ch130_public_api_dsl_by_yaml`

### `scalim.planning`
- examples chapters (3): `ch150_public_api_planning`, `ch160_public_api_execution`, `ch162_public_api_output_write_layout`
- pytest chapters (2): `ch150_public_api_planning`, `ch160_public_api_execution`

### `scalim.execution`
- examples chapters (3): `ch160_public_api_execution`, `ch162_public_api_output_write_layout`, `ch180_public_api_hooks_events`
- pytest chapters (2): `ch160_public_api_execution`, `ch180_public_api_hooks_events`

### `scalim.ob`
- examples chapters (5): `ch130_public_api_dsl_by_yaml`, `ch162_public_api_output_write_layout`, `ch163_public_api_output_write_layout_books`, `ch170_public_api_ob`, `ch180_public_api_hooks_events`
- pytest chapters (3): `ch130_public_api_dsl_by_yaml`, `ch170_public_api_ob`, `ch180_public_api_hooks_events`

### `scalim.events`
- examples chapters (6): `ch130_public_api_dsl_by_yaml`, `ch162_public_api_output_write_layout`, `ch163_public_api_output_write_layout_books`, `ch170_public_api_ob`, `ch180_public_api_hooks_events`, `ch182_public_api_event_type_groups`
- pytest chapters (4): `ch130_public_api_dsl_by_yaml`, `ch170_public_api_ob`, `ch180_public_api_hooks_events`, `ch182_public_api_event_type_groups`

### `scalim.events.type_groups`
- examples chapters (1): `ch182_public_api_event_type_groups`
- pytest chapters (1): `ch182_public_api_event_type_groups`

### `scalim.sinks`
- examples chapters (4): `ch160_public_api_execution`, `ch162_public_api_output_write_layout`, `ch180_public_api_hooks_events`, `ch184_public_api_sinks_pandas`
- pytest chapters (3): `ch160_public_api_execution`, `ch180_public_api_hooks_events`, `ch184_public_api_sinks_pandas`

### `scalim.sinks.memory`
- examples chapters (2): `ch160_public_api_execution`, `ch180_public_api_hooks_events`
- pytest chapters (2): `ch160_public_api_execution`, `ch180_public_api_hooks_events`

### `scalim.sinks.pandas`
- examples chapters (1): `ch184_public_api_sinks_pandas`
- pytest chapters (1): `ch184_public_api_sinks_pandas`

### `scalim.shortcuts.resources`
- examples chapters (2): `ch130_public_api_dsl_by_yaml`, `ch165_public_api_resources`
- pytest chapters (2): `ch130_public_api_dsl_by_yaml`, `ch165_public_api_resources`

### `scalim.shortcuts.resources.outputs`
- examples chapters (2): `ch130_public_api_dsl_by_yaml`, `ch165_public_api_resources`
- pytest chapters (2): `ch130_public_api_dsl_by_yaml`, `ch165_public_api_resources`
