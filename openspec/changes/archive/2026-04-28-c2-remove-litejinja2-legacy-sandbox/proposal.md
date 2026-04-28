## Why

`template_vars` 的 YAML 预编译是高风险能力: 一旦模板渲染阶段允许方法调用/对象自省,就可能在“仅用于配置”的入口中制造代码执行路径。

当前实现仍保留 `template_sandbox=legacy` 分支(在 `LiteJinja2` 内允许无参方法调用,并且默认 sandbox 值也仍是 legacy)。虽然公共入口已经限制 legacy,但该分支继续存在会:
- 拉低整体安全基线(审计点名,且容易被误用)
- 增加维护成本(两套 sandbox 行为需要同步)
- 与我们当前“无兼容包袱,一步到位”的迭代策略冲突

我们认为仓库内/现有使用方已经迁移到 `safe` 语义,因此可以做一次 **BREAKING** 清理: 彻底移除 legacy sandbox。

## What Changes

- **BREAKING**: 删除 `template_sandbox=legacy` 支持(包括 public 与 unsafe 入口)。
- 将 `LiteJinja2` 的默认 sandbox 改为 `safe`,并移除 legacy 分支代码:
  - method call 语法(`x.y()`)一律 fail-fast
  - 继续禁止 `_`/`__dunder__` 属性访问
- 更新 YAML DSL 的模板预编译验证逻辑与测试用例: 删除 legacy 相关测试,并补充 safe-only 的回归覆盖。
- 更新 OpenSpec: 重新定义 `yaml-template-vars` 的 sandbox 契约,移除 legacy opt-in 描述并提供迁移说明。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `yaml-template-vars`: sandbox 策略改为 safe-only,移除 legacy 语义与相关入口。

## Impact

- 受影响代码:
  - `src/scalim/vendor/litejinja2/__init__.py`
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/template_precompile.py`
  - `src/scalim/dsl/yaml_dsl/runtime/unsafe_entrypoints.py`
  - 任何透传/校验 `template_sandbox` 的入口
- 受影响测试:
  - `tests/yaml_dsl/test_yaml_template_vars_precompile.py` (legacy 分支用例移除/替换)
- 风险:
  - 对仍依赖 legacy 行为的调用方是破坏性变更(但本仓库策略选择不兼容旧写法)。
