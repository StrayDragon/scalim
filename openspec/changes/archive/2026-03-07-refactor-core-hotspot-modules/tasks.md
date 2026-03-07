## 1. 基线与保护性测试

- [x] 1.1 盘点 6 个确认热点模块的当前职责边界,为每条主线列出拆分目标与稳定入口.
- [x] 1.2 补齐或整理保护性测试:稳定导入路径、pickle roundtrip、线程安全、viz 产物兼容、adaptive 输出/事件顺序.
- [x] 1.3 明确每个热点的实施顺序与 review 边界,防止一次性 change 在实现时继续扩散 scope.

## 2. DSL runtime / validator 重构 phase

- [x] 2.1 拆分 `config_parsing/validators/fields.py`,按规则职责迁移到内部子模块,保持 validator 稳定入口与行为语义不变.
- [x] 2.2 拆分 `runtime/conversion.py`,按 registry/helper、Config→IR 转换、运行请求映射等边界迁移实现.
- [x] 2.3 运行 YAML runtime / validator 相关测试,确认导入、错误语义与运行行为未回归.

## 3. hooks / observer / viz 重构 phase

- [x] 3.1 拆分 `hooks/base.py`,分离 hook 协议/基类、注册管理与 dispatch 缓存职责.
- [x] 3.2 拆分 `ob/manager.py`,分离 observer 注册管理、wants/handler cache 与 capture/replay 状态职责.
- [x] 3.3 拆分 `ob/presets/viz.py`,分离配置路径解析、事件映射、快照增强与文件写入职责.
- [x] 3.4 运行 hooks / observer / viz 相关测试,确认稳定入口、线程安全、pickle 与回放产物兼容性未回归.

## 4. adaptive execution 重构 phase

- [x] 4.1 拆分 `execution/adaptive/loadref_scheduler.py`,分离策略解析、layer planning、任务提交、结果聚合与顺序维护职责.
- [x] 4.2 校对拆分后与现有 `execution/adaptive/*_unit.py` 的职责边界,避免新的职责重叠.
- [x] 4.3 运行 adaptive execution 相关测试,确认输出顺序、事件顺序与错误语义未回归.

## 5. 统一验证与收口

- [x] 5.1 运行主框架类型检查、相关单元测试与 Python 3.6 兼容检查,确认本次一次性重构未破坏兼容基线.
- [x] 5.2 运行 `openspec validate --all --strict --no-interactive`,确保 change 工件与主规范一致.
- [x] 5.3 检查一个受控外部消费者中的相关调用点;若命中本次一次性重构影响入口,则一步升级到新写法,且不在 change 工件中暴露真实项目路径.
- [x] 5.4 更新必要的开发文档/注释,说明本次 change 覆盖全部确认热点模块的一次性重构范围.
