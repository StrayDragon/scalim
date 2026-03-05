# YAML DSL 编辑器

??? note "适用读者"
    - 写 YAML 配置并希望获得补全/校验的使用方
    - 需要接入本地语义校验(bridge)的开发者

`frontend/scalim-yaml-dsl-editor/` 是一个 **text-first** 的 YAML DSL 编辑器:默认纯前端运行(不依赖 Python),提供基于 canonical schema 的补全/hover/schema 校验;并可选接入本地 bridge 获取 `scalim-cli` 风格的语义校验结果(含定位信息).

## 快速开始

```bash
cd frontend/scalim-yaml-dsl-editor
pnpm install
pnpm dev
```

默认端口:`5174`(strictPort).

## Schema 同步

编辑器内置使用 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 的前端拷贝版本:

```bash
just gen-yaml-dsl-editor-schema
```

会生成/同步:`frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json`.

## 使用要点

- 顶栏:新建模板 / 载入示例 / 插入 `$schema` header / 导入/导出/复制
- `strict`:把未知字段等“潜在问题”提升为 error(便于导出前收敛质量)
- Outline:基于 YAML AST 的快速导航(支持 anchors/comments 的位置保留)
- Issues:统一展示 schema/unknown-fields/(optional)semantic issues,并支持点击跳转

## (可选)语义校验 bridge

bridge 是一个本地 loopback HTTP 服务,前端通过它向本地校验器提交 YAML 文本并获取 issues.

启动:

```bash
uv run python frontend/scalim-yaml-dsl-editor/bridge/scalim_yaml_dsl_bridge.py --token devtoken
```

在编辑器顶栏开启 `bridge` 并填写:
- url: [http://127.0.0.1:8787](http://127.0.0.1:8787)
- token: `devtoken`

### 安全与 CORS

bridge:
- 默认仅监听 `127.0.0.1`
- 仅允许来自白名单 origin 的浏览器请求(CORS)
- 可选 token 鉴权(推荐开启)

默认白名单包含:
- [http://localhost:5174](http://localhost:5174) / [http://127.0.0.1:5174](http://127.0.0.1:5174)(Vite dev)
- [http://localhost:4173](http://localhost:4173) / [http://127.0.0.1:4173](http://127.0.0.1:4173)(Vite preview)

如果你的编辑器运行在其它 origin(或 `file://`,其 Origin 通常为 `null`),需要显式加白:

```bash
uv run python frontend/scalim-yaml-dsl-editor/bridge/scalim_yaml_dsl_bridge.py \
  --token devtoken \
  --allow-origin "null"
```
