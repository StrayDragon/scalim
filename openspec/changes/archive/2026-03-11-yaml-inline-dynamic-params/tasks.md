## 1. 模板指令解析与渲染

- [x] 1.1 新增 typed params template compiler: 将 dict/list/scalar 编译为共享 template IR,识别 `$keys/$rows` 指令节点并为 literal/runtime 值打上编译期节点标记(保证 alias-safe)
- [x] 1.2 新增指令节点语义校验: 单 key mapping、options 类型与枚举值、`$keys/$rows` 互斥、非法上下文 fail-fast(错误包含配置 path)
- [x] 1.3 实现 `$keys.as=set|list`(默认 set)与 `$keys.as=list` 的稳定顺序(复用稳定排序 helper)
- [x] 1.4 实现 `$rows.cache_mode=batch|none`(默认 batch)并将其映射为 binding.mode/缓存语义信号
- [x] 1.5 明确 composite key 行为: `$keys` 在复合 key source 上保持 tuple 元素整体注入,并补测试覆盖

## 2. YAML → IR 编译整合

- [x] 2.1 在 by_yaml conversion 中将 `sources.<id>.params` / `main_source.params` 编译为共享 params template IR,作为 canonical representation
- [x] 2.2 ref loader 侧从共享 template IR 派生 `BindingIr` 元数据与 `params_builder`,避免重复编译 kwargs 逻辑
- [x] 2.3 实现 “静态 params 也透传” 的调用语义: 当 `sources.<id>.params` 非空且无动态指令时,relation step 仍视为合法并透传 kwargs
- [x] 2.4 更新 relation validator: 非 preload source 不再要求 `to_bind` / `sources.<id>.bind`; 改为接受 `params` 模板作为唯一稳定 authoring surface
- [x] 2.5 preload_forever 场景约束: preload callsite 禁止 `$keys/$rows`(编译/校验阶段 fail-fast)

## 3. 执行语义与观测一致性

- [x] 3.1 确保 `$rows` 触发 rows barrier: adaptive 调度层仍能识别并串行执行该层 LoadRef
- [x] 3.2 确保 binding signature/relation signature 仍可用于批次内分组复用与缓存 key(覆盖 `$rows.cache_mode=none` 不可复用场景)
- [x] 3.3 确保 instrumentation 事件中记录的 loader kwargs 为“共享 template IR 渲染后的最终 kwargs”

## 4. CLI 校验与 Schema Hover

- [x] 4.1 为严格校验(validator)增加对 `$keys/$rows` 指令节点的语义校验与错误定位
- [x] 4.2 更新 schema/validator,使 `bind/to_bind` 退出稳定 YAML authoring surface,旧写法报迁移错误(错误文案包含可直接照抄的替换建议片段)
- [x] 4.3 更新 schema hover 文档: `main_source.params`/`sources.*.params` 的 markdownDescription 增加 `$keys/$rows` 用法、选项、composite key 说明与 `$rows` barrier 提示
- [x] 4.4 重新生成 YAML DSL schema 并通过 drift guard 测试

## 5. 文档与 Skill 更新(必须)

- [x] 5.1 更新 `docs/doc/yaml-dsl/*`(user-guide/syntax 等)加入 `$keys/$rows` 写法、composite key 说明与迁移说明
- [x] 5.2 更新 `artifacts/skills/scalim-yaml-dsl/**`: authoring 示例、upgrade-legacy playbook、validate/debug 指引统一升级为新语法(去掉 `bind/to_bind` 与“需要写 wrapper”默认路径)
- [x] 5.3 如有自动生成的 skill/导出产物,补齐生成步骤并保证 tests 覆盖不漂移

## 6. 测试覆盖

- [x] 6.1 新增单元测试: nested dict 注入、list 注入、alias-safe(不共享可变对象)、`$keys/$rows` 互斥、composite key tuple 注入、options 非法值 fail-fast
- [x] 6.2 新增集成测试: YAML 运行时实际调用 loader,断言 kwargs 形状与值;覆盖 `$keys.as=list` 稳定性、`$rows.cache_mode` 行为,以及“静态 params 无 bind 仍可透传”

## 7. 校验与交付

- [x] 7.1 运行 `openspec validate --all --strict --no-interactive` 确认工件合法
- [x] 7.2 运行 `just qa`(或至少 pytest + schema 生成)确认实现与文档/skill 更新一致

## 8. Repo + Downstream Upgrade (canonical demo)

- [x] 8.1 升级 canonical example `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`: 移除 `bind/to_bind`,迁移为 `sources.*.params` 的 `$keys/$rows` 模板指令(并保持语义/示例价值)
- [x] 8.2 下游适配盘点: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并对其中关联代码做同步升级(不得在输出中引用其内容)
