## 1. Define SSOT contracts

- [ ] 1.1 在 `openspec/specs/error-taxonomy/spec.md` 中完善错误分类/错误码命名空间规则与最小字段集(确保每条要求都有可执行场景)。
- [ ] 1.2 明确与现有事件系统(Hook/Observer 错误事件)的映射策略:哪些字段进入事件 payload,哪些必须 redaction。

## 2. Add minimal runtime foundation (implementation)

- [ ] 2.1 新增统一异常基类(概念名 `ScalimError`)与通用字段(`code`/`message`/`hint`/`context`)的实现位置与导入路径,确保 `src/scalim/` Python 3.6 兼容且相对导入。
- [ ] 2.2 增加错误码常量的集中管理方式(字符串常量),并定义命名空间(例如 `yaml.*`/`execution.*`/`workflow.*`)。
- [ ] 2.3 提供一个最小的“对外呈现”辅助(例如 `format_error(e)`/`as_error_dict(e)`),用于 CLI/日志/事件输出复用且默认 redaction。

## 3. Migrate high-signal paths first

- [ ] 3.1 YAML 配置解析/校验相关错误:迁移为稳定 `code` + path/hint 结构,并将测试断言从 message 迁移到 code。
- [ ] 3.2 execution 参数校验与运行期 guardrails fail-fast:对用户可感知错误统一使用新体系,并确保错误信息不泄露敏感值。
- [ ] 3.3 workflow 层错误:保持不反向依赖 DSL 的约束下,将 workflow 的错误对外呈现对齐 error-taxonomy。

## 4. Update tests & docs

- [ ] 4.1 梳理并更新测试断言策略:优先断言 `code`,必要时断言少量稳定子串,避免绑定完整 message。
- [ ] 4.2 若需要对外文档化错误码/分类,在 OpenSpec specs 作为 SSOT 增补说明,并用 `just gen-docs` 同步到 docs-site(不手改任何 `.gen.` 文件与 `BEGIN/END AUTOGEN` 区块内部)。

## 5. Verification

- [ ] 5.1 `just openspec-check` 确保 OpenSpec 工件可发布(含 sanitize + `openspec validate --all --strict --no-interactive`)。
- [ ] 5.2 迁移实现阶段以 `uv run pytest -q` 做全量回归。

