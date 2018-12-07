# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Standard Library Imports
from collections import defaultdict
import logging
import inspect
import re

# Kodi imports
import xbmcplugin

# Package imports
import codequick.support as support
from codequick.utils import ensure_native_str

__all__ = ["Route", "validate_listitems"]
_UNSET = object()

# Logger specific to this module
logger = logging.getLogger("%s.route" % support.logger_id)

# Localized string Constants
SELECT_PLAYBACK_ITEM = 25006
NO_DATA = 33077


def validate_listitems(raw_listitems):
    """Check if listitems are valid."""

    # Convert a generator of listitem into a list of listitems
    if inspect.isgenerator(raw_listitems):
        raw_listitems = list(raw_listitems)

    # Silently ignore False values
    elif raw_listitems is False:
        return False

    if raw_listitems:
        # Check that we have valid listitems
        if isinstance(raw_listitems, (list, tuple)):
            # Check for an explicite False return value
            return False if len(raw_listitems) == 1 and raw_listitems[0] is False else raw_listitems
        else:
            raise ValueError("Unexpected return object: {}:{}".format(type(raw_listitems), raw_listitems))
    else:
        raise RuntimeError("No items found")


def guess_content_type(mediatypes):  # type: (defaultdict) -> str
    """Guess the content type based on the mediatype set on the listitems."""
    # See if we can guess the content_type based on the mediatypes from the listitem
    if len(mediatypes) > 1:
        from operator import itemgetter
        # Sort mediatypes by there count, and return the highest count mediatype
        mediatype = sorted(mediatypes.items(), key=itemgetter(1))[-1][0]
    else:
        mediatype = mediatypes.popitem()[0]

    # Convert mediatype to a content_type, not all mediatypes can be converted directly
    if mediatype in ("video", "movie", "tvshow", "episode", "musicvideo", "song", "album", "artist"):
        return mediatype + "s"


def build_sortmethods(manualsort, autosort):  # type: (list, list) -> list
    """Merge manual & auto sortmethod together."""
    if autosort:
        # Add unsorted sort method if not sorted by date and no manually set sortmethods are given
        if not (manualsort or xbmcplugin.SORT_METHOD_DATE in autosort):
            manualsort.append(xbmcplugin.SORT_METHOD_UNSORTED)

        # Keep the order of the manually set sort methods
        # Only sort the auto sort methods
        for method in sorted(autosort):
            if method not in manualsort:
                manualsort.append(method)

    # If no sortmethods are given then set sort mehtod to unsorted
    return manualsort if manualsort else [xbmcplugin.SORT_METHOD_UNSORTED]


def send_to_kodi(handle, session_data):  # type: (int, dict) -> None
    """Send the session data to kodi."""
    # Guess the contenty type
    if session_data["content_type"] == -1:
        kodi_listitems = []
        folder_counter = 0.0
        mediatypes = defaultdict(int)
        for custom_listitem in session_data["listitems"]:
            # Build the kodi listitem
            listitem_tuple = custom_listitem._close()
            kodi_listitems.append(listitem_tuple)

            # Track the mediatypes used
            if "mediatype" in custom_listitem.info:
                mediatypes[custom_listitem.info["mediatype"]] += 1

            # Track if listitem is a folder
            if listitem_tuple[2]:
                folder_counter += 1

        if mediatypes:
            # Guess content type based on set mediatypes
            session_data["content_type"] = guess_content_type(mediatypes)
        else:
            # Set content type based on type of content been listed
            isfolder = folder_counter > (len(kodi_listitems) / 2)
            session_data["content_type"] = "files" if isfolder else "videos"
    else:
        # Just build the kodi listitem without tracking anything
        kodi_listitems = [custom_listitem._close() for custom_listitem in session_data["listitems"]]

    # Add the sortmethods
    addsort = xbmcplugin.addSortMethod
    for sort_method in session_data["sortmethods"]:
        addsort(handle, sort_method)

    # Set category if we have one
    if session_data["category"]:
        xbmcplugin.setPluginCategory(handle, session_data["category"])

    xbmcplugin.setContent(handle, session_data["content_type"])
    success = xbmcplugin.addDirectoryItems(handle, kodi_listitems, len(kodi_listitems))
    xbmcplugin.endOfDirectory(handle, success, session_data["update_listing"], session_data["cache_to_disc"])


class Route(support.Base):
    """
    This class is used to create "Route" callbacks. “Route" callbacks, are callbacks that
    return "listitems" which will show up as folders in Kodi.

    Route inherits all methods and attributes from :class:`codequick.Script<codequick.script.Script>`.

    The possible return types from Route Callbacks are.
        * ``iterable``: "List" or "tuple", consisting of :class:`codequick.listitem<codequick.listing.Listitem>` objects.
        * ``generator``: A Python "generator" that return's :class:`codequick.listitem<codequick.listing.Listitem>` objects.
        * ``False``: This will cause the "plugin call" to quit silently, without raising a RuntimeError.

    :raises RuntimeError: If no content was returned from callback.

    :example:
        >>> from codequick import Route, Listitem
        >>>
        >>> @Route.register
        >>> def root(_):
        >>>     yield Listitem.from_dict("Extra videos", subfolder)
        >>>     yield Listitem.from_dict("Play video",
        >>>           "http://www.example.com/video1.mkv")
        >>>
        >>> @Route.register
        >>> def subfolder(_):
        >>>     yield Listitem.from_dict("Play extra video",
        >>>           "http://www.example.com/video2.mkv")
    """

    # Change listitem type to 'folder'
    is_folder = True

    def __init__(self, callback, callback_params):  # type: (support.Callback, dict) -> None
        super(Route, self).__init__()
        self.update_listing = self.params.get(u"_updatelisting_", False)
        self.category = re.sub(u"\(\d+\)$", u"", self._title).strip()
        self.cache_to_disc = self.params.get(u"_cache_to_disc_", True)
        self._manual_sort = list()
        self.content_type = _UNSET
        self.autosort = True

        # Check if results of callback are cached the return cache results,
        # else execute the callback and cache the results.
        results = callback(self, **callback_params)
        raw_listitems = validate_listitems(results)

        if raw_listitems is False:
            # Gracefully exit if callback explicitly return False
            xbmcplugin.endOfDirectory(self.handle, False)
        else:
            # Process the results and send results to kodi
            session_data = self._process_results(raw_listitems)
            logger.info("Session Data: %s", session_data)
            send_to_kodi(support.handle, session_data)

    def add_sort_methods(self, *methods, **kwargs):
        """
        Add sorting method(s).

        Any number of sort method's can be given as multiple arguments.
        Normally this should not be needed, as sort method's are auto detected.

        You can pass an optional keyword only argument, 'disable_autosort' to disable auto sorting.

        :param int methods: One or more Kodi sort method's.

        .. seealso:: The full list of sort methods can be found at.\n
                     https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#ga85b3bff796fd644fb28f87b136025f40
        """
        # Disable autosort if requested
        if kwargs.get("disable_autosort", False):
            self.autosort = False

        # Can't use sets here as sets don't keep order
        for method in methods:
            self._manual_sort.append(method)

    def _process_results(self, raw_listitems):  # type: (list) -> dict
        """Process the results and return a cacheable dict of session data."""
        return {"listitems": filter(None, raw_listitems),
                "category": ensure_native_str(self.category),
                "update_listing": self.update_listing, "cache_to_disc": self.cache_to_disc,
                "sortmethods": build_sortmethods(self._manual_sort, support.auto_sort if self.autosort else None),
                "content_type": self.content_type if self.content_type is not _UNSET else -1}
