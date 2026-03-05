# Dev Container

??? note "适用读者"
    - 需要稳定开发环境的项目贡献者
    - 负责维护 devcontainer 配置与依赖的开发者

为了避免不同平台/本机依赖导致的安装问题,本仓库提供了 VS Code Dev Containers 配置:`.devcontainer/`.

## 环境描述单

- OS: Ubuntu 24.04 (devcontainers base image)
- Python: 3.10(与 `.python-version` 一致)
- Python 包管理: `uv`(使用 `uv.lock` 固定版本)
- 任务入口: `just`(容器内用 `apt install just` 安装,与 `justfile` 配合)
- 前端(可选): Node.js LTS + Corepack + `pnpm`(`frontend/scalim-viz`,pnpm 用 corepack 安装最新版)
- 缓存/虚拟环境:
  - `${workspace}/.venv` 使用 Docker volume 挂载(避免污染宿主机、跨平台更稳定)
  - `UV_CACHE_DIR=/home/vscode/.cache/uv` 使用 Docker volume 挂载(加速重复安装)

## 中国大陆镜像源(已默认配置)

为方便受限网络环境,本 Dev Container 默认使用以下镜像:

- APT(Ubuntu/Debian 主仓库):清华 TUNA
  - Ubuntu: [https://mirrors.tuna.tsinghua.edu.cn/ubuntu](https://mirrors.tuna.tsinghua.edu.cn/ubuntu)
  - Debian: [https://mirrors.tuna.tsinghua.edu.cn/debian](https://mirrors.tuna.tsinghua.edu.cn/debian)
  - 安全更新源仍保持官方(避免镜像同步延迟)
- PyPI:阿里云 [https://mirrors.aliyun.com/pypi/simple/](https://mirrors.aliyun.com/pypi/simple/)
  - 通过 `PIP_INDEX_URL / UV_DEFAULT_INDEX / UV_INDEX_URL` 配置
- npm/pnpm:npmmirror [https://registry.npmmirror.com](https://registry.npmmirror.com)
  - 通过 `pnpm config set registry ...`(并同时设置了 npm registry)

如果你不想使用镜像(例如境外网络更快),可以在 `.devcontainer/devcontainer.json` 中将上述地址改回官方源:

- PyPI: [https://pypi.org/simple/](https://pypi.org/simple/)
- npm: [https://registry.npmjs.org/](https://registry.npmjs.org/)
- Ubuntu: [http://archive.ubuntu.com/ubuntu/](http://archive.ubuntu.com/ubuntu/)(security 源建议保持不变)

建议基准版本(不低于本仓库当前开发机):

- `python`: 3.10.18
- `uv`: 0.9.26
- `just`: 1.46.0
- `node`: v22.14.0 (LTS)
- `pnpm`: 10.24.0

## 使用方式(VS Code)

1. 安装 VS Code 扩展 **Dev Containers**(`ms-vscode-remote.remote-containers`)
2. 打开仓库根目录
3. 执行命令:**Dev Containers: Reopen in Container**
4. 首次启动会自动执行:`.devcontainer/postCreateCommand.sh`
   - `uv sync --dev --frozen`
   - `corepack enable && corepack install -g pnpm`

## 常用命令

```bash
just type-check
just test
just lintfix
```

前端(可选):

```bash
cd frontend/scalim-viz
pnpm install
pnpm dev --host 0.0.0.0 --port 5173
```

## 常见问题

### 1) `uv sync` 下载源不可用/过慢

当前 `uv.lock` 可能会记录生成时使用的镜像源(例如 `mirrors.aliyun.com`).如果你的网络环境无法访问该源:

- 推荐做法:在本机/容器内重新生成 `uv.lock`(使用你的可用默认源),再执行 `uv sync`.
- 临时做法:通过环境变量指定默认 index(如 `UV_DEFAULT_INDEX`),并配合 `uv lock` 重新锁定.

### 2) 想“重置”虚拟环境/缓存

Devcontainer 使用了 Docker volumes(`scalim-venv` / `scalim-uv-cache`).需要重置时可以删除对应 volume 后重新构建容器.
