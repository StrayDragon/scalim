from ....exceptions import ScalimYamlError


class ScalimResolverError(ScalimYamlError):
    pass


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
    "ScalimConversionError",
    "ScalimResolverError",
)
