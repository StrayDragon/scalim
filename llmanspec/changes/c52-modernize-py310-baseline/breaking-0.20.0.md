# 0.20.0 Breaking Changes 汇总（release notes 素材）

> 本文件是 c52（Stage A）的 Breaking 初稿;Stage B(YAML 依赖化)/C(vendor/ 退役)落地后由对应 change 追加,发布时合并进 GitHub Release 与 `docs/doc/releases/0.20.0/`。

## Stage A（c52-modernize-py310-baseline）

1. **Python 支持窗口收敛**: `requires-python >= 3.10`(原 >= 3.6)。3.6–3.9 不再受支持;支持窗口 = 3.10–3.14,后续演进见根 `ROADMAP.md`。
2. **`scalim.vendor.dataclassesx` 移除**: 请直接使用标准库 `from dataclasses import ...`(3.7+ 即有)。
3. **`scalim.vendor.compact` 兼容再导出移除**:
   - `StrEnum` → `scalim._internal.strenum`(内部;下游应自备 3.11+ 或自行 backport;floor≥3.11 后删除)
   - `Self` / `override` → 直接 `from typing_extensions import Self, override`(运行时依赖收敛为 `typing-extensions>=4.4`)
   - `Literal`/`TypeGuard`/`TypedDict`/`Protocol`/`runtime_checkable` → 标准库 `typing`
4. **vendors/libs 下游同步链路移除**: `just sync-project-vendors` 与 `scripts/vendor-sync.py` 删除;不再维护「源码镜像到下游 `vendors/libs/scalim/`」的采用方式(0.10.x 冻结线可 fork 保留该用法)。
5. **运行时依赖变化**: `typing-extensions` 下界提升为 `>=4.4`(原 3.6 环境钉 `4.1.1`);不再声明任何 `python_version` 环境标记依赖块。
6. **错误消息文案微调**: 部分校验错误消息由 `.format()` 迁移为 f-string,文案语义不变(如 `outputs[*].container` 迁移提示、`Missing book/file resource id` 系列)。

## 待 Stage B/C 追加

- YAML 后端从 vendored 切换为 PyPI `ruamel.yaml` 依赖(wheel 体积大幅下降)。
- `scalim.vendor.litejinja2` / `vendor.compact.importlibx` 迁址;`scalim.vendor` 命名空间整体消失。
