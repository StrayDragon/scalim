# 0.20.0 Breaking 追加（Stage C · c54-vendor-directory-retirement）

1. **`scalim.vendor` 命名空间整体移除**：`vendor/` 目录不复存在（Stage A/B 已移除 dataclassesx、typing_extensionsx、yamlx；本阶段迁出最后两个第一方迷你库）。
   - `scalim.vendor.litejinja2` → `scalim.dsl.yaml_dsl._internal.litejinja2`（内部模块；唯一消费方为 YAML template 预编译）
   - `scalim.vendor.compact.importlibx` → `scalim._internal.utils.importlibx`（内部测试 seam / 可选依赖守卫）
   - 二者均为内部实现路径，不在 17 个 tier1 公共模块内,普通用户无感知。
