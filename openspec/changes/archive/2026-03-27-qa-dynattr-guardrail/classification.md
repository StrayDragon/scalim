# dynattr 命中分类（基线）

基线生成方式: `uv run scripts/check-dynattr.py --report .tmp/artifacts/dynattr.report.txt`（同时写入 `.tmp/artifacts/dynattr.report.json`）

基线摘要（2026-03-26）:
- total=154
- block=145
- allow=9
- calls: getattr=145, hasattr=9

## 目录/职责分布（按命中数）

> 以 `.tmp/artifacts/dynattr.report.json` 的 `summary.by_file` 聚合得到。

- `src/scalim/dsl`: 62
- `src/scalim/ob`: 46
- `src/scalim/cli`: 15
- `src/scalim/execution`: 13
- `src/scalim/planning`: 7
- `src/scalim/workflow`: 6
- `src/scalim/utils`: 3
- `src/scalim/spec`: 2

## 属性表达式形态（静态化 vs 动态边界）

- **字面量字符串属性名**: 143/154（≈93%）
  - 典型: `getattr(x, "path")` / `getattr(x, "__origin__")`
  - 候选方向: 若对象类型/契约明确,优先改为直接属性访问或用显式接口抽象.
- **动态属性名**: 11/154（≈7%）
  - 典型: `attr_name` / `func_name` / `handler_name` / `field_name` / `str(value.value)`
  - 候选方向: 更可能需要结构性重构（dispatch table/registry）或显式 allow 注释并写清理由.

动态属性名热点（每类各 1 次,合计 11 次）:
- `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`: `attr_name`
- `src/scalim/dsl/by_yaml/runtime/references.py`: `attr_name` / `func_name`（当前已 allow）
- `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`: `str(value.value)`
- `src/scalim/dsl/by_yaml/workflow_config.py`: `attr_name`
- `src/scalim/ob/_internal/manager_registry.py`, `src/scalim/ob/observer.py`: `handler_name`
- `src/scalim/utils/relation_diagnostics.py`: `field_name`

## 热点文件（Top 10）

- 20 `src/scalim/ob/presets/viz/output_composition.py`
- 15 `src/scalim/cli/yaml_dsl.py`
- 15 `src/scalim/dsl/by_yaml/workflow_entrypoints.py`
- 14 `src/scalim/ob/presets/viz/workflow.py`
- 12 `src/scalim/dsl/by_yaml/config_parsing/validator.py`
- 10 `src/scalim/dsl/by_yaml/schema_dsl/builder.py`
- 7 `src/scalim/ob/_internal/manager_registry.py`
- 6 `src/scalim/dsl/by_yaml/config_parsing/jsonschema_issues.py`
- 6 `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- 5 `src/scalim/execution/workflow_cache_pool.py`

## 收口建议（渐进、可验证）

1. **先做“低风险静态化”**（任务 2.1）
   - 目标: 把 `getattr(x, "literal")` 变成 `x.literal` 或更明确的接口调用.
   - 前提: 该属性在运行时确实存在,且可以通过类型/接口表达（`Protocol`/dataclass/ABC 等）.
2. **把第三方/无 stubs 的动态边界显式化**（任务 2.2）
   - 目标: 对确属必要的点加 `# pragma: allow-dynattr <prefix>: <detail>`，避免隐式扩散.
   - 示例候选: CLI/YAML 错误对象字段读取（依赖第三方异常对象结构时）.
3. **对 dispatch/registry 场景优先改为表驱动**（任务 2.1/2.2）
   - 目标: 避免通过 `handler_name` 拼接再 `getattr` 的隐式分发.
4. **每改一个文件就做最小验证**
   - 建议顺序: `uv run basedpyright <file>` → `uv run pytest --no-cov <focused tests>`（必要时再跑 `just qa`）.
