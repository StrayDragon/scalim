## 1. Callable Preflight SSOT

- [ ] 1.1 提炼统一的 callable preflight SSOT API（callsite `location/path` + 引用解析 + 签名绑定校验 + 诊断格式）
- [ ] 1.2（已完成）在派生字段 `fields.*.call_by` 编译期执行签名绑定校验并 fail-fast
- [ ] 1.3（已完成）在聚合后派生字段 `outputs[*].aggregate.fields.*.call_by` 编译期执行签名绑定校验并 fail-fast
- [ ] 1.4 为 `sources.*.normalize.call_by` 增加编译期 signature precheck（至少接受 `result` 位置参数,可选 `ctx`）
- [ ] 1.5 为 loader retry `should_retry(exc, ctx)` 增加编译期 signature precheck（当 `enabled=true` 且回调可 introspect 时）
- [ ] 1.6 为 `compute` 表达式中的 `SAFE_FUNCTIONS` 调用增加“可推理的调用形态/参数个数”预检查（基于 AST + `inspect.signature.bind`）

## 2. Error Lifecycle / Diagnostics

- [ ] 2.1 明确 preflight 错误的异常类型与上抛边界（配置/编译错误；不得进入运行期 guardrails quiet/吞错语义）
- [ ] 2.2 统一错误文案格式（包含 `location`、引用、签名、绑定失败原因、以及可照抄的改写提示）

## 3. Tests / Suites

- [ ] 3.1（已完成）单元测试覆盖 `call_by` 签名绑定校验的关键分支（keyword-only / kwargs / 无签名可取等）
- [ ] 3.2 增加 `normalize.call_by` 的编译期预检查测试（keyword-only result / 接受 ctx 的不同签名形态）
- [ ] 3.3 增加 `compute` 内置函数调用形态预检查测试（例如 `dec(a, b)` 必须编译期失败）
- [ ] 3.4（已完成）补充 notebooks 场景样例并纳入集成测试门禁（坏例子必须 fail-fast；好例子可运行且产出行数稳定）

## 4. Docs / Generated Artifacts / Drift Gates

- [ ] 4.1 若新增/调整 marimo chapters: 重新生成 `notebooks/marimo/marimo_coverage.gen.toon`
  - SSOT: `notebooks/marimo/**.py`
  - 生成入口: `uv run python scripts/gen-marimo-coverage.py`
  - 验收: `just qa`
- [ ] 4.2 若需要在 schema 文案中明确 preflight 语义: 修改 SSOT `src/scalim/dsl/yaml_dsl/schema_dsl/models/*.py` / `src/scalim/dsl/yaml_dsl/schema_dsl/doc_texts.py`
  - 生成入口: `just gen-docs`
  - 验收: `just qa`（含 drift checks）

## 5. Validation

- [ ] 5.1 运行 `just openspec-check`
- [ ] 5.2 运行 `just qa`
