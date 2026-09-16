#!/usr/bin/env bash
# QA 门禁输出控制助手 (SSOT: 本文件; 由 justfile 各 gate 配方 source).
#
# 三档语义 (QA_VERBOSE):
#   L0 静默 (默认; 空/"0"/"off"/"false"/"no"): 捕获步骤 stdout+stderr;
#        通过 → 打印一行 `[pass] <step>: <工具自带摘要尾行>`;
#        失败 → 全量输出到 stderr + 原退出码 (绝不吞没).
#   L1 摘要 ("1"): 实时流式输出 (各工具自带 --quiet 旗标由配方层决定).
#   L2 全量 (其他真值, 如 "2"): 实时流式输出全量, 无 quiet 旗标.
#
# 用法 (shebang 配方内):
#   source "{{ justfile_directory() }}/scripts/qa-step.sh"
#   qa_step "type-check" uv run basedpyright src/scalim/ --level error
#   qa_step "test-gate" bash -o pipefail -c 'uv run pytest ... | sed ...'

# 输出档位: 0 / 1 / 2
qa_level() {
  case "${QA_VERBOSE:-}" in
    "" | 0 | off | false | no) printf '0\n' ;;
    1) printf '1\n' ;;
    *) printf '2\n' ;;
  esac
}

# 通过时打印一行摘要: [pass] <step>: <捕获输出中最后一行非空行>
_qa_print_pass() {
  local name="$1" out="$2"
  local last
  last="$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1 || true)"
  if [ -n "$last" ]; then
    last="$(printf '%s' "$last" | cut -c1-300)"
    printf '[pass] %s: %s\n' "$name" "$last"
  else
    printf '[pass] %s\n' "$name"
  fi
}

qa_step() {
  local name="$1"
  shift
  if [ "$(qa_level)" -eq 0 ]; then
    local rc=0 out
    out="$("$@" 2>&1)" || rc=$?
    if [ "$rc" -ne 0 ]; then
      printf '[FAIL] %s (rc=%s)\n' "$name" "$rc" >&2
      [ -n "$out" ] && printf '%s\n' "$out" >&2
      return "$rc"
    fi
    _qa_print_pass "$name" "$out"
    return 0
  fi
  "$@"
}
