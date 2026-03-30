from typing import Any, Type

from . import nodes as nodes
from . import resolver as resolver

__with_libyaml__: bool


class YAMLError(Exception):
    ...


class MarkedYAMLError(YAMLError):
    ...


class Loader:
    @classmethod
    def add_constructor(cls, tag: str, constructor: Any) -> None:
        ...


class SafeLoader(Loader):
    def construct_object(self, node: Any, deep: bool = ...) -> Any:
        ...

    def flatten_mapping(self, node: Any) -> None:
        ...


class Dumper:
    ...


class SafeDumper(Dumper):
    def ignore_aliases(self, data: Any) -> bool:
        ...


def load(stream: Any, Loader: Type[Loader] = ..., **kwds: Any) -> Any:
    ...


def safe_load(stream: Any) -> Any:
    ...


def dump(data: Any, stream: Any = ..., Dumper: Type[Dumper] = ..., **kwds: Any) -> str:
    ...


def safe_dump(data: Any, stream: Any = ..., **kwds: Any) -> str:
    ...


def compose(stream: Any, Loader: Type[Loader] = ..., **kwds: Any) -> Any:
    ...
