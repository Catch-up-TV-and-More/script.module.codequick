# -*- coding: utf-8 -*-
import xbmcaddon
import xbmc
import re
import os


def load_strings(ref_map=None):
    """
    This function loads in all the string id references from the "strings.po" file into a dictionary.
    The dictionary keys are the english strings and the values are the string ids.

    :param dict ref_map: [opt] Dictionary where the strings will be store,
                         if not given it will default to codequick's strings mapping.

    When using codequick you can call plugin.localize("text") to get the localized string.
    If using you're own string map, you can call plugin.getLocalizedString(strmap["text"])
    to get the localized string.
    """
    # Default to codequick string map
    if ref_map is None:
        from codequick.utils import string_map as ref_map

    # Check if path needs to be translated first
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    if addon_path[:10] == "special://":  # pragma: no cover
        addon_path = xbmc.translatePath(addon_path)

    # Location of strings.po file
    strings_po = os.path.join(addon_path, "resources", "language", "resource.language.en_gb", "strings.po")
    strings_po = strings_po.decode("utf8") if isinstance(strings_po, bytes) else strings_po

    # Check if strings.po actrally exists first
    if os.path.exists(strings_po):  # pragma: no branch
        with open(strings_po, "rb") as fo:
            raw_strings = fo.read()

        # Parse strings using Regular Expressions
        res = u"^msgctxt\s+[\"']#(\d+?)[\"']$[\n\r]^msgid\s+[\"'](.+?)[\"']$"
        data = re.findall(res, raw_strings.decode("utf8"), re.MULTILINE | re.UNICODE)
        ref_map.update((key, int(value)) for value, key in data)
