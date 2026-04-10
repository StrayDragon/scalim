"""Fixtures for deterministic public API notebooks.

This package intentionally contains only fixtures/small helpers.
The public API teaching logic lives in `notebooks/marimo/`.
"""

from __future__ import annotations

from ._fixtures import (
    build_minimal_public_api_ir,
    build_minimal_public_api_runtime_bindings,
    get_preload_counter_calls,
    load_dims,
    load_items,
    reset_preload_counter_calls,
)

__all__ = [
    "build_minimal_public_api_ir",
    "build_minimal_public_api_runtime_bindings",
    "get_preload_counter_calls",
    "load_dims",
    "load_items",
    "reset_preload_counter_calls",
]
