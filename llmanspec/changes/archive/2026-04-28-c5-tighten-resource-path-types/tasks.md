## 1. Introduce SSOT Types

- [x] 1.1 新增 `InitVarRef`(或等价对象)与 `PathNode` 类型别名,放在 YAML DSL runtime 的稳定模块位置
- [x] 1.2 将 `BookConfig.path` / `FileConfig.path`/相关字段从 `Any` 收紧为 `Optional[PathNode]` 或 `PathNode`

## 2. Migrate Parse Layer

- [x] 2.1 修改 demand runtime compiler 的 `_parse_*_path_or_init_var` 使其返回 `PathNode`(将 dict 节点转换为 `InitVarRef`)
- [x] 2.2 修改 workflow config parser 的 `_parse_path_or_init_var` 同步产出 `PathNode`

## 3. Migrate Resolve + Consumers

- [x] 3.1 修改 `runtime/output_path_resolve.py` 使用 `InitVarRef` 分支替代 dict 分支
- [x] 3.2 迁移关键使用侧(按影响面从小到大):
  - `runtime/output_composition_yaml.py`
  - `workflow_compile.py`
  - `workflow_entrypoints.py`
- [x] 3.3 清理残留的 dict/cast/pragma,把必要的边界窄化集中在 parse/resolve

## 4. Tests

- [x] 4.1 补齐/调整回归测试: `{$init_var: ...}` 路径在 demand/workflow 两条链路下仍能正确解析
- [x] 4.2 增加类型相关的单测/静态检查断言(至少确保关键字段不再是 `Any`)

## 5. Verification

- [x] 5.1 运行 `just qa`
- [x] 5.2 运行 `just openspec-check`
