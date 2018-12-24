from addondev import initializer as _initializer
import os as _os

# Initialize mock kodi environment
addon_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "script.module.codequick")
_initializer(addon_path)
