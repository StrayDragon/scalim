## 1. 结构准备

- [x] 1.1 盘点 `HookManager` 与 `ObserverManager` 当前承担的职责边界,确认需要拆出的内部子模块与最小接口.
- [x] 1.2 设计 `hooks` / `ob` phase 1 的内部模块布局,明确哪些类型继续走现有稳定入口暴露.
- [x] 1.3 补充或整理与稳定入口、pickle roundtrip、线程安全、热路径缓存相关的保护性测试.

## 2. Hook / Observer managers phase 1 实施

- [x] 2.1 将 `HookManager` 的注册管理、handler 解析/缓存、dispatch 相关职责拆入内部子模块,保持现有推荐导入路径不变.
- [x] 2.2 将 `ObserverManager` 的注册管理、wants/handler 缓存、capture/replay 状态辅助拆入内部子模块,保持现有推荐导入路径不变.
- [x] 2.3 确保拆分后 `HookManager` / `ObserverManager` 的线程安全与 pickle 后锁恢复语义保持不变.

## 3. 验证与收口

- [x] 3.1 运行 hooks / observability 相关单元测试与模块布局测试,确认稳定入口与行为语义未回归.
- [x] 3.2 运行 `openspec validate --all --strict --no-interactive`,确保 change 工件与主规范一致.
- [x] 3.3 检查一个受控外部消费者中的相关调用点;若命中本次重构影响入口,则一步升级到新写法,且不在 change 工件中暴露真实项目路径.
- [x] 3.4 更新必要的开发文档/注释,说明 phase 1 仅覆盖 managers 内部职责拆分,其余热点模块另开 change 处理.
