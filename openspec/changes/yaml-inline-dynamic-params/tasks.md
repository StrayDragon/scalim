## 1. 模板指令解析与渲染

- [ ] 1.1 新增 params 模板渲染器: 递归渲染 dict/list/scalar,识别 `$keys/$rows` 指令节点并做深拷贝输出(保证 alias-safe)
- [ ] 1.2 新增指令节点语义校验: 单 key mapping、options 类型与枚举值、`$keys/$rows` 互斥、非法上下文 fail-fast(错误包含配置 path)
- [ ] 1.3 实现 `$keys.as=set|list`(默认 set)与 `$keys.as=list` 的稳定顺序(复用稳定排序 helper)
- [ ] 1.4 实现 `$rows.cache_mode=batch|none`(默认 batch)并将其映射为 binding.mode/缓存语义信号

## 2. YAML → IR 编译整合

- [ ] 2.1 在 by_yaml conversion 中将 `sources.<id>.params` 编译为 BindingIr(模板渲染作为 params_builder),支持 nested 注入
- [ ] 2.2 实现 “静态 params 也透传” 的调用语义: 当 `sources.<id>.params` 非空但无 legacy bind/to_bind 时仍透传 kwargs(通过静态 binding 或等价实现)
- [ ] 2.3 实现与 legacy `bind/to_bind` 的冲突检测: 当模板出现 `$keys/$rows` 时禁止同时声明 bind/to_bind(给出迁移提示)
- [ ] 2.4 preload_forever 场景约束: preload callsite 禁止 `$keys/$rows`(编译/校验阶段 fail-fast)

## 3. 执行语义与观测一致性

- [ ] 3.1 确保 `$rows` 触发 rows barrier: adaptive 调度层仍能识别并串行执行该层 LoadRef
- [ ] 3.2 确保 binding signature/relation signature 仍可用于批次内分组复用与缓存 key(覆盖 `$rows.cache_mode=none` 不可复用场景)
- [ ] 3.3 确保 instrumentation 事件中记录的 loader kwargs 为“渲染后的最终 kwargs”

## 4. CLI 校验与 Schema Hover

- [ ] 4.1 为严格校验(validator)增加对 `$keys/$rows` 指令节点的语义校验与错误定位
- [ ] 4.2 更新 schema hover 文档: `main_source.params`/`sources.*.params` 的 markdownDescription 增加 `$keys/$rows` 用法、选项与 `$rows` barrier 提示
- [ ] 4.3 重新生成 YAML DSL schema 并通过 drift guard 测试

## 5. 文档与 Skill 更新(必须)

- [ ] 5.1 更新 `docs/doc/yaml-dsl/*`(user-guide/syntax 等)加入 `$keys/$rows` 写法与迁移说明
- [ ] 5.2 更新 `artifacts/skills/scalim-yaml-dsl/**`: authoring 示例、upgrade-legacy playbook、validate/debug 指引统一升级为新语法(去掉“需要写 wrapper”默认路径)
- [ ] 5.3 如有自动生成的 skill/导出产物,补齐生成步骤并保证 tests 覆盖不漂移

## 6. 测试覆盖

- [ ] 6.1 新增单元测试: nested dict 注入、list 注入、alias-safe(不共享可变对象)、`$keys/$rows` 互斥、options 非法值 fail-fast
- [ ] 6.2 新增集成测试: YAML 运行时实际调用 loader,断言 kwargs 形状与值;覆盖 `$keys.as=list` 稳定性与 `$rows.cache_mode` 行为

## 7. 校验与交付

- [ ] 7.1 运行 `openspec validate --all --strict --no-interactive` 确认工件合法
- [ ] 7.2 运行 `just qa`(或至少 pytest + schema 生成)确认实现与文档/skill 更新一致

