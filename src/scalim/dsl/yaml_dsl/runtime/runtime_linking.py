from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from ....execution.runtime_bindings import (
    DerivedCalculatorFn,
    MainSourceLoaderFn,
    RefDefaultCalculatorFn,
    RuntimeBindings,
    ValueTransformFn,
)
from ....spec.ir import (
    CallBySpecIr,
    CallByValueIr,
    ComputeCallContextIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
)
from ....spec.ir._fields import call_by_requires_ctx
from ....spec.ir.callable_refs import BuiltinCallableIdIr, CallableRefIr, PythonReferenceIr, RuntimeHandleIdIr, describe_callable_ref
from ....spec.ir.lookup_casts import LookupCastSpecIr, lookup_cast_id
from ....typedefs import FieldValue, LoaderResultMapping, LookupKey
from .._internal.config_parsing.security import SecureComputeEngine, build_compute_engine
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from ._internal.callable_preflight import (
    ScalimCallablePreflightError,
    validate_signature_accepts_any_candidate,
    validate_signature_binds_kwargs_keys,
)
from ._internal.conversion_lookup import VALUE_CASTS, LookupCastRegistry
from .errors import ScalimResolverError
from .references import SecurePythonReferenceResolver

_SUPPORTED_FIELD_VALUE_TYPES = (bool, int, float, Decimal, str)


def _ensure_field_value(value: object, *, field_id: str, producer: str) -> FieldValue:
    if value is None or isinstance(value, _SUPPORTED_FIELD_VALUE_TYPES):
        return value
    msg = "Derived field '{}' {} has unsupported value type '{}'; expected int/float/Decimal/str/bool/None".format(
        field_id,
        producer,
        type(value).__name__,
    )
    raise TypeError(msg)


_SignatureCandidate = Tuple[str, Tuple[object, ...], Dict[str, object]]


def _resolve_callable_ref(ref: CallableRefIr, *, resolver: SecurePythonReferenceResolver) -> Callable[..., Any]:
    if isinstance(ref, RuntimeHandleIdIr):
        msg = "Runtime handle references are not supported in YAML runtime linking: {}".format(ref.handle_id)
        raise ScalimResolverError(msg)
    reference = describe_callable_ref(ref)
    if isinstance(ref, BuiltinCallableIdIr):
        reference = "{}{}".format(BUILTIN_CALLABLE_REFERENCE_PREFIX, ref.callable_id)
    if isinstance(ref, PythonReferenceIr):
        reference = str(ref.reference)
    return resolver.resolve(reference)


def _eval_call_by_value(  # pyright: ignore[reportUnusedFunction]  # used by internal tests
    value: CallByValueIr,
    *,
    field_id: str,
    dep_values: Dict[str, object],
    ctx: ComputeCallContextIr,
) -> object:
    kind = str(value.kind or "").strip()
    raw = value.value
    if kind == "literal":
        return raw
    if kind == "field":
        return dep_values.get(str(raw))
    if kind == "ctx":
        return ctx
    if kind == "ctx_attr":
        return getattr(ctx, str(raw))  # pragma: allow-dynattr dsl: ctx_attr access
    msg = "Derived field '{}' has unknown call_by value kind: {!r}".format(field_id, kind)
    raise ValueError(msg)


def _preflight_call_by_signature(
    *,
    field_id: str,
    call_by: CallBySpecIr,
    fn: Callable[..., Any],
) -> None:
    placeholder = object()
    args = tuple(placeholder for _ in (call_by.args or ()))
    kwargs = {str(k): placeholder for k, _v in (call_by.kwargs or ())}
    display = "{}({})".format(
        describe_callable_ref(call_by.reference),
        ", ".join(["..."] * len(args) + ["{}=...".format(k) for k in sorted(kwargs.keys())]),
    )
    candidates = ((display, args, kwargs),)
    validate_signature_accepts_any_candidate(
        location="derived_fields.{}.call_by".format(field_id),
        reference=describe_callable_ref(call_by.reference),
        fn=fn,
        candidates=candidates,
        hint=None,
        extra=None,
    )


def _preflight_ref_default_call_by_signature(
    *,
    field_id: str,
    idx: int,
    call_by: CallBySpecIr,
    fn: Callable[..., Any],
) -> None:
    placeholder = object()
    args = tuple(placeholder for _ in (call_by.args or ()))
    kwargs = {str(k): placeholder for k, _v in (call_by.kwargs or ())}
    display = "{}({})".format(
        describe_callable_ref(call_by.reference),
        ", ".join(["..."] * len(args) + ["{}=...".format(k) for k in sorted(kwargs.keys())]),
    )
    candidates = ((display, args, kwargs),)
    validate_signature_accepts_any_candidate(
        location="fields.{}.default[{}].call_by".format(field_id, int(idx)),
        reference=describe_callable_ref(call_by.reference),
        fn=fn,
        candidates=candidates,
        hint=None,
        extra=None,
    )


def _preflight_normalize_call_by_signature(
    *,
    source_id: str,
    reference: str,
    fn: Callable[..., Any],
) -> None:
    placeholder_result = object()
    placeholder_ctx = object()
    empty_kwargs: Dict[str, object] = {}
    candidates: Tuple[_SignatureCandidate, _SignatureCandidate, _SignatureCandidate] = (
        ("normalize.call_by(result)", (placeholder_result,), empty_kwargs),
        ("normalize.call_by(result, ctx)", (placeholder_result, placeholder_ctx), empty_kwargs),
        ("normalize.call_by(result, ctx=ctx)", (placeholder_result,), {"ctx": placeholder_ctx}),
    )
    validate_signature_accepts_any_candidate(
        location="sources.{}.normalize.call_by".format(source_id),
        reference=str(reference),
        fn=fn,
        candidates=candidates,
        hint="normalize.call_by must accept at least 1 positional argument: (result) or (result, ctx) (when signature is introspectable)",
        extra=None,
    )


def _preflight_loader_params_signature(
    *,
    location: str,
    reference: str,
    fn: Callable[..., Any],
    params_template: object,
) -> None:
    """对 YAML `params` 模板的顶层 `kwargs` 键做签名预检查(不渲染模板)."""

    keys_fn = getattr(  # pragma: allow-dynattr optional-interface: params_template keys contract
        params_template,
        "top_level_mapping_string_keys",
        None,
    )
    if not callable(keys_fn):
        return
    keys = cast("Tuple[str, ...]", keys_fn())  # type: ignore[misc]  # pragma: allow-any template boundary  # pragma: allow-cast template keys contract boundary
    validate_signature_binds_kwargs_keys(
        location=str(location),
        reference=str(reference),
        fn=fn,
        kwargs_keys=keys,
        hint=None,
        extra=None,
    )


def _build_call_by_calculator(  # noqa: C901  # pragma: allow-c901 plan: c0
    *,
    field_spec: DerivedFieldIr,
    call_by: CallBySpecIr,
    fn: Callable[..., Any],
) -> DerivedCalculatorFn:
    field_id = str(field_spec.field_id)
    deps = tuple(str(x) for x in (field_spec.dependencies or ()))
    dep_index = {str(dep): int(idx) for idx, dep in enumerate(deps)}
    needs_ctx = call_by_requires_ctx(call_by)

    def _compile_value(value: CallByValueIr) -> Tuple[str, object]:
        kind = str(value.kind or "").strip()
        raw = value.value
        if kind == "literal":
            return "literal", raw
        if kind == "field":
            return "field", dep_index.get(str(raw))
        if kind == "ctx":
            return "ctx", ""
        if kind == "ctx_attr":
            return "ctx_attr", str(raw)
        msg = "Derived field '{}' has unknown call_by value kind: {!r}".format(field_id, kind)
        raise ValueError(msg)

    args_spec = tuple(_compile_value(item) for item in (call_by.args or ()))
    kwargs_spec = tuple((str(key), _compile_value(item)) for key, item in (call_by.kwargs or ()))

    def _resolve_value_no_ctx(spec: Tuple[str, object], dep_args: Tuple[object, ...]) -> object:
        kind, raw = spec
        if kind == "field":
            return dep_args[raw] if isinstance(raw, int) else None
        return raw

    def _resolve_value_with_ctx(spec: Tuple[str, object], dep_args: Tuple[object, ...], ctx_obj: ComputeCallContextIr) -> object:
        kind, raw = spec
        if kind == "field":
            return dep_args[raw] if isinstance(raw, int) else None
        if kind == "ctx":
            return ctx_obj
        if kind == "ctx_attr":
            return getattr(ctx_obj, str(raw))  # pragma: allow-dynattr dsl: ctx_attr access
        return raw

    def _calculator(*dep_args: object, **_kwargs: object) -> FieldValue:
        if needs_ctx:
            candidate = _kwargs.get("ctx")
            if not isinstance(candidate, ComputeCallContextIr):
                msg = "Derived field '{}' call_by requires ctx=ComputeCallContextIr".format(field_id)
                raise TypeError(msg)
            ctx_obj = candidate

            args: List[object] = []
            for item in args_spec:
                args.append(_resolve_value_with_ctx(item, dep_args, ctx_obj))

            if kwargs_spec:
                kwargs: Dict[str, object] = {}
                for key, item in kwargs_spec:
                    kwargs[str(key)] = _resolve_value_with_ctx(item, dep_args, ctx_obj)
                returned = fn(*args, **kwargs)
            else:
                returned = fn(*args)
            return _ensure_field_value(returned, field_id=field_id, producer="call_by")

        args = []
        for item in args_spec:
            args.append(_resolve_value_no_ctx(item, dep_args))

        if kwargs_spec:
            kwargs = {}
            for key, item in kwargs_spec:
                kwargs[str(key)] = _resolve_value_no_ctx(item, dep_args)
            returned = fn(*args, **kwargs)
        else:
            returned = fn(*args)
        return _ensure_field_value(returned, field_id=field_id, producer="call_by")

    return _calculator


def _build_ref_default_call_by_calculator(  # noqa: C901  # pragma: allow-c901 plan: c0
    *,
    field_id: str,
    idx: int,
    dep_keys: Sequence[str],
    call_by: CallBySpecIr,
    fn: Callable[..., Any],
) -> RefDefaultCalculatorFn:
    deps = tuple(str(x) for x in (dep_keys or ()))
    dep_index = {str(dep): int(i) for i, dep in enumerate(deps)}
    needs_ctx = call_by_requires_ctx(call_by)

    def _compile_value(value: CallByValueIr) -> Tuple[str, object]:
        kind = str(value.kind or "").strip()
        raw = value.value
        if kind == "literal":
            return "literal", raw
        if kind == "field":
            return "field", dep_index.get(str(raw))
        if kind == "ctx":
            return "ctx", ""
        if kind == "ctx_attr":
            return "ctx_attr", str(raw)
        msg = "Field '{}' default[{}].call_by has unknown call_by value kind: {!r}".format(field_id, int(idx), kind)
        raise ValueError(msg)

    args_spec = tuple(_compile_value(item) for item in (call_by.args or ()))
    kwargs_spec = tuple((str(key), _compile_value(item)) for key, item in (call_by.kwargs or ()))

    def _resolve_value_no_ctx(spec: Tuple[str, object], dep_args: Tuple[object, ...]) -> object:
        kind, raw = spec
        if kind == "field":
            return dep_args[raw] if isinstance(raw, int) else None
        return raw

    def _resolve_value_with_ctx(spec: Tuple[str, object], dep_args: Tuple[object, ...], ctx_obj: ComputeCallContextIr) -> object:
        kind, raw = spec
        if kind == "field":
            return dep_args[raw] if isinstance(raw, int) else None
        if kind == "ctx":
            return ctx_obj
        if kind == "ctx_attr":
            return getattr(ctx_obj, str(raw))  # pragma: allow-dynattr dsl: ctx_attr access
        return raw

    def _calculator(*dep_args: object, **_kwargs: object) -> FieldValue:
        if needs_ctx:
            candidate = _kwargs.get("ctx")
            if not isinstance(candidate, ComputeCallContextIr):
                msg = "Field '{}' default[{}].call_by requires ctx=ComputeCallContextIr".format(field_id, int(idx))
                raise TypeError(msg)
            ctx_obj = candidate

            args: List[object] = []
            for item in args_spec:
                args.append(_resolve_value_with_ctx(item, dep_args, ctx_obj))

            if kwargs_spec:
                kwargs: Dict[str, object] = {}
                for key, item in kwargs_spec:
                    kwargs[str(key)] = _resolve_value_with_ctx(item, dep_args, ctx_obj)
                returned = fn(*args, **kwargs)
            else:
                returned = fn(*args)
            return _ensure_field_value(returned, field_id=field_id, producer="default.call_by")

        args = []
        for item in args_spec:
            args.append(_resolve_value_no_ctx(item, dep_args))

        if kwargs_spec:
            kwargs = {}
            for key, item in kwargs_spec:
                kwargs[str(key)] = _resolve_value_no_ctx(item, dep_args)
            returned = fn(*args, **kwargs)
        else:
            returned = fn(*args)
        return _ensure_field_value(returned, field_id=field_id, producer="default.call_by")

    return _calculator


def _resolve_value_op_callable(
    *,
    field_id: str,
    kind: str,
    op: object,
    resolver: SecurePythonReferenceResolver,
) -> Callable[..., Any]:
    ref = getattr(op, "callable_ref", None)  # pragma: allow-dynattr dsl: ValueOpIr contract
    if ref is None:
        msg = "ValueOpIr(kind={!r}) requires callable_ref (field={!r})".format(kind, field_id)
        raise ValueError(msg)

    if not isinstance(ref, (BuiltinCallableIdIr, PythonReferenceIr, RuntimeHandleIdIr)):
        msg = "ValueOpIr(kind={!r}) has invalid callable_ref for field {!r}".format(kind, field_id)
        raise TypeError(msg)

    fn = _resolve_callable_ref(ref, resolver=resolver)
    validate_signature_accepts_any_candidate(
        location="fields.{}.value_ops".format(field_id),
        reference=describe_callable_ref(ref),
        fn=fn,
        candidates=(("fn(value)", (object(),), {}),),
        hint="value op callable must accept a single positional argument: (value)",
        extra=None,
    )
    return fn


def _compose_value_ops(
    *,
    field_id: str,
    ops: Tuple[object, ...],
    resolver: SecurePythonReferenceResolver,
) -> Optional[ValueTransformFn]:
    if not ops:
        return None

    steps: List[ValueTransformFn] = []
    for op in ops:
        kind = str(getattr(op, "kind", "") or "").strip()  # pragma: allow-dynattr dsl: ValueOpIr contract
        if kind == "cast":
            to = str(getattr(op, "to", "") or "").strip()  # pragma: allow-dynattr dsl: ValueOpIr contract
            cast_fn = VALUE_CASTS.get(to)
            if cast_fn is None:
                msg = "Unknown value_cast {!r} for field {!r}".format(to, field_id)
                raise ValueError(msg)
            steps.append(cast_fn)
            continue

        if kind in ("transform", "format"):
            fn = _resolve_value_op_callable(field_id=field_id, kind=kind, op=op, resolver=resolver)

            def _apply(value: FieldValue, _fn: Callable[..., Any] = fn, _producer: str = kind) -> FieldValue:
                returned = _fn(value)
                return _ensure_field_value(returned, field_id=field_id, producer=_producer)

            steps.append(_apply)
            continue

        msg = "Unknown ValueOpIr.kind={!r} for field {!r}".format(kind, field_id)
        raise ValueError(msg)

    def _transform(value: FieldValue) -> FieldValue:
        v: FieldValue = value
        for fn in steps:
            v = fn(v)
        return v

    return _transform


def _collect_lookup_cast_specs(demand_ir: DemandIr) -> List[Tuple[str, LookupCastSpecIr, bool]]:
    specs: List[Tuple[str, LookupCastSpecIr, bool]] = []

    for source in demand_ir.sources.values():
        cast_spec = source.key.cast
        if cast_spec is not None:
            is_multi = isinstance(source.key.key, tuple)
            specs.append((lookup_cast_id(cast_spec, is_multi=is_multi), cast_spec, is_multi))

    for field_spec in demand_ir.fields.values():
        if not isinstance(field_spec, FieldIr):
            continue
        steps = field_spec.lookup_steps or ()
        for step in steps:
            if step.lookup_cast is None:
                continue
            specs.append((lookup_cast_id(step.lookup_cast, is_multi=step.is_multi_field()), step.lookup_cast, step.is_multi_field()))

    return specs


def _bind_main_source_runtime_bindings(
    demand_ir: DemandIr,
    *,
    bindings: RuntimeBindings,
    resolver: SecurePythonReferenceResolver,
) -> None:
    main_source = demand_ir.main_source
    main_loader_fn: MainSourceLoaderFn = _resolve_callable_ref(main_source.loader_ref, resolver=resolver)
    bindings.main_source_loaders[str(main_source.source_id)] = main_loader_fn

    main_params = dict(main_source.params or {})
    if not main_params:
        return

    try:
        validate_signature_binds_kwargs_keys(
            location="main_source.params",
            reference=describe_callable_ref(main_source.loader_ref),
            fn=main_loader_fn,
            kwargs_keys=main_params.keys(),
            hint=None,
            extra=None,
        )
    except ScalimCallablePreflightError as exc:
        raise ScalimResolverError(str(exc)) from exc


def _bind_source_runtime_bindings(
    demand_ir: DemandIr,
    *,
    bindings: RuntimeBindings,
    resolver: SecurePythonReferenceResolver,
) -> None:
    for source_id, source in demand_ir.sources.items():
        loader_ref = source.loader_spec.callable_ref
        loader_fn = _resolve_callable_ref(loader_ref, resolver=resolver)
        bindings.source_loaders[str(source_id)] = loader_fn

        # `sources.*.params`(`YAML` `DSL`) 的顶层 `kwargs` 键需与 `loader` 签名匹配,否则必须 `fail-fast`.
        source_bind = source.bind
        if source_bind is not None:
            template = source_bind.params_template
            template_path = str(source_bind.template_path or "")
            if template is not None:
                try:
                    _preflight_loader_params_signature(
                        location=template_path or "sources.{}.params".format(str(source_id)),
                        reference=describe_callable_ref(loader_ref),
                        fn=loader_fn,
                        params_template=template,
                    )
                except ScalimCallablePreflightError as exc:
                    raise ScalimResolverError(str(exc)) from exc

        if source.loader_spec.extractor_ref is not None:
            extractor_fn = _resolve_callable_ref(source.loader_spec.extractor_ref, resolver=resolver)

            def _extract(lookup_key: LookupKey, result: LoaderResultMapping, _fn: Callable[..., Any] = extractor_fn) -> object:
                return _fn(lookup_key, result)

            bindings.loader_extractors[str(source_id)] = _extract

        if source.normalize is not None and source.normalize.call_by_ref is not None:
            fn = _resolve_callable_ref(source.normalize.call_by_ref, resolver=resolver)
            try:
                _preflight_normalize_call_by_signature(
                    source_id=str(source_id),
                    reference=describe_callable_ref(source.normalize.call_by_ref),
                    fn=fn,
                )
            except ScalimCallablePreflightError as exc:
                raise ScalimResolverError(str(exc)) from exc
            bindings.source_normalize_call_bys[str(source_id)] = fn


def _bind_field_runtime_bindings(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c0
    demand_ir: DemandIr,
    *,
    bindings: RuntimeBindings,
    resolver: SecurePythonReferenceResolver,
    compute_engine: SecureComputeEngine,
) -> None:
    for field_id, field_spec in demand_ir.fields.items():
        fid = str(field_id)
        if isinstance(field_spec, DerivedFieldIr):
            if field_spec.compute_expr:
                raw_calculator = compute_engine.compile(field_spec.compute_expr, tuple(field_spec.dependencies or ()))

                def _calculator(
                    *args: Any,
                    _raw_calculator: Callable[..., Any] = raw_calculator,
                    _field_id: str = fid,
                    **kwargs: Any,
                ) -> FieldValue:
                    returned = _raw_calculator(*args, **kwargs)
                    return _ensure_field_value(returned, field_id=_field_id, producer="compute")

                bindings.derived_calculators[fid] = _calculator
            elif field_spec.call_by is not None:
                fn = _resolve_callable_ref(field_spec.call_by.reference, resolver=resolver)
                try:
                    _preflight_call_by_signature(field_id=fid, call_by=field_spec.call_by, fn=fn)
                except ScalimCallablePreflightError as exc:
                    raise ScalimResolverError(str(exc)) from exc
                bindings.derived_calculators[fid] = _build_call_by_calculator(field_spec=field_spec, call_by=field_spec.call_by, fn=fn)
            else:
                msg = "Derived field {!r} missing compute_expr/call_by".format(fid)
                raise ValueError(msg)

        if isinstance(field_spec, FieldIr):
            for idx, case in enumerate(field_spec.default_cases or ()):
                kind = str(getattr(case, "kind", "") or "").strip()  # pragma: allow-dynattr dsl: FieldDefaultCaseIr contract
                if kind != "call_by":
                    continue
                call_by = getattr(case, "call_by", None)  # pragma: allow-dynattr dsl: FieldDefaultCaseIr contract
                if not isinstance(call_by, CallBySpecIr):
                    continue

                ref = call_by.reference
                if isinstance(ref, BuiltinCallableIdIr) and str(ref.callable_id) in (
                    "defaults/default_of_value_cast",
                    "defaults/default",
                ):
                    # 在运行期 `runtime linking` 中内联内置策略: 其语义依赖当前字段的 `value_cast`.
                    # 该策略刻意不作为普通的 `callable` 暴露,因此绑定必须按字段(`per-field`)生成.
                    cast_to = None
                    for op in tuple(field_spec.value_ops or ()):
                        op_kind = str(getattr(op, "kind", "") or "").strip()  # pragma: allow-dynattr dsl: ValueOpIr contract
                        if op_kind == "cast":
                            cast_to = str(getattr(op, "to", "") or "").strip()  # pragma: allow-dynattr dsl: ValueOpIr contract
                            break
                    if cast_to is None:
                        msg = "Field '{}' default builtin '^{}()' requires explicit value_cast".format(fid, str(ref.callable_id))
                        raise ScalimResolverError(msg)

                    zero: FieldValue = None
                    if cast_to in ("int", "decimal"):
                        zero = 0
                    elif cast_to in ("str", "auto"):
                        zero = ""
                    else:
                        msg = "Field '{}' has unsupported value_cast={!r} for '^{}()'".format(fid, cast_to, str(ref.callable_id))
                        raise ScalimResolverError(msg)

                    def _zero_calc(*_dep_args: object, _zero: FieldValue = zero, **_kwargs: object) -> FieldValue:
                        return _zero

                    bindings.ref_default_calculators[(fid, int(idx))] = _zero_calc
                    continue

                fn = _resolve_callable_ref(call_by.reference, resolver=resolver)
                try:
                    _preflight_ref_default_call_by_signature(field_id=fid, idx=int(idx), call_by=call_by, fn=fn)
                except ScalimCallablePreflightError as exc:
                    raise ScalimResolverError(str(exc)) from exc

                bindings.ref_default_calculators[(fid, int(idx))] = _build_ref_default_call_by_calculator(
                    field_id=fid,
                    idx=int(idx),
                    dep_keys=tuple(call_by.field_names or ()),
                    call_by=call_by,
                    fn=fn,
                )

        value_ops = field_spec.value_ops if isinstance(field_spec, (FieldIr, DerivedFieldIr)) else ()
        transform = _compose_value_ops(field_id=fid, ops=tuple(value_ops or ()), resolver=resolver)
        if transform is not None:
            bindings.value_transforms[fid] = transform


def _bind_lookup_cast_runtime_bindings(
    demand_ir: DemandIr,
    *,
    bindings: RuntimeBindings,
) -> None:
    registry = LookupCastRegistry()
    for cast_key, cast_spec, is_multi in _collect_lookup_cast_specs(demand_ir):
        if cast_key in bindings.lookup_key_casts:
            continue
        bindings.lookup_key_casts[cast_key] = registry.build(cast_spec, is_multi=bool(is_multi))


def resolve_runtime_bindings(
    demand_ir: DemandIr,
    *,
    resolver: SecurePythonReferenceResolver,
    compute_engine: Optional[SecureComputeEngine] = None,
) -> RuntimeBindings:
    """从静态 IR 解析运行时绑定.

    说明:
    - 这是唯一允许执行 `import`/解析 `PythonReferenceIr` 的阶段.
    - 执行阶段只消费返回的 `RuntimeBindings`,不再做任何导入/解析.
    """

    engine = compute_engine or build_compute_engine()
    bindings = RuntimeBindings()

    _bind_main_source_runtime_bindings(demand_ir, bindings=bindings, resolver=resolver)
    _bind_source_runtime_bindings(demand_ir, bindings=bindings, resolver=resolver)
    _bind_field_runtime_bindings(demand_ir, bindings=bindings, resolver=resolver, compute_engine=engine)
    _bind_lookup_cast_runtime_bindings(demand_ir, bindings=bindings)

    return bindings


__all__ = ("resolve_runtime_bindings",)
