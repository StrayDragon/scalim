## Why

`src/scalim/dsl/yaml_dsl/workflow_compile.py` 当前约 1900 行,同时承担多项职责(资源 patch/overlay、需求节点与 DAG 构建、demand 预加载、outputs 选择与 write-node 注入、runtime options 解析/IR 构建等)。

这种“单文件多职责热点”会直接带来:
- 单元测试困难(需要构造大量上下文才能覆盖某个小规则)
- review 成本高,变更容易误伤无关逻辑
- 后续与 `runtime/compiler.py` 的 SSOT 合并更难推进

你在第 3 点希望我给出更好的建议。我的建议是: **先用模块拆分把职责边界做出来,再在边界上做更深的去重/语义治理**。拆分本身不改变行为,但会显著降低后续改造的返工风险。

## What Changes

- 将 `workflow_compile.py` 按职责拆分为若干内部子模块,保留原有公开入口函数名/导入路径(对外无行为变化):
  - `workflow_compile_resources.py`: books/files 资源 patch/overlay 与资源 IR 构建
  - `workflow_compile_graph.py`: runs -> demand nodes + edges + slots 的 DAG 构建
  - `workflow_compile_outputs.py`: effective outputs 选择、output_extras、default book binding、write-node 构建与依赖注入
  - `workflow_compile_options.py`: runtime options 的 normalize/validate 与 options IR 构建
  - `workflow_compile.py`: 仅保留 orchestrator glue(`compile_workflow_ir`)与少量薄封装
- 拆分过程中同步建立“关键路径地图”(模块 docstring/注释): 哪些函数是 parse-only,哪些函数会触发 filesystem IO,哪些函数依赖 runtime policy。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `governance-module-organization`: 对 `workflow_compile.py` 这种热点模块建立更强的职责拆分约束与可测试边界。

## Impact

- 受影响代码:
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py`
  - 新增 `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_*.py` 子模块(或等价分包)
- 受影响测试:
  - 现有测试应保持通过;拆分后可补充更细粒度的 unit tests 覆盖 extracted rules
- 依赖关系:
  - 建议在 `c4-dsl-resource-override-ssot` 之后实施(先收敛 override SSOT,再拆分会更省力)
