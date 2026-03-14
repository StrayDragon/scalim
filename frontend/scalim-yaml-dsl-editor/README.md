# Scalim YAML DSL Editor (Svelte)

可视化/用户友好的 Scalim YAML DSL 编辑器(text-first + schema 校验 + issues 面板).

## 开发

```bash
pnpm install
pnpm dev
```

默认端口:`5174`(strictPort).

## 构建

```bash
pnpm build
pnpm preview
```

## 资源同步

编辑器使用 canonical schema:

- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json`

在仓库根目录执行:

```bash
just gen-yaml-dsl-editor-schema
```

会把 schema 同步到:

- `frontend/scalim-yaml-dsl-editor/public/schema/*.gen.json`
- `frontend/scalim-yaml-dsl-editor/src/schema/*.gen.json`(用于打包内置)

并在 `pnpm build` 后出现在 `frontend/scalim-yaml-dsl-editor/dist/schema/*.gen.json`(来自 `public/`).

注意:不要手改 `*.gen.json`。`just qa`/CI 会捕获 `src/`、`public/`、`dist/` 的 drift。

## 校验层级(schema + semantic)

- **schema 校验(默认)**:Monaco + YAML 顶部 `# yaml-language-server: $schema=...`(支持 demand/workflow). schema 在打包时内置(`src/schema/*.gen.json`),运行时 fetch 仅作为 fallback(`/schema/*.gen.json`).
- **semantic 校验(local,纯前端内置)**:补充关系链路、source 引用、bind/to_bind 要求、loader ref 格式等跨字段规则(持续增强中,暂不追求与 `scalim-cli` 100% 一致).
- **semantic 校验(exact,可选)**:通过 Pyodide 在浏览器内运行 `scalim` 的 Python 校验逻辑,对齐 `scalim-cli yaml-dsl validate`(WebWorker 内执行,失败自动降级到 local).

## 模板 / 示例

- 顶栏 **新建最小模板**:生成 demand YAML 的最小可运行配置(使用 `outputs:`;不包含旧顶层键 `output:`)。
- 顶栏 **载入示例**:根据当前 `$schema` 选择载入 demand 的 `order_report.yaml` 或 workflow 的 `workflow_minimal.yaml`。
- 顶栏 **载入片段**:载入 `imports/$import`、runtime vars 指令节点、`normalize.kind` 的示例(`imports` 片段文件不会在浏览器侧被解析;用于写法参考与 schema 校验)。

## 可选:Pyodide 精确语义校验(semantic: exact)

纯静态页面无法直接执行本机 Python,但可以通过 Pyodide(WASM Python)在浏览器内执行关键校验逻辑.

一键准备(推荐,Pyodide 使用 CDN,wheel 本地提供):

```bash
just frontend-yaml-dsl-editor-exact-prepare
just frontend-yaml-dsl-editor-exact-check-assets
just frontend-yaml-dsl-editor-dev-exact
```

### 1) 准备 Pyodide(默认 CDN,可选本地资源)

默认情况下,编辑器会优先尝试加载本地 `public/pyodide/`(如果存在),否则自动回退到 Pyodide CDN.

也可以显式指定 Pyodide 资源地址(用于内网 CDN / 自定义路径):

```bash
VITE_PYODIDE_INDEX_URL="https://example.com/pyodide/v0.25.1/full/" pnpm dev
```

当 CDN 不可用/希望离线运行时,再准备本地 Pyodide 静态资源:

```bash
bash frontend/scalim-yaml-dsl-editor/scripts/prepare_pyodide.sh
```

网络受限时可加代理:`HTTPS_PROXY=http://127.0.0.1:20171 bash frontend/scalim-yaml-dsl-editor/scripts/prepare_pyodide.sh`

资源会下载到 `frontend/scalim-yaml-dsl-editor/public/pyodide/`(体积较大,默认不提交到 git).

### 2) 构建 scalim wheel(供 Pyodide 安装)

在仓库根目录(本 repo)运行:

```bash
bash frontend/scalim-yaml-dsl-editor/scripts/build_scalim_wheel.sh
```

会生成 `frontend/scalim-yaml-dsl-editor/public/wheels/scalim-*.whl`,并写入清单 `frontend/scalim-yaml-dsl-editor/public/scalim-wheel.json`.

> 注意:Pyodide 端安装 wheel 时使用 `deps=False`,不会拉取 `numpy/pandas/openpyxl` 等大依赖;校验逻辑需保持在“纯 Python + pyyaml”可运行的范围内.

离线/本地 Pyodide 一键准备(包含 wheel + 本地 Pyodide 静态资源):

```bash
just frontend-yaml-dsl-editor-exact-prepare-local
```

### 3) 在编辑器里启用

- 顶栏点击 `semantic: local` → 勾选 “启用 exact(Pyodide)” → 保存
- 如果 Pyodide 资源 / wheel 缺失或初始化失败,会显示错误并自动降级到 local

## Round-trip 与安全应用

结构化 UI 修改优先走“最小文本补丁”;当检测到需要大范围重写(`plan=rewrite`)时,会弹出 diff 预览并要求确认,同时支持顶栏 **撤销(Undo)**.
