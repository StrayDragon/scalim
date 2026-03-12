set dotenv-load := true

UV_OPTIONS := "--preview-features extra-build-dependencies"

# 统一在 just 子进程里固定到默认 PyPI,避免继承本地镜像环境后把 `uv.lock` 再次写脏。
export UV_DEFAULT_INDEX := "https://pypi.org/simple"
export UV_INDEX_URL := ""
export UV_EXTRA_INDEX_URL := ""
export PIP_INDEX_URL := ""
export PIP_EXTRA_INDEX_URL := ""

_default:
    just --list

# 构建文档站点: 预览
docs-serve *ARGS:
    just gen-docs
    uv {{ UV_OPTIONS }} run zensical serve -f docs/zensical.toml -a 0.0.0.0:8000 {{ ARGS }}

# 构建文档站点
docs-build: gen-docs
    uv {{ UV_OPTIONS }} run zensical build -f docs/zensical.toml

# 检查: frontend 公共流程 (install + lint + build)
_frontend-check DIR LABEL:
    #!/usr/bin/env bash
    set -euo pipefail
    dir="{{ DIR }}"
    label="{{ LABEL }}"
    if ! command -v pnpm >/dev/null 2>&1; then
        if [ -n "${CI:-}" ]; then
            echo "pnpm not found (required in CI for ${label})" >&2
            exit 1
        fi
        echo "pnpm not found; skipping ${label}" >&2
        exit 0
    fi
    pnpm -C "$dir" install --frozen-lockfile
    pnpm -C "$dir" lint
    pnpm -C "$dir" build

# 检查: YAML DSL 编辑器 (install + lint + build)
frontend-yaml-dsl-editor-check:
    just _frontend-check frontend/scalim-yaml-dsl-editor frontend-yaml-dsl-editor-check

# 检查: Scalim Viz 前端 (install + lint + build)
frontend-scalim-viz-check:
    just _frontend-check frontend/scalim-viz frontend-scalim-viz-check

# 检查: 所有 frontend (install + lint + build)
frontend-check:
    just frontend-yaml-dsl-editor-check
    just frontend-scalim-viz-check

# 准备: YAML DSL 编辑器 exact (Pyodide) 资源
frontend-yaml-dsl-editor-exact-prepare:
    #!/usr/bin/env bash
    set -e
    bash frontend/scalim-yaml-dsl-editor/scripts/build_scalim_wheel.sh

# 准备: YAML DSL 编辑器 exact (Pyodide) 资源 (离线/本地 Pyodide)
frontend-yaml-dsl-editor-exact-prepare-local:
    #!/usr/bin/env bash
    set -e
    bash frontend/scalim-yaml-dsl-editor/scripts/prepare_pyodide.sh
    bash frontend/scalim-yaml-dsl-editor/scripts/build_scalim_wheel.sh

# 检查: YAML DSL 编辑器 exact (Pyodide) 资源
frontend-yaml-dsl-editor-exact-check-assets:
    #!/usr/bin/env bash
    set -e
    bash frontend/scalim-yaml-dsl-editor/scripts/check_exact_assets.sh

# 检查: YAML DSL 编辑器 exact (Pyodide) 资源 (assets + lint + build)
frontend-yaml-dsl-editor-exact-check:
    #!/usr/bin/env bash
    set -e
    just frontend-yaml-dsl-editor-exact-check-assets
    just frontend-yaml-dsl-editor-check

# 开发: YAML DSL 编辑器 exact (Pyodide) 开发服务器
frontend-yaml-dsl-editor-dev-exact:
    #!/usr/bin/env bash
    set -e
    just frontend-yaml-dsl-editor-exact-prepare
    pnpm -C frontend/scalim-yaml-dsl-editor dev

# 生成: YAML DSL 校验 schema
gen-yaml-dsl-schema:
    uv {{ UV_OPTIONS }} run python scripts/gen-yaml-dsl-schema.py

# 生成: 项目常量(从 `pyproject.toml` 派生;供 Python/前端统一引用)
gen-project-constants:
    uv {{ UV_OPTIONS }} run python scripts/gen-project-constants.py

# 生成: YAML DSL 编辑器 schema
gen-yaml-dsl-editor-schema: gen-yaml-dsl-schema
    uv {{ UV_OPTIONS }} run python scripts/gen-yaml-dsl-editor-schema.py

# 检查: 项目常量生成物是否有 drift
project-constants-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-project-constants.py --check

# 检查: YAML DSL schema 生成物是否有 drift (含 canonical 文本形式)
schema-drift-check: gen-yaml-dsl-editor-schema
    #!/usr/bin/env bash
    set -e
    if ! git diff --exit-code -- src/scalim/dsl/by_yaml/schema/demand.gen.json >/dev/null; then
        echo ""
        echo "YAML DSL schema drift detected:"
        echo "  - src/scalim/dsl/by_yaml/schema/demand.gen.json has uncommitted changes"
        echo ""
        echo "Fix:"
        echo "  - commit the updated generated schema file"
        exit 1
    fi
    if ! git diff --exit-code -- frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json >/dev/null; then
        echo ""
        echo "YAML DSL editor schema drift detected:"
        echo "  - frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json has uncommitted changes"
        echo ""
        echo "Fix:"
        echo "  - run: just gen-yaml-dsl-editor-schema"
        echo "  - commit the updated frontend schema file"
        exit 1
    fi

# 检查: 文档治理一致性(SSOT 入口/漂移源头)
doc-governance-check:
    uv {{ UV_OPTIONS }} run python scripts/check-doc-governance.py

# 检查: stdlib 同名模块冲突
stdlib-collisions-check:
    uv {{ UV_OPTIONS }} run python scripts/check-stdlib-module-collisions.py

# 依赖: 同步开发依赖
uv-sync-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    env \
        -u UV_INDEX \
        -u UV_INDEX_URL \
        -u UV_EXTRA_INDEX_URL \
        -u PIP_INDEX_URL \
        -u PIP_EXTRA_INDEX_URL \
        UV_DEFAULT_INDEX="https://pypi.org/simple" \
        uv {{ UV_OPTIONS }} sync --locked


# 检查: `uv.lock` 是否与当前项目元数据一致(强制按默认 PyPI 校验,避免本地镜像环境掩盖 CI 漂移)
uv-lock-check:
    #!/usr/bin/env bash
    set -euo pipefail
    env \
        -u UV_INDEX \
        -u UV_INDEX_URL \
        -u UV_EXTRA_INDEX_URL \
        -u PIP_INDEX_URL \
        -u PIP_EXTRA_INDEX_URL \
        UV_DEFAULT_INDEX="https://pypi.org/simple" \
        uv {{ UV_OPTIONS }} lock --check

# 构建: wheel/sdist (发行物)
build-dist:
    uv {{ UV_OPTIONS }} build --wheel --sdist --no-create-gitignore --no-sources

# 检查: wheel/sdist 内容边界 (不应包含 tests/docs/notebooks/frontend/artifacts)
dist-check: build-dist
    uv {{ UV_OPTIONS }} run python scripts/check-build-artifacts.py

# 生成: Viz 数据 (默认为 notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml)
gen-viz-data PARAM="":
    uv {{ UV_OPTIONS }} run python scripts/gen-viz-data.py --mode events-only {{ PARAM }}
    # uv {{ UV_OPTIONS }} run python scripts/gen-viz-data.py --mode events+trace {{ PARAM }}

# 生成: Viz schedule plan (基于已生成的 viz_events.jsonl; 用于补齐/修复缺失的 viz_schedule_plan.json)
gen-viz-schedule-plan RUN_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -n "{{ RUN_DIR }}" ]; then
        run_dirs=( "{{ RUN_DIR }}" )
    else
        run_dirs=()
        while IFS= read -r line; do
            run_dirs+=( "$line" )
        done < <(
            find artifacts/scalim-viz/examples/demo_big_data_report -type f -name "viz_events.jsonl" -print \
                | sed 's#/viz_events.jsonl$##' \
                | sort -u
        )
    fi

    for dir in "${run_dirs[@]}"; do
        events_jsonl="${dir}/viz_events.jsonl"
        output_json="${dir}/viz_schedule_plan.json"

        if [ ! -f "$events_jsonl" ]; then
            echo "[warn] missing viz_events.jsonl:" "$events_jsonl" >&2
            continue
        fi
        if [ -f "$output_json" ]; then
            continue
        fi

        uv {{ UV_OPTIONS }} run python scripts/gen-viz-schedule-plan.py \
            --events-jsonl "$events_jsonl" \
            --output-json "$output_json"
    done

# 检查 Agent Skill 数据是否合法
validate-agent-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-agent-skill.py --validate

# 检查: `openspec/` 脱敏 (自动叠加本地 `sanitize_rules.local.yaml`; 默认 dry-run; 需要 YES 才执行)
openspec-sanitize CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    confirm="{{ CONFIRM }}"
    if [ "$confirm" = "YES" ] || [ "$confirm" = "CONFIRM=YES" ]; then
        uv {{ UV_OPTIONS }} run python scripts/sanitize.py --apply --root openspec
        exit 0
    fi
    if [ -n "$confirm" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "$confirm" >&2
    fi
    uv {{ UV_OPTIONS }} run python scripts/sanitize.py --check --root openspec
    echo ""
    echo "[info] dry-run only. Apply with: just openspec-sanitize CONFIRM=YES"

# 检查: OpenSpec 提案/规范的脱敏与结构校验 (自动叠加本地 `sanitize_rules.local.yaml`; 缺失时脚本仅在非 CI 告警)
openspec-check: openspec-sanitize
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v openspec >/dev/null 2>&1; then
        uv {{ UV_OPTIONS }} run openspec validate --all --strict --no-interactive
        exit 0
    fi

    ci_value="$(printf '%s' "${CI:-}" | tr '[:upper:]' '[:lower:]')"
    case "$ci_value" in
        ""|0|false|no|off)
            echo "[error] openspec CLI not found; install it before running openspec-check." >&2
            exit 2
            ;;
        *)
            echo "[warn] openspec CLI not found in CI; skipping openspec validate --all --strict --no-interactive." >&2
            exit 0
            ;;
    esac

# 工具: 统一主包/子包/前端版本 (默认 dry-run; 需要 YES 才执行)
bump-versions VERSION="" CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    args=()
    if [ -n "{{ VERSION }}" ]; then
        args+=( --version "{{ VERSION }}" )
    fi
    if [ "{{ CONFIRM }}" = "YES" ] || [ "{{ CONFIRM }}" = "CONFIRM=YES" ]; then
        args+=( --apply )
    elif [ -n "{{ CONFIRM }}" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "{{ CONFIRM }}" >&2
    fi
    uv {{ UV_OPTIONS }} run python scripts/bump-versions.py "${args[@]}"

# 生成: Agent Skill 数据
gen-agent-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-agent-skill.py

# 生成: 文档站点受控生成物(含 injected blocks)
gen-docs:
    uv {{ UV_OPTIONS }} run python scripts/gen-docs.py

# 检查: docs 生成物是否有 drift
docs-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-docs.py --check

# 生成: 所有需要生成的数据
gen: gen-project-constants gen-yaml-dsl-schema gen-yaml-dsl-editor-schema gen-agent-skill gen-viz-data gen-viz-schedule-plan gen-docs

# 检查: 类型检查
type-check:
    uv {{ UV_OPTIONS }} run basedpyright src/scalim/ # --level error

# 检查: Docker 可用性
is-docker-available:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! docker version >/dev/null 2>&1; then
        echo "[error] docker unavailable; please start Docker and retry" >&2
        exit 1
    fi

# 检查: 核心链路更严格的类型边界(以 `pyproject.toml` 的 `tool.basedpyright.strict` 为准)
type-check-core-tight:
    uv {{ UV_OPTIONS }} run basedpyright $(uv {{ UV_OPTIONS }} run scripts/toml-get.py --file pyproject.toml --key tool.basedpyright.strict --format shell-words)

# 检查: 格式化&Lint (只检查;不改文件)
lint: type-check type-check-core-tight
    uv {{ UV_OPTIONS }} run ruff format --check .
    uv {{ UV_OPTIONS }} run ruff check .

# 检查: 类型错误检查 / lint错误并修复
lintfix: type-check
    uv {{ UV_OPTIONS }} run ruff format .
    uv {{ UV_OPTIONS }} run ruff check --fix .

# 检查: 文档字符串/注释语言(中文为主;允许反引号包裹技术词)
py-doc-language-check:
    uv {{ UV_OPTIONS }} run python scripts/check-py-doc-language.py

# 检查: `src/scalim/` 运行时契约规则(`pyright` 顶层指令 + 严格顶层规则 + 类内 `if TYPE_CHECKING:` 条件方法)
top-level-pyright-pragmas-check:
    uv {{ UV_OPTIONS }} run python scripts/check-top-level-pyright-pragmas.py --strict-top-level

# 检查: `src/scalim/` 注释/文档字符串英文需用反引号包裹(更严格)
comments-cn-check:
    uv {{ UV_OPTIONS }} run python scripts/check-comments-cn.py

# 检查: 运行时输出文案语言(中文为主). 同时写入 `.tmp/artifacts/` 以便 CI 上传
py-output-language-check:
    uv {{ UV_OPTIONS }} run python scripts/check-py-output-language.py --report .tmp/artifacts/output-language.report.txt

# 检查: 运行单元测试
test:
    # Fast/local functional checks (bench excluded). Use for daily dev loops.
    uv {{ UV_OPTIONS }} run pytest tests/ -q -m "not bench"

# 压力测试: 运行
bench *ARGS:
    # Performance baseline run only. Typical workflows:
    # - Save baseline: `just bench-baseline-save`
    # - Compare vs latest baseline: `just bench-compare`
    # - Gate regressions (default mean:10%): `just bench-compare-fail` or `just bench-compare-fail "mean:5%"`
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" {{ ARGS }}

# 压力测试: 保存基准
bench-baseline-save:
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-save baseline -o addopts=""

# 压力测试: 对比基准
bench-compare:
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-compare -o addopts=""

# 压力测试: 对比基准(失败阈值)
bench-compare-fail THRESH="mean:10%":
    # Default: mean:10%. Override: `just bench-compare-fail "mean:5%"`
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-compare --benchmark-compare-fail {{ THRESH }} -o addopts=""

# 内存压力测试: 运行
bench-memray *ARGS:
    # Memray memory profiling (dev-only). Outputs to .benchmarks/memray/
    mkdir -p .benchmarks/memray
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" --memray --memray-bin-path .benchmarks/memray {{ ARGS }}

# 内存压力测试: 显示最耗内存的分配
bench-memray-most MOST:
    # Show top allocation sites while collecting memray output.
    mkdir -p .benchmarks/memray
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" --memray --memray-bin-path .benchmarks/memray --most-allocations {{ MOST }}

# 交互笔记: 打开笔记首页
notebook:
    uv {{ UV_OPTIONS }} run marimo edit notebooks/marimo/

# 运行示例: 大数据的示例
examples-big-data:
    uv {{ UV_OPTIONS }} run python notebooks/marimo/examples/demo_big_data_report/demo_a0_main.py

# 运行示例: 运行所有示例
examples:
    #!/usr/bin/env bash
    set -e
    shopt -s nullglob

    tmpdir="$(mktemp -d)"
    cleanup() {
        rm -rf "$tmpdir"
    }
    trap cleanup EXIT

    group_titles=(
        "demo_big_data_report"
        "demo_big_data_report (yaml dsl)"
    )
    group_globs=(
        "notebooks/marimo/examples/demo_big_data_report/demo_*.py"
        "notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/demo_*.py"
    )

    pids=()
    outs=()
    group_start=()
    group_count=()

    for idx in "${!group_titles[@]}"; do
        files=( ${group_globs[$idx]} )
        group_start+=( "${#pids[@]}" )
        group_count+=( "${#files[@]}" )
        for f in "${files[@]}"; do
            out="$tmpdir/out_${#pids[@]}.log"
            (
                echo "Running: $f"
                PYTHONPATH="{{ justfile_directory() }}${PYTHONPATH:+:$PYTHONPATH}" uv {{ UV_OPTIONS }} run python "$f"
            ) >"$out" 2>&1 &
            pids+=( "$!" )
            outs+=( "$out" )
        done
    done

    status=0
    done_count=0
    done=()
    total="${#pids[@]}"
    # Poll for completion so we can fail fast without relying on wait -n.
    while [ "$done_count" -lt "$total" ]; do
        progress=0
        for i in "${!pids[@]}"; do
            if [ "${done[$i]:-0}" -eq 1 ]; then
                continue
            fi
            pid="${pids[$i]}"
            if kill -0 "$pid" 2>/dev/null; then
                continue
            fi
            if ! wait "$pid"; then
                status=1
            fi
            done[$i]=1
            done_count=$((done_count + 1))
            progress=1
            if [ "$status" -ne 0 ]; then
                # Stop remaining jobs early on first failure.
                for j in "${!pids[@]}"; do
                    if [ "${done[$j]:-0}" -eq 0 ]; then
                        kill "${pids[$j]}" 2>/dev/null || true
                    fi
                done
                for j in "${!pids[@]}"; do
                    if [ "${done[$j]:-0}" -eq 0 ]; then
                        wait "${pids[$j]}" 2>/dev/null || true
                        done[$j]=1
                        done_count=$((done_count + 1))
                    fi
                done
                break 2
            fi
        done
        if [ "$progress" -eq 0 ]; then
            sleep 0.1
        fi
    done

    for idx in "${!group_titles[@]}"; do
        echo "=== ${group_titles[$idx]} ==="
        start=${group_start[$idx]}
        count=${group_count[$idx]}
        for ((i=0; i<count; i++)); do
            pos=$((start + i))
            cat "${outs[$pos]}"
        done
        echo ""
    done

    if [ "$status" -ne 0 ]; then
        exit "$status"
    fi

    echo "All examples completed!"

# QA: 仅py轻量的检查
quick-check-only-py: uv-lock-check lint py-doc-language-check top-level-pyright-pragmas-check comments-cn-check py-output-language-check project-constants-drift-check schema-drift-check docs-drift-check doc-governance-check stdlib-collisions-check openspec-check test

alias quick-qa-only-py := quick-check-only-py

# QA: 所有轻量的检查
quick-check: quick-check-only-py

alias quick-qa := quick-check

# QA: 仅py完整的检查
check-only-py: quick-check-only-py py36-compat-check py36-typingext-check examples bench bench-memray

# QA: 所有完整的检查
check: quick-check-only-py py36-compat-check py36-typingext-check frontend-check examples

alias qa := check

# 检查: `Python 3.6` 语法兼容性 (仅 `src/scalim/`)
py36-compat-check:
    #!/usr/bin/env bash
    set -euo pipefail

    if docker version >/dev/null 2>&1; then
        docker run --rm -e CI -v "{{ justfile_directory() }}:/repo" -w /repo python:3.6 python -m compileall -q src/scalim
        exit 0
    fi

    echo "[error] docker unavailable; py36-compat-check requires docker. Please install/start docker and retry." >&2
    exit 1

# 检查: `Python 3.6` + `typing-extensions==4.1.1` 隔离环境兼容性
py36-typingext-check:
    #!/usr/bin/env bash
    set -euo pipefail

    if docker version >/dev/null 2>&1; then
        docker run --rm -e CI -v "{{ justfile_directory() }}:/repo" -w /repo python:3.6 bash /repo/scripts/check-py36-typingext-docker.sh
        exit 0
    fi

    echo "[error] docker unavailable; py36-typingext-check requires docker. Please install/start docker and retry." >&2
    exit 1

# 清理缓存/产物 (默认 dry-run; 需要 YES 才执行)
clean-cache CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob

    confirm="{{ CONFIRM }}"
    root="{{ justfile_directory() }}"

    cd "$root"

    mode="dry-run"
    if [ "$confirm" = "YES" ]; then
        mode="execute"
    elif [ -n "$confirm" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "$confirm" >&2
    fi

    targets=()

    add_if_exists() {
        local p="$1"
        if [ -e "$p" ]; then
            targets+=( "$p" )
        fi
    }

    add_find_dirs() {
        local find_root="$1"
        local name="$2"

        if [ ! -d "$find_root" ]; then
            return 0
        fi

        while IFS= read -r d; do
            targets+=( "$d" )
        done < <(
            find "$find_root" \
                -type d \( -name .git -o -name .venv -o -name node_modules \) -prune -false \
                -o -type d -name "$name" -prune -print
        )
    }

    # light
    add_if_exists .ruff_cache
    add_if_exists .pytest_cache
    add_if_exists .mypy_cache
    add_if_exists .pytype
    add_if_exists .pyre
    add_if_exists .hypothesis
    add_if_exists .cache
    add_if_exists .benchmarks/memray
    add_if_exists .uv-cache

    add_if_exists .coverage
    for f in .coverage.*; do
        add_if_exists "$f"
    done
    add_if_exists coverage.xml
    add_if_exists htmlcov

    add_if_exists build
    add_if_exists dist
    add_if_exists site

    add_find_dirs . __pycache__
    # add_if_exists .tmp
    # add_find_dirs . .tmp

    while IFS= read -r d; do
        targets+=( "$d" )
    done < <(find . -maxdepth 3 -type d -name "*.egg-info" -prune -print)

    # Normalize + dedupe + sort
    if [ "${#targets[@]}" -eq 0 ]; then
        echo "MODE=$mode ROOT=$root"
        echo "[ok] nothing to clean"
        exit 0
    fi

    mapfile -t targets < <(
        printf "%s\n" "${targets[@]}" \
            | sed 's#^\./##' \
            | awk 'NF' \
            | sort -u
    )

    echo "MODE=$mode ROOT=$root"
    printf "%s\n" "${targets[@]}"

    if [ "$mode" = "dry-run" ]; then
        echo ""
        echo "Dry-run only."
        echo "To execute:"
        echo "  just clean-cache YES"
        exit 0
    fi

    git_tracked() {
        local p="$1"
        if ! command -v git >/dev/null 2>&1; then
            return 1
        fi
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            return 1
        fi
        git ls-files --error-unmatch -- "$p" >/dev/null 2>&1
    }

    safe_rm_rf() {
        local p="$1"

        case "$p" in
            ""|"."|"./")
                echo "[skip unsafe] empty or root path" >&2
                return 0
                ;;
            /*)
                echo "[skip unsafe] absolute path:" "$p" >&2
                return 0
                ;;
            ../*|./../*|*/../*|*/..|*/../)
                echo "[skip unsafe] path traversal:" "$p" >&2
                return 0
                ;;
        esac

        if git_tracked "$p"; then
            echo "[skip tracked]" "$p" >&2
            return 0
        fi

        rm -rf -- "$p"
        echo "[rm]" "$p" >&2
    }

    for p in "${targets[@]}"; do
        if [ -e "$p" ]; then
            safe_rm_rf "$p"
        fi
    done
