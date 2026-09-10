"""Single package version; the user-facing product tag is derived from it."""

__version__ = "4.7.2.7"
ENGINE_VERSION = ".".join(__version__.split(".")[:3])
PRODUCT_VERSION = f"v{ENGINE_VERSION}_{__version__.split('.')[-1]}"
PROTOCOL_VERSION = "2026-07-28"
