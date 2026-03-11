## Why

当前 YAML DSL 的 `loader` / `call_by` 引用只支持绝对 Python 路径(例如 `myapp.loaders:load_orders`),当配置与实现代码一起被移动/拆分到新的模块层级时,配置会产生大量机械性改动且可读性下降。
我们希望像 Python 的相对导入一样,允许在 YAML 中使用相对模块引用,以支持“配置与实现同目录/同包”协作与更低成本的重构。

## What Changes

- 为 YAML DSL 中所有“Python 引用字符串”增加相对模块路径语法:
  - 支持以 `.` / `..` 开头的 module path(类似 Python relative import),例如 `.loaders:load_orders`、`..common.transforms:fixup`。
  - 相对路径的基准为 **YAML 文件所在目录** 的“当前 module 路径”(见 design,由运行时根据 `yaml_path` 计算)。
- 兼容保留现有绝对引用格式:
  - `module.path.function`
  - `module.path:obj.method`
- 安全边界保持不变:
  - 相对引用在解析为绝对引用后,必须通过与现有一致的 allowlist 约束(`allowed_modules`/`allowed_functions`)与 resolver 安全检查,否则 fail-fast 并给出可操作的错误信息。
- 更新 schema/编辑器 hover 文案与用户文档示例,明确相对引用的语义与限制。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `demand-dsl`: 扩展 loader / `call_by` / retry 回调等 Python 引用语法,并定义相对引用的解析规则与 allowlist 约束行为。
- `field-compute`: 扩展 `call_by` 的 `reference(args...)` 中 reference 语法,允许使用相对模块引用并保持 allowlist 约束。
- `yaml-dsl-schema`: 更新相关字段的 schema `description`/`markdownDescription` 与示例,说明相对引用语法与基准目录规则。
- `yaml-dsl-editor-core`: 编辑器跟随 canonical schema 提供相对引用语法提示/hover,并保持文案一致。
- `yaml-dsl-agent-guidance`: 更新 agent guidance 与示例,指导何时使用相对引用,以及如何配置 allowlist 以通过校验。

## Impact

- 受影响代码(预计):
  - YAML 解析/校验: `src/scalim/dsl/by_yaml/config_parsing/*`(loader ref / call_by ref 的格式校验)
  - YAML 编译/解析: `src/scalim/dsl/by_yaml/runtime/*`(从 `yaml_path` 计算 base module,并在 resolver 前完成相对引用归一化)
  - Schema/编辑器镜像与文档示例: `src/scalim/dsl/by_yaml/schema/*` + `frontend/scalim-yaml-dsl-editor/public/schema/*` + `docs/doc/yaml-dsl/*`
- API 影响:
  - `run/compile(yaml_path, allowed_modules=..., allowed_functions=...)` 的调用方式不变;新增能力仅影响 YAML 内引用字符串解析。
  - 相对引用引入新的校验失败场景: 当 `yaml_path` 无法映射到可导入的 module 路径、或解析后的绝对引用不在 allowlist 内时将明确报错。
