"""`RuntimeBindings` 运行时绑定契约(DSL 无关).

本模块定义“运行时链接”边界: 静态 `IR`/`ExecutionPlan` 仅包含纯数据,执行阶段需要的可调用对象集中放在 `RuntimeBindings` 中.

硬约束:
- 运行时必须兼容 `Python 3.6`.
- 静态 `IR`/`ExecutionPlan` 不得保存任何 `Python` 可调用对象;统一通过 `RuntimeBindings` 注入.
"""

from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from ..spec.ir.aliases import NormalizedLookupKeySpec
from ..spec.ir.binding import LoaderCallContextIr
from ..typedefs import FieldValue, LoaderCallParams, LoaderResultMapping, LookupKey, RowData, RuntimeValue
from ..vendor.dataclassesx import dataclass, field

MainSourceLoaderFn = Callable[..., Iterable[RowData]]
SourceLoaderFn = Callable[..., object]
ParamsBuilderFn = Callable[[LoaderCallContextIr], LoaderCallParams]
NormalizeCallByFn = Callable[..., object]
DerivedCalculatorFn = Callable[..., FieldValue]
RefDefaultCalculatorFn = Callable[..., FieldValue]
ValueTransformFn = Callable[[FieldValue], FieldValue]
LookupKeyCastFn = Callable[[object], Optional[LookupKey]]


@dataclass
class RuntimeBindings:
    """执行阶段使用的运行时绑定(可调用对象注册表).

    说明:
    - 执行阶段不做 `import`/解析;所有函数对象在运行前通过“运行时链接”阶段解析后放入此处.
    """

    main_source_loaders: Dict[str, MainSourceLoaderFn] = field(default_factory=dict)
    source_loaders: Dict[str, SourceLoaderFn] = field(default_factory=dict)
    params_builders: Dict[Tuple[str, NormalizedLookupKeySpec], ParamsBuilderFn] = field(default_factory=dict)
    source_normalize_call_bys: Dict[str, NormalizeCallByFn] = field(default_factory=dict)
    derived_calculators: Dict[str, DerivedCalculatorFn] = field(default_factory=dict)
    ref_default_calculators: Dict[Tuple[str, int], RefDefaultCalculatorFn] = field(default_factory=dict)
    value_transforms: Dict[str, ValueTransformFn] = field(default_factory=dict)
    lookup_key_casts: Dict[str, LookupKeyCastFn] = field(default_factory=dict)
    loader_extractors: Dict[str, Callable[[LookupKey, LoaderResultMapping], RuntimeValue]] = field(default_factory=dict)

    def require_main_source_loader(self, source_id: str) -> MainSourceLoaderFn:
        fn = self.main_source_loaders.get(str(source_id))
        if fn is None:
            msg = "Missing runtime main source loader for source_id={!r}".format(source_id)
            raise KeyError(msg)
        return fn

    def require_source_loader(self, source_id: str) -> SourceLoaderFn:
        fn = self.source_loaders.get(str(source_id))
        if fn is None:
            msg = "Missing runtime source loader for source_id={!r}".format(source_id)
            raise KeyError(msg)
        return fn

    def get_params_builder(self, source_id: str, key_field: NormalizedLookupKeySpec) -> Optional[ParamsBuilderFn]:
        key = (str(source_id), key_field)
        return self.params_builders.get(key)

    def get_source_normalize_call_by(self, source_id: str) -> Optional[NormalizeCallByFn]:
        return self.source_normalize_call_bys.get(str(source_id))

    def require_derived_calculator(self, field_id: str) -> DerivedCalculatorFn:
        fn = self.derived_calculators.get(str(field_id))
        if fn is None:
            msg = "Missing runtime derived calculator for field_id={!r}".format(field_id)
            raise KeyError(msg)
        return fn

    def get_ref_default_calculator(self, field_id: str, idx: int) -> Optional[RefDefaultCalculatorFn]:
        return self.ref_default_calculators.get((str(field_id), int(idx)))

    def get_value_transform(self, field_id: str) -> Optional[ValueTransformFn]:
        return self.value_transforms.get(str(field_id))

    def get_lookup_key_cast(self, cast_id: str) -> Optional[LookupKeyCastFn]:
        return self.lookup_key_casts.get(str(cast_id))

    def get_loader_extractor(self, source_id: str) -> Optional[Callable[[LookupKey, LoaderResultMapping], RuntimeValue]]:
        return self.loader_extractors.get(str(source_id))

    def debug_summary(self) -> Dict[str, Any]:
        return {
            "main_source_loaders": len(self.main_source_loaders),
            "source_loaders": len(self.source_loaders),
            "params_builders": len(self.params_builders),
            "source_normalize_call_bys": len(self.source_normalize_call_bys),
            "derived_calculators": len(self.derived_calculators),
            "ref_default_calculators": len(self.ref_default_calculators),
            "value_transforms": len(self.value_transforms),
            "lookup_key_casts": len(self.lookup_key_casts),
            "loader_extractors": len(self.loader_extractors),
        }


__all__ = ("RuntimeBindings",)
