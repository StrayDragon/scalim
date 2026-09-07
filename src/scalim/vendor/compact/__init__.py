"""`vendor/compact` 包标记。

原 `StrEnum`/`Self`/`override` 兼容再导出已随版本线 `0.20.x` 阶段一移除:
- `StrEnum` → `scalim._internal.strenum`(下界到达 `3.11` 时删除,见 `ROADMAP` 棘轮步骤)
- `Self`/`override` → 直接 `from typing_extensions import ...`(需 `>=4.4`)
仅保留 `importlibx`(测试接缝 + 可选依赖守卫,阶段三将迁至 `_internal/utils/`)。
"""
