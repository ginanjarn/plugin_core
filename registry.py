"""Plugin settings registry"""

from .safe_dict import SafeDict


class Registry(SafeDict):
    """Settings registry"""


REGISTRY = Registry()
"""Global settings registry"""

# ------------------------------------------------------
# Temporary assignvalue from constant
# ------------------------------------------------------
from .. import constant

REGISTRY.update(
    {
        "package_name": constant.PACKAGE_NAME,
        "logging_channel": constant.LOGGING_CHANNEL,
        "command_prefix": constant.COMMAND_PREFIX,
        "settings_basename": constant.SETTINGS_BASENAME,
        "view_selector": constant.VIEW_SELECTOR,
    }
)
# ------------------------------------------------------

# Reserved settings
PACKAGE_NAME = REGISTRY["package_name"]
LOGGING_CHANNEL = REGISTRY["logging_channel"]
COMMAND_PREFIX = REGISTRY["command_prefix"]
SETTINGS_BASENAME = REGISTRY["settings_basename"]
VIEW_SELECTOR = REGISTRY["view_selector"]
