from ....vendor.compact import StrEnum


class ResolverTrustedMode(StrEnum):
    STRICT_ALLOWLIST = "strict_allowlist"
    TRUSTED_ALLOW_ALL_MODULES = "trusted_allow_all_modules"


__all__ = [
    "ResolverTrustedMode",
]
