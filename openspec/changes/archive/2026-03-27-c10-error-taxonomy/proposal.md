## Why

当前 scalim 的错误/异常体系缺少统一规范:不同模块混用 `ValueError`/`TypeError`/`RuntimeError` 以及零散的自定义异常类,错误信息口径不一致(异常类型/层级、消息格式、是否泄露敏感信息、是否给出迁移提示等),导致用户排障成本高、测试断言脆弱且跨模块行为难以稳定演进。

## What Changes

- 引入一套明确的“异常体系”规范:以 `ScalimException(Exception)` 作为唯一根,并给出严格树形继承与分类/命名约定。
- 以异常类型(而非错误码)作为稳定契约:用户与测试通过 `isinstance`/`except` 进行分类处理;错误 message 主要用于人类诊断并遵循敏感信息治理。
- 明确与事件系统(Observer/Hook)的对齐边界:不引入额外错误码/映射层,沿用现有 `error_type`/`error_message` 语义。
- 明确各类错误的抛出边界与传播策略(配置错误/输入不合法/运行时护栏违规/系统错误/第三方依赖错误等)。
- 定义渐进迁移策略:允许先在新代码/新路径使用新体系,再逐步迁移存量错误点,并提供可测试的验收口径(优先断言异常类型/字段;必要时 message 常量共享)。

## Capabilities

### New Capabilities
- `error-taxonomy`: 统一 scalim 的异常体系(单根异常、分类分层、命名约定、message/敏感信息治理、迁移与测试口径)。

### Modified Capabilities
- (none)

## Impact

- 代码: 影响范围横跨 `src/scalim/`(execution/dsl/workflow/ob/hooks/utils 等)的错误抛出点与异常类型定义;需要逐步迁移以保持可控。
- 测试: 需要将“匹配原始错误 message”的断言逐步迁移为“匹配异常类型/稳定字段(必要时 message 常量)”的断言,降低脆弱性。
- 文档治理: 本 change 通过 delta spec 维护 SSOT(`openspec/changes/c10-error-taxonomy/specs/**`),完成后同步到 `openspec/specs/**`;如需要同步到 docs-site,遵循生成物/注入区块规则,入口为 `just gen-docs`(不手改任何 `.gen.` 文件与 `BEGIN/END AUTOGEN` 区块内部)。
