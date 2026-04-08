## 1. Callable Preflight SSOT

- [ ] 1.1 提炼统一的 callable preflight SSOT API（callsite `location/path` + 签名绑定校验 + 诊断格式）
  - Touchpoints: 复用并泛化现有 `src/scalim/dsl/yaml_dsl/runtime/_internal/call_by_signature.py` 模式（`inspect.signature` + `bind` + keyword-only hint）
  - DoD:
    - 支持“多候选调用形态”的校验（例如 normalize 的 `(result)` / `(result, ctx)` / `(result, ctx=ctx)`）
    - `inspect.signature` 不可用时跳过绑定校验,但保留 callsite 的引用解析/可调用性边界
    - 诊断文本稳定（便于 notebooks 断言关键 token）,并包含 rewrite hint（若可推理）
- [ ] 1.2（已完成）在派生字段 `fields.*.call_by` 编译期执行签名绑定校验并 fail-fast
- [ ] 1.3（已完成）在聚合后派生字段 `outputs[*].aggregate.fields.*.call_by` 编译期执行签名绑定校验并 fail-fast
- [ ] 1.4 为 `sources.*.normalize.call_by` 增加编译期 signature precheck（至少接受 `result` 位置参数,可选 `ctx`）
  - Touchpoints: `src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py`（resolve 后,构造 `SourceNormalizeIr` 前）
  - DoD:
    - `def norm(*, result): ...` MUST 编译期失败（不接受任何位置参数）
    - `def norm(result): ...` / `def norm(result, ctx): ...` / `def norm(result, *, ctx): ...` MUST 通过
    - 诊断包含 `sources.<id>.normalize.call_by` 与引用/签名
- [ ] 1.5 为 loader retry `should_retry(exc, ctx)` 增加编译期 signature precheck（当 `enabled=true` 且回调可 introspect 时）
  - Touchpoints: `src/scalim/dsl/yaml_dsl/runtime/compiler.py:_finalize_retry_policy`（effective policy 构建期）
  - DoD:
    - `def should_retry(*, exc, ctx): ...` / `def should_retry(exc, *, ctx): ...` MUST 编译期失败
    - `def should_retry(exc, ctx): ...` / `def should_retry(*args, **kw): ...` MUST 通过
    - 错误不得被 `_safe_should_retry` 静默降级为 `False`
- [ ] 1.6 为 `compute` 表达式中的 `SAFE_FUNCTIONS` 调用增加“可推理的调用形态/参数个数”预检查（基于 AST + `inspect.signature.bind`）
  - Touchpoints: `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py:SecureComputeValidator._validate_call_node`（仅校验 argc/形态,不执行）
  - DoD:
    - 对禁用 keyword args 的前提下,基于 `len(node.args)` 做 `bind(*placeholders)` 校验（当签名可 introspect）
    - 失败 MUST 作为 compute 编译错误 fail-fast（不得进入 compute operator quiet 吞错）
    - 诊断包含: function name、实参个数、签名（当可用）、表达式位置（field_id/path）
- [ ] 1.7 为 loader `params` kwargs 模板增加编译期 signature precheck（`main_source.params` / `sources.*.params`; 当签名可 introspect 时用 `bind(**kwargs_keys)` 校验未知 key / 缺失必填）
  - Touchpoints:
    - `src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py:_convert_main_source`（main_source）
    - `src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py:_binding_from_params_template`（sources.*）
  - DoD:
    - 仅校验 **top-level kwargs keys**（不渲染 template,不依赖 `$keys/$rows` 执行期上下文）
    - 未知 key / 缺失必填 MUST 编译期失败；`**kwargs` loader MUST 允许未知 key
    - `inspect.signature` 不可用时跳过绑定校验,但不得影响引用解析与其它 compile 约束

## 2. Error Lifecycle / Diagnostics

- [ ] 2.1 明确 preflight 错误的异常类型与上抛边界（配置/编译错误；不得进入运行期 guardrails quiet/吞错语义）
  - DoD:
    - 所有 preflight 失败路径在 engine 执行前抛出（demand compile / workflow preflight）
    - compute/should_retry 等原本可能被“运行期吞错/降级”的路径,由 compile 期错误替代
- [ ] 2.2 统一错误文案格式（包含 `location`、引用、签名、绑定失败原因、以及可照抄的改写提示）
  - DoD:
    - call_by / normalize.call_by / should_retry / params / compute builtins 复用同一诊断框架（同字段顺序/同关键 token）
    - notebooks 负例章节仅通过断言关键 token 即可稳定判定（避免依赖完整字符串匹配）

## 3. Tests / Suites

- [ ] 3.1（已完成）单元测试覆盖 `call_by` 签名绑定校验的关键分支（keyword-only / kwargs / 无签名可取等）
- [ ] 3.2 增加 `normalize.call_by` 的编译期预检查测试（keyword-only result / 接受 ctx 的不同签名形态）
  - DoD: 覆盖 `(result)` / `(result, ctx)` / `(result, *, ctx)` / `*args/**kwargs` / 不可 introspect 的跳过策略
- [ ] 3.3 增加 `compute` 内置函数调用形态预检查测试（例如 `len(x, y)` / `dec(a, b)` 必须编译期失败）
  - DoD: 同时覆盖“通过用例”（例如 `Decimal('0.1')` / `dec(x)`）与“拒绝用例”（arity mismatch）
- [ ] 3.4（已完成）补充 notebooks 场景样例并纳入集成测试门禁（坏例子必须 fail-fast；好例子可运行且产出行数稳定）
  - 范围: 仅覆盖 `call_by` keyword-only 的 fast-fail（`yaml_dsl_call_by_keyword_only`）
- [ ] 3.5 增加 `should_retry` 的编译期预检查测试（keyword-only / 缺少 ctx / 缺少 exc 等）
  - DoD: `enabled=true` 时触发预检查；`enabled=false` 不强制要求 `should_retry`（保持现有语义）
- [ ] 3.6 增加 loader `params` 的编译期预检查测试（未知 kw / 缺失必填 kw）
  - DoD: 覆盖 `main_source.params` 与 `sources.*.params` 两类入口
  - DoD: 覆盖 `**kwargs` loader 允许未知 kw 的路径
- [ ] 3.7 notebooks: 新增 `yaml_dsl_compute_builtin_arity_mismatch`（bad YAML 必须 compile 期失败；good gate 复用 `yaml_dsl_support`/`yaml_dsl_ecommerce`）
- [ ] 3.8 notebooks: 新增 `yaml_dsl_normalize_call_by_signature_mismatch`
  - good gate 优先把 `normalize.call_by` 融入 `declared_yaml_dsl/support/support_sla_report.yaml`（identity normalize,保持输出不变）
  - bad gate: keyword-only result（必须 compile 期失败）
- [ ] 3.9 notebooks: 新增 `yaml_dsl_loader_params_signature_mismatch`（bad: params unknown/missing；good gate 复用 `yaml_dsl_support`）
- [ ] 3.10 notebooks: 新增 `yaml_dsl_should_retry_signature_mismatch`（注入 bad should_retry,要求 compile 期失败；good gate 复用 `yaml_dsl_ads`）
- [ ] 3.11 集成门禁: 更新 `notebooks/.../chapters_of_yaml_dsl/registry.py` 与 `tests/integration/test_demo_big_data_report_chapters.py` 选中上述新 chapter ids

### Notebooks strategy (user-side reproduction)

- 好例子尽量融入现有的“全面 YAML fixture”（例如 `support/support_sla_report.yaml`），由现有章节作为 good-path gate
- 坏例子用独立 chapter + 临时 YAML 触发编译期 fast-fail（参考 `yaml_dsl_call_by_keyword_only`）
- `should_retry` 由于是 runtime injection,需要独立章节覆盖“坏签名必须编译期失败 / 好签名可 retry 成功”的端到端链路

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
