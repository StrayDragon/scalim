# 2026-04-08: yaml-dsl-api-naming-alignment

## 变更摘要

本批次做一次性 **BREAKING** 命名收敛,目标是让 YAML DSL 的 Python public API 在“模块路径 / 名词 / 参数名”层面更一致、更可搜索：

- canonical public facade: `scalim.dsl.by_yaml` → `scalim.dsl.yaml_dsl`
- **(后续变更已覆盖)** `RunOptions` 已拆分为 `DemandRunOptions` / `WorkflowRunOptions`；`run_workflow` 变为 options-only
- workflow per-run patch 更新为:
  - `WorkflowRunOptionsPatch` → `WorkflowNodePatch`
  - `run_options_patches_by_run_id` → `WorkflowRunOptions.patches_by_run_id`

本批次 **不提供兼容层/弃用期**：旧路径与旧名字会直接失效.

对应 llmanspec change:
- `llmanspec/changes/archive/2026-04-07-c1-yaml-dsl-api-naming-alignment/` (归档后路径)

## Migration Checklist

### 1) 全局替换导入路径

将所有导入从旧 facade 切到新 facade:

```python
# Before
from scalim.dsl.by_yaml import RunOptions, run, compile, run_workflow

# After
from scalim.dsl.yaml_dsl import DemandRunOptions, WorkflowRunOptions, run, compile, run_workflow
```

同理,curated stable modules 也统一切换:

- `scalim.dsl.by_yaml.workflow` → `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.by_yaml.workflow_types` → `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.by_yaml.workflow_paths` → `scalim.dsl.yaml_dsl.workflow_paths`
- `scalim.dsl.by_yaml.tools` → `scalim.dsl.yaml_dsl.tools`

### 2) workflow per-run patch 重命名

`run_workflow` 的 per-run patch 参数与类型同步更新:

```python
# Before
from scalim.dsl.by_yaml.workflow_types import WorkflowRunPatch

_ = run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(...),
    run_patches_by_id={
        "A": WorkflowRunPatch(batch_size=5000),
    },
)

# After
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowNodePatch

_ = run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=...),
            runtime=DemandRunRuntimeOptions(batch_size=2000),  # 全局默认
        ),
        patches_by_run_id={"A": WorkflowNodePatch(batch_size=5000)},
    ),
)
```

### 3) 更新 schema 文件路径(仅当你在仓库内硬编码路径)

若你在 docs/脚本/校验命令中显式写死了 schema 文件路径,更新为:

- `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
- `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`

示例:

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>
```

### 4) 跑一遍门禁与回归

仓库内建议至少跑:

```bash
just gen-docs
just gen-agent-skill
just llmanspec-check
just qa
```

若你是下游仓库:
- 优先 `rg -n "scalim\\.dsl\\.by_yaml\\b" -S .` 找到旧导入
- 再跑你的 YAML 校验/运行回归用例
