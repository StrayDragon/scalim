## 1. 内部日志工具

- [x] 1.1 新增 `src/scalim/_internal/loggingx.py`: 提供 `get_logger/prefix/format_kv/bind`,并在导入时为 `logging.getLogger("scalim")` 安装 `NullHandler`(库端默认静默,不做全局配置).
- [x] 1.2 新增 `src/scalim/_internal/__init__.py` 作为内部工具包入口(仅承载最小导入与说明).

## 2. 统一框架内日志输出

- [x] 2.1 YAML DSL schema 校验: `jsonschema` 不可用/不兼容时,统一输出为 `[scalim] schema:` 前缀并附带 `reason/detail` 诊断字段.
- [x] 2.2 派生输出护栏: `max_groups/max_distinct/dedup_by.max_distinct` 等风险提示统一为 `[scalim] derived_outputs:` 前缀,并附带 `target_id/group_by/key_fields` 等字段.
- [x] 2.3 hooks/ob/performance/sinks 等热点: 统一前缀与 `k=v` 追加字段格式,消除类名前缀与不一致的标签写法。

## 3. Tests

- [x] 3.1 新增 `tests/test_loggingx.py` 覆盖 `loggingx` 的所有分支(含 `NullHandler` 幂等、`k=v` 稳定性、`LoggerAdapter` 绑定).
- [x] 3.2 更新相关回归测试,使其断言新前缀与关键诊断字段(例如 `[scalim] schema:`、`[scalim] performance:`)。

## 4. Specs

- [x] 4.1 新增能力规范 `framework-logging` 的 delta 规范: `openspec/changes/c10-unify-framework-logging/specs/framework-logging/spec.md`。
- [x] 4.2 同步到主规范: `openspec/specs/framework-logging/spec.md`。

## 5. Gates

- [x] 5.1 运行 `pytest -q` 确保无回归。
- [x] 5.2 运行 `just openspec-check`(sanitize + `openspec validate --all --strict --no-interactive`)确保 OpenSpec 工件结构通过。
