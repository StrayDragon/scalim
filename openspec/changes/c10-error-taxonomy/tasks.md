## 1. Define SSOT contracts

- [x] 1.1 在 `openspec/changes/c10-error-taxonomy/specs/error-taxonomy/spec.md` 中完善异常根类型/分类分层/命名约定/测试口径/敏感信息治理(确保每条要求都有可执行场景)。
- [x] 1.2 明确与现有事件系统(Hook/Observer 错误事件)的对齐边界:不新增错误码/映射,仅约束最小输出与安全性(`error_type`/`error_message`)。

## 2. Add minimal runtime foundation (implementation)

- [x] 2.1 新增统一异常根 `ScalimException`(以及必要的分类基类)的实现位置与导入路径,确保 `src/scalim/` Python 3.6 兼容且相对导入。
- [x] 2.2 迁移现有自定义异常继承 `ScalimException`(保持单继承,避免多根)并按域拆分模块(例如 YAML/Execution/Workflow)。
- [x] 2.3 若测试必须断言 message,将 message/模板提升为常量并在实现与测试中共享(避免断言漂移)。

## 3. Migrate high-signal paths first

- [x] 3.1 YAML 配置解析/校验相关错误:迁移为明确异常类型(可携带 path/issues 等显式字段),并将测试断言从 message 迁移到异常类型/字段(必要时 message 常量)。
- [x] 3.2 execution 参数校验与运行期 guardrails fail-fast:对用户可感知错误统一使用新体系,并确保错误信息不泄露敏感值。
- [x] 3.3 workflow 层错误:保持不反向依赖 DSL 的约束下,将 workflow 的错误对外呈现对齐 error-taxonomy。

## 4. Update tests & docs

- [x] 4.1 梳理并更新测试断言策略:优先断言异常类型/显式字段;仅在必要时断言少量稳定子串,并通过常量共享避免漂移。
- [x] 4.2 完成后将 delta spec 同步到主 specs (`openspec/specs/error-taxonomy/spec.md`);如需对外文档化再用 `just gen-docs` 同步到 docs-site(不手改任何 `.gen.` 文件与 `BEGIN/END AUTOGEN` 区块内部)。

## 5. Verification

- [x] 5.1 `just openspec-check` 确保 OpenSpec 工件可发布(含 sanitize + `openspec validate --all --strict --no-interactive`)。
- [x] 5.2 迁移实现阶段以 `uv run pytest -q` 做全量回归。
