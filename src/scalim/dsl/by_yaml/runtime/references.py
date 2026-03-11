import importlib
import logging
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar, FrozenSet, List, Optional, Sequence, Tuple

from ....vendor.compact.typing_extensionsx import override
from .errors import ResolverError

resolver_logger = logging.getLogger("scalim.dsl.by_yaml.resolver")

_MIN_PARTS_COUNT = 2
_ALLOWLIST_WILDCARD = "*"

ALLOWLIST_WILDCARD_MODULES_WARNING = "在 `allowed_modules` 中使用允许列表通配符 `*`: 将允许所有模块. 生产环境请使用严格允许列表."
ALLOWLIST_WILDCARD_FUNCTIONS_WARNING = "在 `allowed_functions` 中使用允许列表通配符 `*`: 将允许所有函数. 生产环境请使用严格允许列表."

RELATIVE_REFERENCE_BASE_REQUIRED = (
    "Relative module reference '{}' requires a base module path derived from `yaml_path` + `sys.path`. "
    "Fix: use `scalim.dsl.by_yaml.run/compile(yaml_path=...)`, or provide `base_module_path` when creating the resolver."
)


@dataclass(frozen=True)
class ParsedReference:
    reference: str
    module_path: str
    attr_path: Tuple[str, ...]
    style: str

    @property
    def entry_attr(self) -> str:
        return self.attr_path[0]


class ReferenceParser:
    def parse(self, reference: str) -> ParsedReference:
        if ":" in reference:
            return self._parse_class_style(reference)
        return self._parse_dotted_style(reference)

    def _parse_class_style(self, reference: str) -> ParsedReference:
        parts = reference.split(":")
        if len(parts) != _MIN_PARTS_COUNT:
            msg = "Invalid class-style reference '{}'. Expected 'module.path:attr' or 'module.path:obj.method'".format(reference)
            raise ResolverError(msg)
        module_path, attr_path = parts
        attr_parts = tuple(attr_path.split("."))
        return ParsedReference(reference=reference, module_path=module_path, attr_path=attr_parts, style="class")

    def _parse_dotted_style(self, reference: str) -> ParsedReference:
        parts = reference.rsplit(".", 1)
        if len(parts) < _MIN_PARTS_COUNT:
            msg = "Invalid dotted reference '{}'. Expected 'module.path.function'".format(reference)
            raise ResolverError(msg)
        module_path, func_name = parts
        if func_name.startswith("__"):
            msg = "Access to dunder attribute '{}' is forbidden in reference '{}'".format(func_name, reference)
            raise ResolverError(msg)
        return ParsedReference(reference=reference, module_path=module_path, attr_path=(func_name,), style="dotted")


class ResolverPolicy:
    _allowed_modules: Optional[FrozenSet[str]]
    _allowed_functions: Optional[FrozenSet[str]]
    _allow_all_modules: bool
    _allow_all_functions: bool

    def __init__(
        self,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
    ) -> None:
        self._allowed_modules = allowed_modules
        self._allowed_functions = allowed_functions
        self._allow_all_modules = self._has_wildcard(self._allowed_modules)
        self._allow_all_functions = self._has_wildcard(self._allowed_functions)

    @property
    def allow_all_modules(self) -> bool:
        return self._allow_all_modules

    @property
    def allow_all_functions(self) -> bool:
        return self._allow_all_functions

    @property
    def has_allowlist(self) -> bool:
        return self._allowed_modules is not None or self._allowed_functions is not None

    def check(self, module_path: str, func_name: str) -> None:
        if self._is_allowed_function(module_path, func_name):
            return
        if self._allowed_functions is not None and self._allowed_modules is None:
            full_path = "{}:{}".format(module_path, func_name)
            msg = "Function '{}' is not in the allowed functions list".format(full_path)
            if "." in func_name:
                msg += " (class-style allowlist must include full attr chain, e.g. 'pkg.mod:Obj.safe' or 'pkg.mod.Obj.safe')"
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
            msg = "Module '{}' is not in the allowed modules list".format(module_path)
            raise ResolverError(msg)

    def _is_allowed_function(self, module_path: str, func_name: str) -> bool:
        if self._allowed_functions is None:
            return False
        if self._allow_all_functions:
            return True

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

    def __init__(
        self,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        max_cache_size: int = DEFAULT_CACHE_MAX_SIZE,
    ) -> None:
        if int(max_cache_size) < 1:
            msg = "max_cache_size must be >= 1"
            raise ValueError(msg)
        # 推荐: 仅允许统一的加载模块或明确的函数列表.
        self._policy = ResolverPolicy(allowed_modules=allowed_modules, allowed_functions=allowed_functions)
        self._parser = ReferenceParser()
        self._cache = OrderedDict()
        self._max_cache_size = int(max_cache_size)
        # 注意:
        # - 通配符白名单(`\"*\"`)仅用于可信/内部场景与快速迭代.
        # - 它会实质上关闭白名单约束;不要用于不可信的 `YAML`/配置输入.
        if self._policy.allow_all_modules:
            resolver_logger.warning(ALLOWLIST_WILDCARD_MODULES_WARNING)
        if self._policy.allow_all_functions:
            resolver_logger.warning(ALLOWLIST_WILDCARD_FUNCTIONS_WARNING)

    def has_allowlist(self) -> bool:
        return self._policy.has_allowlist

    def resolve(self, reference: str) -> Callable[..., Any]:
        cached = self._cache.get(reference)
        if cached is not None:
            self._cache.move_to_end(reference)
            return cached

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
                msg = "Access to dunder attribute '{}' is forbidden in reference '{}'".format(attr_name, parsed.reference)
                raise ResolverError(msg)
            if not hasattr(obj, attr_name):
                msg = "Object '{}' has no attribute '{}'".format(obj, attr_name)
                raise ResolverError(msg)
            obj = getattr(obj, attr_name)

        if not callable(obj):
            msg = "'{}:{}' is not callable".format(parsed.module_path, ".".join(parsed.attr_path))
            raise ResolverError(msg)

        return obj

    def _resolve_dotted_style(self, parsed: ParsedReference) -> Callable[..., Any]:
        func_name = parsed.entry_attr

        self._policy.check(parsed.module_path, func_name)

        module = self._import_module(parsed.module_path)

        if not hasattr(module, func_name):
            msg = "Module '{}' has no attribute '{}'".format(parsed.module_path, func_name)
            raise ResolverError(msg)

        obj = getattr(module, func_name)
        if not callable(obj):
            msg = "'{}' is not callable".format(parsed.reference)
            raise ResolverError(msg)

        return obj

    def _import_module(self, module_path: str) -> Any:
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            msg = "Failed to import module '{}': {}".format(module_path, e)
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
        max_cache_size: int = PythonReferenceResolver.DEFAULT_CACHE_MAX_SIZE,
        base_module_path: Optional[str] = None,
    ) -> None:
        super(SecurePythonReferenceResolver, self).__init__(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
            max_cache_size=max_cache_size,
        )
        self._base_module_path = base_module_path

    @override
    def resolve(self, reference: str) -> Callable[..., Any]:
        if reference.startswith("."):
            normalized = self._normalize_reference(reference)
            self._security_check(normalized)
            return super(SecurePythonReferenceResolver, self).resolve(normalized)

        self._security_check(reference)
        return super(SecurePythonReferenceResolver, self).resolve(reference)

    def _normalize_reference(self, reference: str) -> str:
        if ":" in reference:
            parts = reference.split(":")
            if len(parts) != _MIN_PARTS_COUNT:
                msg = "Invalid class-style reference '{}'. Expected 'module.path:attr' or 'module.path:obj.method'".format(reference)
                raise ResolverError(msg)
            module_path, attr_path = parts
            absolute_module_path = self._normalize_relative_module_path(module_path, reference=reference)
            return "{}:{}".format(absolute_module_path, attr_path)

        module_path, func_name = reference.rsplit(".", 1)
        if not module_path:
            msg = "Invalid relative dotted reference '{}'. Expected '.module.path.function'".format(reference)
            raise ResolverError(msg)
        absolute_module_path = self._normalize_relative_module_path(module_path, reference=reference)
        return "{}.{}".format(absolute_module_path, func_name)

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
        if not rest:
            msg = "Invalid relative module path '{}' in reference '{}' (missing module path after leading dots)".format(
                module_path, reference
            )
            raise ResolverError(msg)

        base_parts = [p for p in str(base).split(".") if p] if base else []
        up_levels = dot_count - 1
        if up_levels > len(base_parts):
            msg = "Relative module reference '{}' goes beyond root (base_module_path='{}')".format(reference, base)
            raise ResolverError(msg)

        prefix_parts = base_parts[: len(base_parts) - up_levels] if up_levels else base_parts

        rest_parts = rest.split(".")
        invalid = [p for p in rest_parts if not p.isidentifier()]
        if invalid:
            msg = "Invalid relative module path '{}' in reference '{}' (illegal identifier segment: '{}')".format(
                module_path, reference, invalid[0]
            )
            raise ResolverError(msg)

        absolute_parts = prefix_parts + rest_parts
        return ".".join(absolute_parts)

    def _security_check(self, reference: str) -> None:
        if ":" in reference:
            module_path, attr_path = reference.split(":", 1)
            attr_parts = attr_path.split(".")
        else:
            parts = reference.rsplit(".", 1)
            if len(parts) < _MIN_PARTS_COUNT:
                msg = "Invalid reference format: '{}'".format(reference)
                raise ResolverError(msg)
            module_path, func_name = parts
            attr_parts = [func_name]

        module_parts = module_path.split(".")
        for part in module_parts:
            if part in self.DANGEROUS_MODULES:
                msg = "Security violation: Module '{}' is in the dangerous modules list".format(part)
                raise ResolverError(msg)
            if "__" in part:
                msg = "Security violation: Reference contains dangerous pattern '__'"
                raise ResolverError(msg)
            if part == "lambda":
                msg = "Security violation: Reference contains dangerous pattern 'lambda'"
                raise ResolverError(msg)

        for part in attr_parts:
            if part in self.DANGEROUS_FUNCTIONS or part == "lambda":
                msg = "Security violation: Function '{}' is in the dangerous functions list".format(part)
                raise ResolverError(msg)
            if "__" in part:
                msg = "Security violation: Reference contains dangerous pattern '__'"
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
        msg = "yaml_path is required to derive base module path"
        raise ResolverError(msg)

    yaml_dir = Path(raw_yaml_path).expanduser().resolve(strict=False).parent
    cwd_path = Path(cwd).expanduser().resolve(strict=False) if cwd else Path.cwd().resolve(strict=False)

    candidates = _collect_sys_path_prefixes(yaml_dir=yaml_dir, sys_path=sys_path, cwd_path=cwd_path)

    if not candidates:
        msg = (
            "Cannot derive base module path from yaml_path '{}': directory '{}' is not under any sys.path entry. "
            "Fix: add the package root to PYTHONPATH (or sys.path), or use absolute module references."
        ).format(raw_yaml_path, str(yaml_dir))
        raise ResolverError(msg)

    prefix = max(candidates, key=lambda p: len(p.parts))
    rel_path = yaml_dir.relative_to(prefix)
    if rel_path == Path():
        return ""

    parts = [p for p in rel_path.parts if p and p != "."]
    _validate_module_parts(parts=parts, raw_yaml_path=raw_yaml_path, yaml_dir=yaml_dir, prefix=prefix)

    return ".".join(parts)


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
            "Cannot derive base module path from yaml_path '{}': directory segment '{}' (from '{}', sys.path prefix='{}') "
            "is not a valid Python identifier. Fix: rename the directory segment or use absolute references."
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
