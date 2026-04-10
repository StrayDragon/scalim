from typing import Optional

from ...vendor.compact.typing_extensionsx import Protocol, runtime_checkable
from .aliases import LookupKeySpec, NormalizedLookupKeySpec
from .binding import BindingIr, LoaderIr
from .lookup_casts import LookupCastSpecIr


@runtime_checkable
class SourceKeyIrBase(Protocol):
    """供关联模块使用的最小键契约."""

    @property
    def key(self) -> LookupKeySpec: ...

    @property
    def cast(self) -> Optional[LookupCastSpecIr]: ...


@runtime_checkable
class SourceRefIrBase(Protocol):
    """供跨模块共享的最小数据源引用契约."""

    @property
    def source_id(self) -> str: ...


@runtime_checkable
class SourceNormalizeIrBase(Protocol):
    """数据源 `normalize` 契约: 供 `execution` 模块使用的最小接口."""

    def apply(self, result: object, *, source_id: str, call_by: Optional[object] = None) -> object: ...


@runtime_checkable
class LookupSourceRefIrBase(SourceRefIrBase, Protocol):
    """具备键定义、可作为关联查找目标的数据源契约."""

    @property
    def key(self) -> SourceKeyIrBase: ...

    @property
    def loader_spec(self) -> LoaderIr: ...

    @property
    def lookup_chunk_size(self) -> Optional[int]: ...

    @property
    def normalize(self) -> Optional[SourceNormalizeIrBase]: ...

    def get_binding(self, key_field: NormalizedLookupKeySpec) -> Optional[BindingIr]: ...


@runtime_checkable
class MainSourceRefIrBase(SourceRefIrBase, Protocol):
    """主数据源契约: 可作为关联端点,不可作为关联查找目标."""

    @property
    def loader_ref(self) -> object: ...


__all__ = ()
