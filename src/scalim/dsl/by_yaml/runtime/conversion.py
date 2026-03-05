import re
from collections import deque
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Hashable,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from ....spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr, build_stable_lookup_key_list
from ....spec.ir.demand import DemandIr
from ....spec.ir.fields import DerivedFieldIr, FieldIr
from ....spec.ir.relations import LookupStepIr
from ....spec.ir.sources import KeyIr, MainSourceIr, OrderByKeyIr, SourceIr
from ....typedefs import SourceSpecIrCacheMode
from ....utils.converters import NamedLookupCast, auto_normalize_key, auto_str_normalize, must_to_int, must_to_str
from ..config_parsing.call_by import CallByParseError, CallByValue, parse_call_by
from ..config_parsing.security import SecureComputeEngine, is_constant_compute_expression
from ..schema_dsl.constants import DEFAULT_BIND_AS, DEFAULT_BIND_CACHE_MODE
from ..schema_dsl.models import (
    BindConfig,
    DemandConfig,
    DerivedFieldConfig,
    InlineRelationConfig,
    LookupCastConfig,
    MainSourceConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from .errors import ALLOWLIST_REQUIRED_MSG, AllowlistRequiredError, ConversionError
from .references import PythonReferenceResolver, SecurePythonReferenceResolver

StepInfo = Tuple[str, str, LookupStepIr]

_SOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_CALL_BY_CTX_KEY = "$ctx"

if TYPE_CHECKING:
    from ....spec.ir.aliases import LoaderResultMapCallable, MainSourceRowIterableCallable


def _cast_int(value: Any) -> int:
    return int(value)


def _cast_str(value: Any) -> str:
    return str(value)


_VALUE_CASTS: Dict[str, Callable[[Any], Any]] = {
    "int": _cast_int,
    "str": _cast_str,
    "auto": auto_str_normalize,
}


class LookupCastRegistry:
    _BASE_CASTS: ClassVar[Dict[str, Callable[[Any], Optional[Hashable]]]] = {
        "auto": auto_normalize_key,
        "int": must_to_int,
        "str": must_to_str,
    }

    def build(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> Callable[[Any], Optional[Hashable]]:
        base = self._get_base_cast(lookup_cast)
        if not is_multi:
            return NamedLookupCast(lookup_cast.name, base)
        return NamedLookupCast(lookup_cast.name, self._wrap_multi(base))

    def _get_base_cast(self, lookup_cast: LookupCastConfig) -> Callable[[Any], Optional[Hashable]]:
        if lookup_cast.name == "sep_first":
            return self._build_sep_first(lookup_cast.sep)
        base = self._BASE_CASTS.get(lookup_cast.name)
        if base is None:
            msg = "Unknown lookup_cast: '{}'".format(lookup_cast.name)
            raise ConversionError(msg)
        return base

    def _build_sep_first(self, sep: Optional[str]) -> Callable[[Any], Optional[Hashable]]:
        separator = sep or ","

        def _cast(value: Any) -> Optional[Hashable]:
            if value is None:
                return None
            raw = str(value)
            first = raw.split(separator, maxsplit=1)[0].strip()
            if not first:
                return None
            return auto_normalize_key(first)

        return _cast

    def _wrap_multi(self, base: Callable[[Any], Optional[Hashable]]) -> Callable[[Any], Optional[Hashable]]:
        def _cast_multi(value: Any) -> Optional[Hashable]:
            if not isinstance(value, (list, tuple)):
                return None
            casted: List[Hashable] = []
            items = cast("Iterable[Any]", value)
            for item in items:
                converted = base(item)
                if converted is None:
                    return None
                casted.append(converted)
            return tuple(casted)

        return _cast_multi


def _validate_source_id(source_id: str, context: str) -> None:
    if not _SOURCE_ID_PATTERN.match(source_id):
        msg = "{}: source_id '{}' must match pattern [a-zA-Z_][a-zA-Z0-9_]*".format(context, source_id)
        raise ConversionError(msg)


class ConfigToIRConverter:
    @classmethod
    def from_allowlist(
        cls,
        *,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
    ) -> "ConfigToIRConverter":
        if not allowed_modules and not allowed_functions:
            raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)
        resolver = SecurePythonReferenceResolver(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
        )
        return cls(resolver=resolver, compute_engine=compute_engine)

    def __init__(
        self,
        resolver: Optional[PythonReferenceResolver] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
        *,
        allow_unsafe_resolver: bool = False,
    ) -> None:
        resolved = resolver
        allow_unsafe = bool(allow_unsafe_resolver)
        if resolved is None:
            if not allow_unsafe:
                raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)
            # 注意:`allow_unsafe_resolver=True` 会关闭 `allowlist` 校验,并回退到“仅黑名单”解析器.
            # 这对不受信任的 `YAML`/配置输入不安全;仅用于测试/演示.
            resolved = SecurePythonReferenceResolver()
        elif not resolved.has_allowlist() and not allow_unsafe:
            raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)

        self._allow_unsafe_resolver: bool = allow_unsafe
        self._resolver: PythonReferenceResolver = resolved
        self._compute_engine: SecureComputeEngine = compute_engine or SecureComputeEngine()
        self._lookup_casts: LookupCastRegistry = LookupCastRegistry()
        self._sources_ir: Dict[str, "SourceIr"] = {}
        self._main_source_ir: Optional[MainSourceIr] = None
        self._relation_steps: Dict[str, List[StepInfo]] = {}
        self._relation_adjacency: Dict[str, List[StepInfo]] = {}
        self._source_field_id_map: Dict[str, Dict[str, str]] = {}
        self._source_data_key_map: Dict[str, Dict[str, List[str]]] = {}

    def convert(self, config: DemandConfig) -> "DemandIr":
        self._sources_ir.clear()
        self._main_source_ir = None
        self._relation_steps = {}
        self._relation_adjacency = {}
        self._source_field_id_map = config.source_field_id_map or {}
        self._source_data_key_map = self._build_source_data_key_map(self._source_field_id_map)

        main_source_ir = self._convert_main_source(config.main_source)
        self._main_source_ir = main_source_ir

        for source_id, source_config in config.sources.items():
            self._sources_ir[source_id] = self._convert_source(source_config)

        if main_source_ir.source_id in self._sources_ir:
            msg = "Main source '{}' conflicts with sources".format(main_source_ir.source_id)
            raise ConversionError(msg)

        self._relation_steps = self._convert_relations(config)
        self._relation_adjacency = self._build_relation_adjacency(self._relation_steps)

        required_field_ids = self._resolve_required_field_ids(config)
        if required_field_ids is not None:
            known_fields = set(config.source_fields.keys()) | set(config.derived_fields.keys())
            missing = required_field_ids - known_fields
            if missing:
                msg = "Output fields reference unknown fields: {}".format(", ".join(sorted(missing)))
                raise ConversionError(msg)

        fields_ir: List[Union["FieldIr", "DerivedFieldIr"]] = []

        for field_id, field_config in config.source_fields.items():
            if required_field_ids is not None and field_id not in required_field_ids:
                continue
            field_ir = self._convert_source_field(field_config, config)
            fields_ir.append(field_ir)

        for field_id, derived_config in config.derived_fields.items():
            if required_field_ids is not None and field_id not in required_field_ids:
                continue
            derived_ir = self._convert_derived_field(derived_config)
            fields_ir.append(derived_ir)

        return DemandIr.from_irs(
            sources=list(self._sources_ir.values()),
            fields=fields_ir,
            main_source=main_source_ir,
            batch_size_hint=config.batch_size,
            name=config.name,
        )

    def _resolve_required_field_ids(self, config: DemandConfig) -> Optional[Set[str]]:
        if config.output is None or not config.output.fields:
            return None

        output_fields = [str(item) for item in config.output.fields]
        required: Set[str] = set(output_fields)
        queue: "deque[str]" = deque(field_id for field_id in output_fields if field_id in config.derived_fields)

        while queue:
            field_id = queue.popleft()
            derived = config.derived_fields.get(field_id)
            if derived is None:
                continue
            for dep in derived.depends_on:
                if dep in required:
                    continue
                required.add(dep)
                if dep in config.derived_fields:
                    queue.append(dep)

        for item in config.main_source.order_by:
            raw = str(item).strip()
            if not raw:
                continue
            field_id = raw[1:] if raw.startswith("-") else raw
            if field_id:
                required.add(field_id)

        return required

    def _convert_main_source(self, config: MainSourceConfig) -> MainSourceIr:
        if not config.source_id:
            msg = "Main source 'source_id' is required"
            raise ConversionError(msg)
        _validate_source_id(config.source_id, "Main source")
        if not config.loader:
            msg = "Main source 'loader' is required"
            raise ConversionError(msg)

        loader_fn = cast("MainSourceRowIterableCallable", self._resolver.resolve(config.loader))
        order_by = self._convert_main_source_order_by(config.order_by)

        return MainSourceIr(
            source_id=config.source_id,
            loader=loader_fn,
            params=dict(config.params or {}),
            order_by=order_by,
        )

    def _convert_main_source_order_by(self, order_by: Tuple[str, ...]) -> Tuple[OrderByKeyIr, ...]:
        if not order_by:
            return ()
        converted: List[OrderByKeyIr] = []
        for item in order_by:
            raw = str(item).strip()
            if not raw or raw == "-":
                msg = "Main source order_by contains invalid field"
                raise ConversionError(msg)
            direction = "desc" if raw.startswith("-") else "asc"
            field_id = raw[1:] if raw.startswith("-") else raw
            converted.append(OrderByKeyIr(field_key=field_id, direction=direction))
        return tuple(converted)

    def _convert_source(self, source_config: SourceConfig) -> "SourceIr":
        _validate_source_id(source_config.source_id, "Source")
        loader_fn = cast("LoaderResultMapCallable", self._resolver.resolve(source_config.loader))

        lookup_cast_fn = None
        if source_config.lookup_cast is not None:
            is_multi = isinstance(source_config.key, tuple)
            lookup_cast_fn = self._get_lookup_cast_fn(source_config.lookup_cast, is_multi=is_multi)

        key_ir = KeyIr(
            key=source_config.key,
            cast=lookup_cast_fn,
        )

        bind_ir = None
        if source_config.bind is not None:
            bind_ir = self._create_binding(source_config.bind, source_config.params, source_config.key)

        loader_ir = LoaderIr(
            callable=loader_fn,
            bindings={},
        )

        cache_mode = SourceSpecIrCacheMode.NONE
        if source_config.cache_mode == "preload_forever":
            cache_mode = SourceSpecIrCacheMode.PRELOAD_FOREVER

        fk_fields: FrozenSet[str] = frozenset()

        return SourceIr(
            source_id=source_config.source_id,
            key=key_ir,
            loader_spec=loader_ir,
            fk_fields=fk_fields,
            cache_mode=cache_mode,
            lookup_chunk_size=source_config.lookup_chunk_size,
            bindings={},
            bind=bind_ir,
        )

    def _convert_relations(self, config: DemandConfig) -> Dict[str, List[StepInfo]]:
        relation_steps: Dict[str, List[StepInfo]] = {}
        for rel_id, rel_config in config.relations.items():
            relation_steps[rel_id] = self._convert_steps(rel_config.steps, config)
        return relation_steps

    def _build_relation_adjacency(self, relation_steps: Dict[str, List[StepInfo]]) -> Dict[str, List[StepInfo]]:
        adjacency: Dict[str, List[StepInfo]] = {}
        for steps in relation_steps.values():
            for step_info in steps:
                from_source_id, _to_source_id, _step_ir = step_info
                adjacency.setdefault(from_source_id, []).append(step_info)
        return adjacency

    def _convert_steps(self, steps: Tuple[RelationStepConfig, ...], config: DemandConfig) -> List[StepInfo]:
        step_infos: List[StepInfo] = []
        for step in steps:
            step_infos.append(self._convert_step(step, config))
        return step_infos

    def _convert_step(self, step: RelationStepConfig, config: DemandConfig) -> StepInfo:
        from_source_id, from_fields = self._parse_step_field(step.from_)
        to_source_id, to_fields = self._parse_step_field(step.to)

        to_source = self._require_source_ir(to_source_id)
        to_field = self._resolve_to_field(to_fields, to_source)
        lookup_cast_fn = self._resolve_step_lookup_cast(step, from_fields)
        bind_ir = self._resolve_step_binding(step, config, to_source_id, to_source.key.key)

        step_ir = LookupStepIr(
            from_field=tuple(from_fields) if len(from_fields) > 1 else from_fields[0],
            to_source=to_source,
            to_field=to_field,
            lookup_cast=lookup_cast_fn,
            bind=bind_ir,
        )

        return from_source_id, to_source_id, step_ir

    def _require_source_ir(self, source_id: str) -> SourceIr:
        source = self._sources_ir.get(source_id)
        if source is None:
            msg = "Step references unknown source '{}'".format(source_id)
            raise ConversionError(msg)
        return source

    def _resolve_to_field(self, to_fields: List[str], to_source: SourceIr) -> Optional[Union[str, Tuple[str, ...]]]:
        if len(to_fields) > 1:
            to_field: Optional[Union[str, Tuple[str, ...]]] = tuple(to_fields)
        else:
            to_field = to_fields[0]

        if to_field == to_source.key.key:
            return None
        return to_field

    def _resolve_step_lookup_cast(self, step: RelationStepConfig, from_fields: List[str]) -> Optional[Callable[[Any], Optional[Hashable]]]:
        if step.lookup_cast is None:
            return None
        is_multi = len(from_fields) > 1
        return self._get_lookup_cast_fn(step.lookup_cast, is_multi=is_multi)

    def _resolve_step_binding(
        self,
        step: RelationStepConfig,
        config: DemandConfig,
        to_source_id: str,
        key_field: Union[str, Tuple[str, ...]],
    ) -> Optional[BindingIr]:
        if step.to_bind is None:
            return None
        return self._create_binding(step.to_bind, config.sources[to_source_id].params, key_field)

    def _convert_source_field(self, field_config: SourceFieldConfig, config: DemandConfig) -> "FieldIr":
        from_source_id = field_config.source
        data_key = field_config.field or field_config.field_id
        if not from_source_id:
            msg = "Field '{}' missing source".format(field_config.field_id)
            raise ConversionError(msg)
        if not data_key:
            msg = "Field '{}' missing field".format(field_config.field_id)
            raise ConversionError(msg)

        source_ir: Optional[Union[SourceIr, MainSourceIr]] = None
        if self._main_source_ir and from_source_id == self._main_source_ir.source_id:
            source_ir = self._main_source_ir
        else:
            source_ir = self._sources_ir.get(from_source_id)
        if source_ir is None:
            msg = "Field '{}' references unknown source '{}'".format(field_config.field_id, from_source_id)
            raise ConversionError(msg)

        transform: Optional[Callable[[Any], Any]] = None
        if field_config.value_cast:
            transform = self._get_value_cast_fn(field_config.value_cast)

        lookup_steps: Optional[Tuple[LookupStepIr, ...]] = None
        if isinstance(source_ir, SourceIr):
            lookup_steps = self._resolve_lookup_steps(field_config, config, source_ir)

        return FieldIr(
            field_id=field_config.field_id,
            name=field_config.name or field_config.field_id,
            source=source_ir,
            data_key=data_key,
            is_primary=False,
            transform=transform,
            relation=None,
            lookup_steps=lookup_steps,
        )

    def _resolve_lookup_steps(
        self, field_config: SourceFieldConfig, config: DemandConfig, target_source: SourceIr
    ) -> Optional[Tuple[LookupStepIr, ...]]:
        if self._main_source_ir is None:
            return None

        if field_config.relation is None:
            if target_source.source_id == self._main_source_ir.source_id:
                return None
            path = self._infer_unique_path(self._main_source_ir.source_id, target_source.source_id)
            return tuple(step for _from_id, _to_id, step in path) if path else None

        if isinstance(field_config.relation, InlineRelationConfig):
            steps = self._convert_steps(field_config.relation.steps, config)
            return tuple(step for _from_id, _to_id, step in steps)

        if field_config.relation is not None:
            msg = "Unsupported relation reference; use inline steps object"
            raise ConversionError(msg)

        return None  # pragma: no cover

    def _infer_unique_path(self, start_id: str, target_id: str) -> Optional[List[StepInfo]]:
        if start_id == target_id:
            return []

        adjacency = self._relation_adjacency
        if not adjacency and self._relation_steps:
            adjacency = self._build_relation_adjacency(self._relation_steps)
            self._relation_adjacency = adjacency

        max_paths = 2
        found_paths: List[List[StepInfo]] = []
        queue: "deque[Tuple[str, List[StepInfo], Set[str]]]" = deque()
        queue.append((start_id, [], {start_id}))

        while queue and len(found_paths) < max_paths:
            current, path, visited = queue.popleft()
            if current == target_id:
                found_paths.append(path)
                continue
            for step_info in adjacency.get(current, []):
                _from_source_id, to_source_id, _step_ir = step_info
                if to_source_id in visited:
                    continue
                next_visited = set(visited)
                next_visited.add(to_source_id)
                queue.append((to_source_id, [*path, step_info], next_visited))

        if len(found_paths) == 1:
            return found_paths[0]

        if not found_paths:
            msg = "No relation path found from '{}' to '{}'".format(start_id, target_id)
            raise ConversionError(msg)

        msg = "Ambiguous relation paths from '{}' to '{}'".format(start_id, target_id)
        raise ConversionError(msg)

    def _convert_derived_field(self, derived_config: DerivedFieldConfig) -> "DerivedFieldIr":
        call_ctx_key = None
        is_constant_compute = False
        if derived_config.compute:
            calculator = self._compute_engine.compile(
                derived_config.compute,
                derived_config.depends_on,
            )
            if not derived_config.depends_on and is_constant_compute_expression(derived_config.compute):
                is_constant_compute = True
        elif derived_config.call_by:
            calculator = self._compile_call_by(
                field_id=derived_config.field_id,
                call_by=derived_config.call_by,
            )
            call_ctx_key = _CALL_BY_CTX_KEY
        else:
            msg = "Derived field '{}' must declare 'compute' or 'call_by'".format(derived_config.field_id)
            raise ConversionError(msg)

        return DerivedFieldIr(
            field_id=derived_config.field_id,
            name=derived_config.name,
            dependencies=derived_config.depends_on,
            calculator=calculator,
            call_ctx_key=call_ctx_key,
            is_constant_compute=is_constant_compute,
        )

    def _compile_call_by(self, *, field_id: str, call_by: str) -> Callable[..., Any]:
        try:
            parsed = parse_call_by(call_by)
        except CallByParseError as exc:
            msg = "Derived field '{}' has invalid call_by: {}".format(field_id, exc)
            raise ConversionError(msg) from exc

        try:
            fn = self._resolver.resolve(parsed.reference)
        except Exception as exc:
            msg = "Derived field '{}' failed to resolve call_by reference '{}': {}".format(field_id, parsed.reference, exc)
            raise ConversionError(msg) from exc

        def _eval_value(value: CallByValue, field_values: Dict[str, Any]) -> Any:
            if value.kind == "literal":
                return value.value
            if value.kind == "field":
                return field_values.get(value.value)
            ctx = field_values.get(_CALL_BY_CTX_KEY)
            if ctx is None:
                msg = "call_by requires context, but '{}' is missing".format(_CALL_BY_CTX_KEY)
                raise ValueError(msg)
            if value.kind == "ctx":
                return ctx
            if value.kind == "ctx_attr":
                return getattr(ctx, value.value)
            msg = "Unknown call_by value kind: {}".format(value.kind)  # pragma: no cover
            raise ValueError(msg)  # pragma: no cover

        def calculator(**field_values: Any) -> Any:
            args = [_eval_value(v, field_values) for v in parsed.args]
            kwargs = {k: _eval_value(v, field_values) for k, v in parsed.kwargs}
            return fn(*args, **kwargs)

        return calculator

    def _parse_source_field_expr(self, expr: str) -> Tuple[str, str]:
        if "." not in expr:
            msg = "Invalid field reference: '{}'".format(expr)
            raise ConversionError(msg)
        source_id, field_name = expr.split(".", 1)
        if not source_id or not field_name:
            msg = "Invalid field reference: '{}'".format(expr)
            raise ConversionError(msg)
        field_name = self._resolve_source_field_name(source_id, field_name)
        return source_id, field_name

    def _parse_step_field(self, value: Union[str, Tuple[str, ...]]) -> Tuple[str, List[str]]:
        if isinstance(value, tuple):
            source_id: Optional[str] = None
            fields: List[str] = []
            items = cast("Iterable[str]", value)
            for item in items:
                src, field_name = self._parse_source_field_expr(item)
                if source_id is None:
                    source_id = src
                elif source_id != src:
                    msg = "Step fields must reference the same source, got '{}' and '{}'".format(source_id, src)
                    raise ConversionError(msg)
                fields.append(field_name)
            if source_id is None:
                msg = "Empty step field list"
                raise ConversionError(msg)
            return source_id, fields

        src, field_name = self._parse_source_field_expr(value)
        return src, [field_name]

    def _build_source_data_key_map(
        self,
        source_field_id_map: Dict[str, Dict[str, str]],
    ) -> Dict[str, Dict[str, List[str]]]:
        data_key_map: Dict[str, Dict[str, List[str]]] = {}
        for source_id, field_map in source_field_id_map.items():
            source_data_keys = data_key_map.setdefault(source_id, {})
            for field_id, data_key in field_map.items():
                source_data_keys.setdefault(data_key, []).append(field_id)
        return data_key_map

    def _resolve_source_field_name(self, source_id: str, field_name: str) -> str:
        field_map = self._source_field_id_map.get(source_id)
        if not field_map:
            return field_name
        if field_name not in field_map:
            return field_name
        mapped = field_map[field_name]
        data_key_map = self._source_data_key_map.get(source_id, {})
        conflicts = data_key_map.get(field_name, [])
        if conflicts:
            unique = set(conflicts)
            if unique != {field_name}:
                msg = (
                    "Relation step field '{}.{}' is ambiguous: field_id '{}' maps to '{}', "
                    "but '{}' is also a data_key for field_id(s): {}. "
                    "Rename one of the fields to disambiguate."
                ).format(
                    source_id,
                    field_name,
                    field_name,
                    mapped,
                    field_name,
                    ", ".join(sorted(unique)),
                )
                raise ConversionError(msg)
        return mapped

    def _create_binding(
        self, bind_config: BindConfig, static_params: Optional[Dict[str, Any]], key_field: Union[str, Tuple[str, ...]]
    ) -> BindingIr:
        if bind_config.use_rows is not None:
            mode = "rows"
            as_mode = DEFAULT_BIND_AS
            cache_mode = bind_config.use_rows.cache_mode or DEFAULT_BIND_CACHE_MODE
            param_name = bind_config.use_rows.param
        elif bind_config.use_keys is not None:
            mode = "keys"
            as_mode = bind_config.use_keys.as_
            cache_mode = "none"
            param_name = bind_config.use_keys.param
        else:
            msg = "BindConfig requires use_rows or use_keys"
            raise ConversionError(msg)
        params_builder = self._create_params_builder(bind_config, static_params)
        return BindingIr(
            key_field=key_field,
            params_builder=params_builder,
            mode=mode,
            as_=as_mode,
            cache_mode=cache_mode or "none",
            param_name=param_name,
        )

    def _create_params_builder(
        self,
        bind_config: BindConfig,
        static_params: Optional[Dict[str, Any]] = None,
    ) -> Callable[["LoaderCallContextIr"], Tuple[Tuple[Any, ...], Dict[str, Any]]]:
        base_params: Dict[str, Any] = dict(static_params) if static_params else {}
        if bind_config.use_rows is not None:
            param_name = bind_config.use_rows.param
            mode = "rows"
            as_mode = DEFAULT_BIND_AS
        elif bind_config.use_keys is not None:
            param_name = bind_config.use_keys.param
            mode = "keys"
            as_mode = bind_config.use_keys.as_
        else:
            msg = "BindConfig requires use_rows or use_keys"
            raise ConversionError(msg)

        def _builder(ctx: LoaderCallContextIr) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
            params: Dict[str, Any] = dict(base_params)
            if mode == "rows":
                # `rows` 模式直接传入 `batch_rows`,不支持 `as`.
                params[param_name] = ctx.batch_rows or []
                return (), params

            keys = ctx.lookup_keys if ctx.lookup_keys is not None else ctx.batch_row_nth
            if as_mode == "list":
                if ctx.lookup_keys_list is not None:
                    params[param_name] = list(ctx.lookup_keys_list)
                elif isinstance(keys, set):
                    params[param_name] = build_stable_lookup_key_list(keys)
                else:
                    params[param_name] = list(keys)
            else:
                params[param_name] = set(keys)
            return (), params

        return _builder

    def _get_value_cast_fn(self, value_cast: str) -> Callable[[Any], Any]:
        fn = _VALUE_CASTS.get(value_cast)
        if fn is None:
            msg = "Unknown value_cast: '{}'".format(value_cast)
            raise ConversionError(msg)
        return fn

    def _get_lookup_cast_fn(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> Callable[[Any], Optional[Hashable]]:
        return self._lookup_casts.build(lookup_cast, is_multi=is_multi)


__all__ = [
    "ConfigToIRConverter",
    "LookupCastRegistry",
]
