Route
=====
This module is used for the creation of “Route callbacks”.

.. autoclass:: codequick.Route()
    :members: add_sort_methods

    .. attribute:: cache_ttl
        :annotation: = -1

        The time in minutes that the cache will be valid for, Value of -1 disables cacheing.

        .. note::  This parameter can only be set when registering a callback, see :meth:`codequick.Script.register`

    .. attribute:: autosort
        :annotation: = True

        Set to ``False`` to disable auto sortmethod selection.

        .. note::  If autosort is disabled and no sortmethods are given, then SORT_METHOD_UNSORTED will be set.

    .. attribute:: update_listing
        :annotation: = False

        When set to ``True``, the current page of listitems will be updated, instead of creating a new page of listitems.

    .. attribute:: category
        :annotation: = ""

        The category name of the current list, defaults to the title of previously selected listitem.

    .. attribute:: content_type
        :annotation: = None

        The add-on’s "content type".

        If not given, then the "content type" is based on the "mediatype" infolabel of the listitems.
        If the “mediatype” infolabel” was not set, then it defaults to “files/videos”, based on type of content.

        * "files" when listing folders.
        * "videos" when listing videos.

        .. seealso:: The full list of "content types" can be found at:

                     https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#gaa30572d1e5d9d589e1cd3bfc1e2318d6
