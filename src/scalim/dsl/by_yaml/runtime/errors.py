from ....exceptions import ScalimYamlException


class ResolverError(ScalimYamlException):
    pass


class ConversionError(ScalimYamlException):
    pass


class AllowlistRequiredError(ScalimYamlException):
    pass


ALLOWLIST_REQUIRED_MSG = (
    "Allowlist is required for secure loading. "
    "Please provide 'allowed_modules' and/or 'allowed_functions' parameter. "
    "Example: allowed_modules=frozenset(['myapp.loaders'])"
)

__all__ = [
    "ALLOWLIST_REQUIRED_MSG",
    "AllowlistRequiredError",
    "ConversionError",
    "ResolverError",
]
