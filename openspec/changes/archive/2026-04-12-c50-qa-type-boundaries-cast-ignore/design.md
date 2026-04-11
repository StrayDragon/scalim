## Context

仓库运行时代码（`src/scalim/`）需要保持 Python 3.6 兼容，同时工程治理强（`ruff` + `basedpyright`）。在“动态结构解析 / 运行时边界”处出现一定数量的 `cast()` 与 `type: ignore[...]` 是合理的，但当前存在治理痛点：

- `cast/ignore` 分散在业务逻辑中，可读性差、评审成本高；
- 同类“窄化（mapping/list/str）+ 路径报错拼接”逻辑重复实现；
- 少量 `type: ignore[call-arg]` 掩盖了动态签名调用的真实风险（只能靠运行时暴露）；
- 难以判断某个 ignore 是“有意的边界豁免”还是“临时绕过”。

本变更定位为 qa-0：把必要的动态性集中到少量边界 helper 中，让大部分业务逻辑只处理“已被验证/窄化过的结构化对象”，并对不可避免的动态调用用测试矩阵兜住。

## Goals / Non-Goals

**Goals:**

- 让绝大多数业务逻辑不直接写 `cast()` / `type: ignore`
- 将常用类型窄化与错误信息口径集中到可复用 helper（形成 runtime 边界 SSOT）
- 对必须 ignore 的动态调用点：收敛到极少数函数，并用签名矩阵测试覆盖
- 保持 Python 3.6 兼容（必要时使用 `typing_extensionsx` 兼容层）

**Non-Goals:**

- 不追求把所有 dynamic/reflective 行为完全静态化（类型系统无法表达的部分仍允许存在）
- 不引入新的对外 API；本次治理以内部模块与测试护栏为主

## Decisions

### 1) 引入内部 narrowing helper（方案 A）

新增一个内部模块作为“运行时边界窄化 SSOT”（命名以实现为准，例如 `src/scalim/_internal/type_narrowing.py` 或放在 YAML parsing 内部 utils）：

- `as_mapping(value, *, path) -> Optional[Dict[str, object]]`
- `as_list(value, *, path) -> Optional[List[object]]`
- `require_str(value, *, path) -> str`
- `mapping_get_str(mapping, key, *, path) -> Optional[str]`

并在 `validator.py` 等配置解析模块逐步替换散落的 `isinstance + cast` 片段，让业务逻辑更线性、更易读，同时统一错误信息（path/消息）生成口径。

### 2) 将不可避免的 ignore 聚拢到边界函数，并用测试矩阵兜底（方案 B）

对动态签名调用类逻辑（例如根据 `inspect.signature` 选择 `fn(result, ctx)` / `fn(result)` 形态）：

- `type: ignore[call-arg]` MUST 只存在于 1~2 个边界函数内，不得扩散到调用方
- 增加“签名矩阵测试”，覆盖常见签名形态与 fallback（`inspect.signature` 不可用场景）

对低风险 ignore（例如 `Literal` 返回值推导不足）优先用标准写法消除（例如显式 `cast(KeyNormalizationMode, raw)`）。

## Risks / Trade-offs

- **迁移工作量**：需要在多个模块替换窄化片段；但通过 helper 集中后，后续新增解析逻辑会更快且更不易出错。
- **测试维护成本**：签名矩阵测试需要维护，但能有效降低未来 Python/inspect 行为变化导致的回归风险。

## Migration Plan

- Phase 0：落地 narrowing helper + 修复/收敛最痛点 ignore（`Literal` 返回值、动态签名调用点）+ 增加签名矩阵测试
- Phase 1：逐步将 YAML parsing/validator 中的重复窄化逻辑迁移到 helper（不追求一次性清空）

## Helper Location

本 change 选择将通用 narrowing helper 放在 `src/scalim/_internal/` 下（例如 `src/scalim/_internal/type_narrowing.py`），使其可被多个领域模块复用，而不是仅局限于 YAML parsing 子包。

## Open Questions

- 无。
