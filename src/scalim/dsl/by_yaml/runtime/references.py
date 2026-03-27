import importlib
import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, ClassVar, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from ...._internal.loggingx import format_kv, prefix
from ....vendor.compact.typing_extensionsx import override
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX, ParsedReference, ReferenceSyntaxError, parse_python_reference
from .allowlist_policy import ResolverTrustedMode
from .builtin_callables import resolve_builtin_callable_reference
from .errors import ResolverError

resolver_logger = logging.getLogger("scalim.dsl.by_yaml.resolver")

_ALLOWLIST_WILDCARD = "*"

_TRUSTED_MODE_ALLOW_ALL_MODULES_WARNING = (
    "已启用 resolver_trusted_mode=trusted_allow_all_modules: resolver allowlist 已放宽为允许任意模块. "
    "此模式等效于授予 YAML 配置代码执行权限,仅用于可信输入/内部测试."
)

_TRUSTED_MODE_ENV_GATE = "SCALIM_ALLOW_TRUSTED_ALL_MODULES"

_TRUSTED_MODE_ENV_GATE_REJECTED_MSG = (
    "trusted_allow_all_modules 需要显式设置环境变量 {}=1 方可启用. 此模式等效于代码执行权限,仅用于完全可信的输入."
).format(_TRUSTED_MODE_ENV_GATE)

_WILDCARD_MODULES_REJECTED_BY_DEFAULT_MSG = (
    "不允许在 `allowed_modules` 中使用通配符 `*` (默认 resolver_trusted_mode=strict_allowlist 会 fail-fast). "
    "迁移: 若仅做模块约束,请改为显式模块前缀 allowlist (例如 allowed_modules=frozenset(['myapp.loaders'])); "
    "若确需在可信输入场景放宽为允许任意模块,请显式设置 "
    "resolver_trusted_mode=trusted_allow_all_modules 且 allowed_modules=frozenset(['*'])."
)

_WILDCARD_FUNCTIONS_REJECTED_MSG = (
    "不允许 `allowed_functions={'*'}`: 该配置无法表达“仍受模块 allowlist 约束”,且容易造成误用脚枪. "
    "迁移: 若希望仅做模块约束,请移除 allowed_functions 并仅设置 allowed_modules; "
    "若希望放宽为允许任意模块,请使用 resolver_trusted_mode=trusted_allow_all_modules."
)

_TRUSTED_MODE_MIXED_ALLOWLIST_REJECTED_MSG = (
    "当 resolver_trusted_mode=trusted_allow_all_modules 时,仅允许以下配置组合: "
    "allowed_modules=frozenset(['*']), allowed_functions=None. "
    "请勿与显式 allowlist 混用(避免制造“部分约束仍生效”的错觉)."
)


def _has_wildcard(values: Optional[FrozenSet[str]]) -> bool:
    return values is not None and _ALLOWLIST_WILDCARD in values


RELATIVE_REFERENCE_BASE_REQUIRED = (
    "相对模块引用 '{}' 需要先根据 `yaml_path` + `sys.path` 推导 `base_module_path`. "
    "修复方式: 使用 `scalim.dsl.by_yaml.run/compile(yaml_path=...)`,"
    " 或在创建 resolver 时显式传入 `base_module_path`."
)


class ReferenceParser:
    def parse(self, reference: str) -> ParsedReference:
        try:
            return parse_python_reference(reference)
        except ReferenceSyntaxError as exc:
            raise ResolverError(str(exc)) from exc


class ResolverPolicy:
    _allowed_modules: Optional[FrozenSet[str]]
    _allowed_functions: Optional[FrozenSet[str]]
    _allow_all_modules: bool

    def __init__(
        self,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
    ) -> None:
        self._allowed_modules = allowed_modules
        self._allowed_functions = allowed_functions
        self._allow_all_modules = self._has_wildcard(self._allowed_modules)

    @property
    def has_allowlist(self) -> bool:
        return self._allowed_modules is not None or self._allowed_functions is not None

    def check(self, module_path: str, func_name: str) -> None:
        if self._is_allowed_function(module_path, func_name):
            return
        if self._allowed_functions is not None and self._allowed_modules is None:
            full_path = "{}:{}".format(module_path, func_name)
            msg = "函数 '{}' 不在 `allowed_functions` 允许列表中".format(full_path)
            if "." in func_name:
                msg += " (类式引用的允许列表必须写完整属性链,例如 `pkg.mod:Obj.safe` 或 `pkg.mod.Obj.safe`)"
            raise ResolverError(msg)
        self._check_allowed_module(module_path)

    def _check_allowed_module(self, module_path: str) -> None:
        if self._allowed_modules is None:
            return
        if self._allow_all_modules:
            return

        allowed = False
        for allowed_mod in self._allowed_modules:
            if module_path == allowed_mod or module_path.startswith(allowed_mod + "."):
                allowed = True
                break

        if not allowed:
            msg = "模块 '{}' 不在 `allowed_modules` 允许列表中".format(module_path)
            raise ResolverError(msg)

    def _is_allowed_function(self, module_path: str, func_name: str) -> bool:
        if self._allowed_functions is None:
            return False

        full_path = "{}:{}".format(module_path, func_name)
        dotted_path = "{}.{}".format(module_path, func_name)
        return full_path in self._allowed_functions or dotted_path in self._allowed_functions

    @staticmethod
    def _has_wildcard(values: Optional[FrozenSet[str]]) -> bool:
        return values is not None and _ALLOWLIST_WILDCARD in values


class PythonReferenceResolver:
    DEFAULT_CACHE_MAX_SIZE: ClassVar[int] = 256

    _policy: ResolverPolicy
    _parser: ReferenceParser
    _cache: "OrderedDict[str, Callable[..., Any]]"
    _max_cache_size: int
    _builtin_callables_by_id: Optional[Mapping[str, Callable[..., Any]]]
    _public_builtin_callable_ids: Optional[Tuple[str, ...]]

    def __init__(
        self,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
        max_cache_size: int = DEFAULT_CACHE_MAX_SIZE,
        builtin_callables_by_id: Optional[Mapping[str, Callable[..., Any]]] = None,
        public_builtin_callable_ids: Optional[Sequence[str]] = None,
    ) -> None:
        if int(max_cache_size) < 1:
            msg = "`max_cache_size` 必须 >= 1"
            raise ValueError(msg)
        if _has_wildcard(allowed_functions):
            raise ValueError(_WILDCARD_FUNCTIONS_REJECTED_MSG)
        if resolver_trusted_mode == ResolverTrustedMode.TRUSTED_ALLOW_ALL_MODULES:
            if os.environ.get(_TRUSTED_MODE_ENV_GATE) != "1":
                raise ValueError(_TRUSTED_MODE_ENV_GATE_REJECTED_MSG)
            if allowed_functions is not None or allowed_modules != frozenset([_ALLOWLIST_WILDCARD]):
                raise ValueError(_TRUSTED_MODE_MIXED_ALLOWLIST_REJECTED_MSG)
            resolver_logger.warning(
                "%s%s (%s)",
                prefix("resolver"),
                _TRUSTED_MODE_ALLOW_ALL_MODULES_WARNING,
                format_kv(
                    resolver_trusted_mode=str(resolver_trusted_mode),
                    allowed_modules=_ALLOWLIST_WILDCARD,
                ),
            )
        elif _has_wildcard(allowed_modules):
            raise ValueError(_WILDCARD_MODULES_REJECTED_BY_DEFAULT_MSG)
        # 推荐: 仅允许统一的加载模块或明确的函数列表.
        self._policy = ResolverPolicy(allowed_modules=allowed_modules, allowed_functions=allowed_functions)
        self._parser = ReferenceParser()
        self._cache = OrderedDict()
        self._max_cache_size = int(max_cache_size)
        self._builtin_callables_by_id = builtin_callables_by_id
        self._public_builtin_callable_ids = tuple(public_builtin_callable_ids) if public_builtin_callable_ids is not None else None

    def has_allowlist(self) -> bool:
        return self._policy.has_allowlist

    def resolve(self, reference: str) -> Callable[..., Any]:
        cached = self._cache.get(reference)
        if cached is not None:
            self._cache.move_to_end(reference)
            return cached

        raw = str(reference or "").strip()
        if raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
            result = resolve_builtin_callable_reference(
                reference,
                callables_by_id=self._builtin_callables_by_id,
                public_ids=self._public_builtin_callable_ids,
            )
            self._cache[reference] = result
            if len(self._cache) > self._max_cache_size:
                _ = self._cache.popitem(last=False)
            return result

        parsed = self._parser.parse(reference)
        if parsed.style == "class":
            result = self._resolve_class_style(parsed)
        else:
            result = self._resolve_dotted_style(parsed)

        self._cache[reference] = result
        if len(self._cache) > self._max_cache_size:
            _ = self._cache.popitem(last=False)
        return result

    def clear_cache(self) -> None:
        self._cache.clear()

    def _resolve_class_style(self, parsed: ParsedReference) -> Callable[..., Any]:
        self._policy.check(parsed.module_path, ".".join(parsed.attr_path))

        module = self._import_module(parsed.module_path)

        obj: Any = module
        for attr_name in parsed.attr_path:
            if attr_name.startswith("__"):
                msg = "引用 '{}' 禁止访问双下划线属性 '{}'".format(parsed.reference, attr_name)
                raise ResolverError(msg)
            if not hasattr(obj, attr_name):  # pragma: allow-dynattr dsl: resolver attr traversal
                msg = "对象 '{}' 不存在属性 '{}'".format(obj, attr_name)
                raise ResolverError(msg)
            obj = getattr(obj, attr_name)  # pragma: allow-dynattr dsl: resolver attr traversal

        if not callable(obj):
            msg = "'{}:{}' 不是可调用对象".format(parsed.module_path, ".".join(parsed.attr_path))
            raise ResolverError(msg)

        return obj

    def _resolve_dotted_style(self, parsed: ParsedReference) -> Callable[..., Any]:
        func_name = parsed.entry_attr

        if func_name.startswith("__"):
            msg = "引用 '{}' 禁止访问双下划线属性 '{}'".format(parsed.reference, func_name)
            raise ResolverError(msg)

        self._policy.check(parsed.module_path, func_name)

        module = self._import_module(parsed.module_path)

        if not hasattr(module, func_name):  # pragma: allow-dynattr dsl: module callable resolution
            msg = "模块 '{}' 不存在属性 '{}'".format(parsed.module_path, func_name)
            raise ResolverError(msg)

        obj = getattr(module, func_name)  # pragma: allow-dynattr dsl: module callable resolution
        if not callable(obj):
            msg = "'{}' 不是可调用对象".format(parsed.reference)
            raise ResolverError(msg)

        return obj

    def _import_module(self, module_path: str) -> Any:
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            msg = "导入模块 '{}' 失败: {}".format(module_path, e)
            raise ResolverError(msg) from e


class SecurePythonReferenceResolver(PythonReferenceResolver):
    DANGEROUS_MODULES: ClassVar[FrozenSet[str]] = frozenset(
        [
            "os",
            "sys",
            "subprocess",
            "shutil",
            "importlib",
            "builtins",
            "__builtin__",
            "eval",
            "exec",
            "compile",
            "pickle",
            "marshal",
            "shelve",
            "socket",
            "urllib",
            "http",
            "ftplib",
            "telnetlib",
            "smtplib",
            "poplib",
            "imaplib",
            "nntplib",
            "ctypes",
            "multiprocessing",
        ]
    )

    DANGEROUS_FUNCTIONS: ClassVar[FrozenSet[str]] = frozenset(
        [
            "eval",
            "exec",
            "compile",
            "__import__",
            "open",
            "input",
            "globals",
            "locals",
            "vars",
            "dir",
            "getattr",
            "setattr",
            "delattr",
            "hasattr",
        ]
    )

    _base_module_path: Optional[str]

    def __init__(
        self,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST,
        max_cache_size: int = PythonReferenceResolver.DEFAULT_CACHE_MAX_SIZE,
        base_module_path: Optional[str] = None,
        builtin_callables_by_id: Optional[Mapping[str, Callable[..., Any]]] = None,
        public_builtin_callable_ids: Optional[Sequence[str]] = None,
    ) -> None:
        super(SecurePythonReferenceResolver, self).__init__(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
            resolver_trusted_mode=resolver_trusted_mode,
            max_cache_size=max_cache_size,
            builtin_callables_by_id=builtin_callables_by_id,
            public_builtin_callable_ids=public_builtin_callable_ids,
        )
        self._base_module_path = base_module_path

    @override
    def resolve(self, reference: str) -> Callable[..., Any]:
        raw = str(reference or "").strip()
        if raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
            return super(SecurePythonReferenceResolver, self).resolve(reference)

        if reference.startswith("."):
            normalized = self._normalize_reference(reference)
            self._security_check(normalized)
            return super(SecurePythonReferenceResolver, self).resolve(normalized)

        self._security_check(reference)
        return super(SecurePythonReferenceResolver, self).resolve(reference)

    def _normalize_reference(self, reference: str) -> str:
        parsed = self._parser.parse(reference)
        absolute_module_path = self._normalize_relative_module_path(parsed.module_path, reference=reference)
        if parsed.style == "class":
            return "{}:{}".format(absolute_module_path, ".".join(parsed.attr_path))
        return "{}.{}".format(absolute_module_path, parsed.entry_attr)

    def _normalize_relative_module_path(self, module_path: str, *, reference: str) -> str:
        base = self._base_module_path
        if base is None:
            msg = RELATIVE_REFERENCE_BASE_REQUIRED.format(reference)
            raise ResolverError(msg)

        dot_count = 0
        for ch in module_path:
            if ch != ".":
                break
            dot_count += 1

        rest = module_path[dot_count:]
        base_parts = [p for p in str(base).split(".") if p] if base else []
        up_levels = dot_count - 1
        if up_levels > len(base_parts):
            msg = "相对模块引用 '{}' 超出了根包范围(`base_module_path='{}'`)".format(reference, base)
            raise ResolverError(msg)

        prefix_parts = base_parts[: len(base_parts) - up_levels] if up_levels else base_parts

        rest_parts = rest.split(".")
        absolute_parts = prefix_parts + rest_parts
        return ".".join(absolute_parts)

    def _security_check(self, reference: str) -> None:
        parsed = self._parser.parse(reference)
        module_path = parsed.module_path
        attr_parts = list(parsed.attr_path)

        module_parts = module_path.split(".")
        for part in module_parts:
            if part in self.DANGEROUS_MODULES:
                msg = "安全限制: 模块 '{}' 位于危险模块列表中".format(part)
                raise ResolverError(msg)
            if "__" in part:
                msg = "安全限制: 引用中包含危险模式 '__'"
                raise ResolverError(msg)
            if part == "lambda":
                msg = "安全限制: 引用中包含危险模式 'lambda'"
                raise ResolverError(msg)

        for part in attr_parts:
            if part in self.DANGEROUS_FUNCTIONS or part == "lambda":
                msg = "安全限制: 函数 '{}' 位于危险函数列表中".format(part)
                raise ResolverError(msg)
            if "__" in part:
                msg = "安全限制: 引用中包含危险模式 '__'"
                raise ResolverError(msg)


def derive_base_module_path(
    yaml_path: str,
    *,
    sys_path: Optional[Sequence[Optional[str]]] = None,
    cwd: Optional[str] = None,
) -> str:
    """从 `yaml_path` + `sys.path` 推导相对引用的基准模块路径(`base module path`).

    规则:
    - 以 YAML 文件所在目录为基准(`Path(yaml_path).parent`)
    - 遍历 `sys.path` 找到 YAML 目录的前缀路径候选
    - 选择最长匹配
    - 将 `yaml_dir` 相对前缀的目录段用 `.` 拼接为模块路径
    """
    raw_yaml_path = str(yaml_path or "").strip()
    if not raw_yaml_path:
        msg = "推导 `base_module_path` 时必须提供 `yaml_path`"
        raise ResolverError(msg)

    yaml_dir = Path(raw_yaml_path).expanduser().resolve(strict=False).parent
    cwd_path = Path(cwd).expanduser().resolve(strict=False) if cwd else Path.cwd().resolve(strict=False)

    candidates = _collect_sys_path_prefixes(yaml_dir=yaml_dir, sys_path=sys_path, cwd_path=cwd_path)

    if not candidates:
        msg = (
            "无法根据 `yaml_path='{}'` 推导 `base_module_path`: 目录 '{}' 不在任何 `sys.path` 条目下. "
            "修复方式: 把包根目录加入 `PYTHONPATH`(或 `sys.path`),或者改用绝对模块引用."
        ).format(raw_yaml_path, str(yaml_dir))
        raise ResolverError(msg)

    valid: List[Tuple[Tuple[str, ...], Path]] = []
    for sys_prefix in candidates:
        rel_path = yaml_dir.relative_to(sys_prefix)
        if rel_path == Path():
            valid.append(((), sys_prefix))
            continue
        parts = tuple(p for p in rel_path.parts if p and p != ".")
        try:
            _validate_module_parts(parts=parts, raw_yaml_path=raw_yaml_path, yaml_dir=yaml_dir, prefix=sys_prefix)
        except ResolverError:
            continue
        valid.append((parts, sys_prefix))

    if valid:
        # 选择“最长的模块路径”(更符合“YAML 文件所在目录对应模块路径”的直觉),
        # 同时避免在脚本执行场景下被 `sys.path[0]==yaml_dir` 误导为根包(`base_module_path=''`).
        parts, _prefix = max(valid, key=lambda item: (len(item[0]), -len(item[1].parts), str(item[1])))
        return ".".join(parts)

    # 若所有候选均非法(例如包含非标识符的目录段),沿用旧策略选择最长前缀并报错.
    sys_prefix = max(candidates, key=lambda p: len(p.parts))
    rel_path = yaml_dir.relative_to(sys_prefix)
    if rel_path == Path():
        return ""  # pragma: no cover  # pragma: allow-no-cover invariant: would have matched earlier valid-prefix branch

    parts = [p for p in rel_path.parts if p and p != "."]
    _validate_module_parts(parts=parts, raw_yaml_path=raw_yaml_path, yaml_dir=yaml_dir, prefix=sys_prefix)

    return ".".join(
        parts
    )  # pragma: no cover  # pragma: allow-no-cover invariant: valid parts would have matched earlier valid-prefix branch


def _normalize_sys_path_entry(entry: Optional[str], *, cwd_path: Path) -> Optional[Path]:
    if entry is None:
        return None
    item = str(entry)
    if item == "":
        return cwd_path
    p = Path(item)
    if not p.is_absolute():
        return (cwd_path / p).resolve(strict=False)
    return p.resolve(strict=False)


def _collect_sys_path_prefixes(*, yaml_dir: Path, sys_path: Optional[Sequence[Optional[str]]], cwd_path: Path) -> List[Path]:
    candidates: List[Path] = []
    for entry in list(sys_path) if sys_path is not None else list(sys.path):
        p = _normalize_sys_path_entry(entry, cwd_path=cwd_path)
        if p is None:
            continue
        try:
            _ = yaml_dir.relative_to(p)
        except ValueError:
            continue
        candidates.append(p)
    return candidates


def _validate_module_parts(*, parts: Sequence[str], raw_yaml_path: str, yaml_dir: Path, prefix: Path) -> None:
    for part in parts:
        if part.isidentifier():
            continue
        msg = (
            "无法根据 `yaml_path='{}'` 推导 `base_module_path`: 目录片段 '{}' (来自 '{}', sys.path 前缀='{}')"
            "不是合法的 Python 标识符. 修复方式: 重命名该目录片段,或改用绝对引用."
        ).format(raw_yaml_path, part, str(yaml_dir), str(prefix))
        raise ResolverError(msg)


__all__ = [
    "ParsedReference",
    "PythonReferenceResolver",
    "ReferenceParser",
    "ResolverPolicy",
    "SecurePythonReferenceResolver",
    "derive_base_module_path",
]
