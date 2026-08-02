# 任务: 按 API 适配 EventType 身份变更

## 何时使用

升级 Scalim 后出现与事件订阅 / `Event.event_type` / payload 导入相关的失败,或需要按公开契约迁移自定义 Observer / Hook。

## 阅读顺序

1. `references/upgrades/2026-07-19-event-type-enum-identity.md`(EventType 身份 + Before/After)
2. `references/upgrades/2026-08-02-typed-handlers-receive-event.md`(typed `on_*` 收 `Event` + Before/After)
3. `docs/doc/architecture/arch.md` 中 Event / Hook 身份说明(可选)
4. 示例: `ch180_public_api_hooks_events` / `ch182_public_api_event_type_groups`

## 工作方式

1. 在用户代码中按 upgrade 文档「如何判断是否受影响」一节搜索
2. 对每个命中点,对照 upgrade 文档 **A–H** 小节完成替换
3. 跑用户现有的最小执行路径(注册组件 + 一次运行)确认不再因 `event_types` / `EventType` 失败

## 常见错误 → 对应小节

| 错误 / 现象 | 见 upgrade |
|-------------|------------|
| `must contain only EventType; got str` | A |
| `must be None or Set[EventType]` | A |
| 无法或不该从非公开模块导入 `*Event` payload | B |
| typed `on_*` 仍按 payload dataclass 取字段 | `2026-08-02-typed-handlers-receive-event.md` A；旧 EventType 卡 C |
| 序列化后再构造 `Event` 身份不对 | E |
| `wants` / `emit` 参数类型不匹配 | F |
