# 导航：pygls 2.1.1（Server + 协议扩展）

这份导航的目标是：**用最少上下文，最快定位权威信息**（本 skill 内置 *pygls 2.1.1* docs 快照：`references/pygls-2.1.1/docs/source/**`）。

## 事实来源优先级（推荐）

1. **官方文档优先**：先按用户项目锁定的 `pygls` 版本阅读官方 docs（不确定版本先查锁文件/环境）。
2. **源码验证其次**：当文档不明确或与实际行为冲突时，优先查“用户环境中的源码”（项目 vendor 或 site-packages）。
3. **本 skill 只提供 docs 快照索引**：`references/pygls-2.1.1/docs/source/**`（版本可能与用户不一致，只用于索引/关键词/主题定位）。

## 定位用户环境的 `pygls`（版本 + 源码路径）

优先用用户项目的 Python 环境（venv/uv/poetry/pipx 等）执行：

- 版本：`python -c "import importlib.metadata as m; print(m.version('pygls'))"`
- 源码根：`python -c "import pygls, pathlib; print(pathlib.Path(pygls.__file__).resolve().parent)"`

如果 `import pygls` 失败（未安装/环境未激活），需要先激活用户项目的 Python 环境，或从依赖管理工具/锁文件定位安装位置（因为本 skill 不再内置源码快照）。

## 速查（优先打开的文件）

- Docs 索引：`references/_docs_index.md`
- Server 核心：`references/10-server-core.md`
- Workspace/位置编码：`references/15-workspace-positions.md`
- Built-in / 生命周期：`references/20-builtins-and-lifecycle.md`
- Handler 类型 / 线程 / 取消：`references/30-handler-types-threading.md`
- 协议扩展与自定义消息：`references/40-protocol-extension.md`
- 迁移（只用新写法）：`references/50-migrations-v1-to-v2.md`

## Repo 地图（源码）

核心入口（强相关）：

- `pygls/lsp/server.py`：`LanguageServer`
- `pygls/lsp/_base_server.py`：`BaseLanguageServer`（**generated**：大量 `workspace_*`/`window_*`/`client_*` helper）
- `pygls/server.py`：`JsonRPCServer`、IO 启动（stdio/tcp/ws）、decorator `feature/command/thread`
- `pygls/protocol/language_server.py`：`LanguageServerProtocol`（built-in features 实现、workspace 初始化、executeCommand 参数处理）
- `pygls/protocol/json_rpc.py`：`JsonRPCProtocol`（分发、并发、future、取消、notify/request）
- `pygls/feature_manager.py`：`FeatureManager`（注册 feature/command、thread 标记、server 注入规则）
- `pygls/workspace/*`：`Workspace`、`TextDocument`、`PositionCodec`（同步、文本、位置编码转换）
- `pygls/io_.py`：`run/run_async/run_websocket`（协议循环与 headers/body 解析）

这些路径都应在用户环境的 `PYGLS_SRC` 目录下查找（见下方 `rg` 模板）。

## Repo 地图（文档）

建议从这些 docs 进入（再按需下钻）：

- `references/pygls-2.1.1/docs/source/index.rst`：总站入口
- `references/pygls-2.1.1/docs/source/servers/reference/built-in-features.rst`：built-in features 行为与“自定义 handler 调用顺序”
- `references/pygls-2.1.1/docs/source/pygls/reference/message-handler-types.rst`：async/sync/thread handler 语义
- `references/pygls-2.1.1/docs/source/pygls/howto/send-custom-messages.rst`：自定义 JSON-RPC 消息、扩展 protocol
- `references/pygls-2.1.1/docs/source/pygls/howto/use-custom-converter.rst`：converter/structure hooks
- `references/pygls-2.1.1/docs/source/pygls/howto/migrate-to-v2.rst`：v2 迁移要点（只用新写法）

## 常用 `rg` 模板（复制即用）

先确定 `PYGLS_SRC`（*pygls 包根目录*）：

- 用户环境优先：`PYGLS_SRC=$(python -c "import pygls, pathlib; print(pathlib.Path(pygls.__file__).resolve().parent)")`
 
（没有离线源码兜底；`PYGLS_SRC` 必须来自用户环境。）

定位类/入口：

- `rg -n "class (LanguageServer|BaseLanguageServer|JsonRPCServer|LanguageServerProtocol|JsonRPCProtocol)" "$PYGLS_SRC"`

定位注册点：

- `rg -n "@server\\.(feature|command|thread)\\b" "$PYGLS_SRC"`
- `rg -n "def (feature|command)\\b" "$PYGLS_SRC"`

定位 built-in handler（LSP 方法）：

- `rg -n "@lsp_method\\(" "$PYGLS_SRC/protocol/language_server.py"`

定位某个 LSP 方法名（例如 `textDocument/hover`）：

- `rg -n "textDocument/hover|TEXT_DOCUMENT_HOVER" "$PYGLS_SRC"`

## 使用方式

- `references/_docs_index.md` 是本 skill 内置的 docs 快照索引。
- 需要核对真实行为时，不生成额外索引；直接在用户环境源码上运行上面的 `rg` 模板。
