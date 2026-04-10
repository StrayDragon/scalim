from ....exceptions import ScalimYamlError


class ScalimResolverError(ScalimYamlError):
    pass


class ScalimAllowlistViolationError(ScalimResolverError):
    """当 `Python` 引用被白名单策略拒绝时抛出."""


class ScalimConversionError(ScalimYamlError):
    pass


class ScalimAllowlistRequiredError(ScalimYamlError):
    pass


ALLOWLIST_REQUIRED_MSG = (
    "Allowlist is required for secure loading. "
    "Please provide 'allowed_modules' and/or 'allowed_functions' parameter. "
    "Example: allowed_modules=frozenset(['myapp.loaders'])"
)

__all__ = (
    "ALLOWLIST_REQUIRED_MSG",
    "ScalimAllowlistRequiredError",
    "ScalimAllowlistViolationError",
    "ScalimConversionError",
    "ScalimResolverError",
)
