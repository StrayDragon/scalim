from typing import Optional

from ..typedefs import KeyNormalizationMode


def normalize_key_normalization(value: object) -> KeyNormalizationMode:
    if value is None:
        return "raw"
    raw = str(value).strip()
    if raw in ("raw", "auto_str", "force_str"):
        return raw  # type: ignore[return-value]
    msg = "Invalid key_normalization={!r}. Expected 'raw', 'auto_str', or 'force_str'.".format(value)
    raise ValueError(msg)


def should_apply_str_key_normalization(
    mode: KeyNormalizationMode,
    *,
    has_explicit_cast: bool,
) -> bool:
    if mode == "raw":
        return False
    if mode == "auto_str":
        return not bool(has_explicit_cast)
    return True


def is_experimental_key_normalization(mode: Optional[object]) -> bool:
    try:
        resolved = normalize_key_normalization(mode)
    except ValueError:
        return False
    return resolved != "raw"


__all__ = [
    "is_experimental_key_normalization",
    "normalize_key_normalization",
    "should_apply_str_key_normalization",
]
