Route
=====
This module is used for the creation of “Route callbacks”.

.. autoclass:: codequick.Route()

    .. attribute:: cache_ttl
        :annotation: = 0

        The cache time to live value when using route caching

        Value of -1 will force cache to be always fresh.
        Value of 0 will disable the cache.
        Value greater than 0 is the time in minutes that the cache will be valid for.

        Caching is disabled by default, unless a cache_ttl value greater than 0 is set.
        But this may change in the future.

        .. note::  This parameter can only be set when registering a Route callback, See :meth:`codequick.Script.register`

    .. attribute:: sort_methods
        :annotation: = []

        List of sorting methods for the media list.

    .. attribute:: autosort
        :annotation: = True

        Set to ``False`` to disable auto sortmethod selection.

        By default, sortmethods are auto selected based on the set infolabels.

        .. note::  If autosort is disabled and no sortmethods are given, then SORT_METHOD_UNSORTED will be set.

    .. attribute:: update_listing
        :annotation: = False

        When set to ``True``, the current page of listitems will be updated, instead of creating a new page of listitems.

    .. attribute:: category
        :annotation: = ""

        The category name of the current list, defaults to the title of previously selected listitem.

    .. attribute:: content_type
        :annotation: = unset

        The add-on’s "content type".

        If left unset, then the "content type" is based on the "mediatype" infolabel of the listitems.
        If the “mediatype” infolabel” was not set, then it defaults to “files/videos”, based on type of content.

        * "files" when listing folders.
        * "videos" when listing videos.

        .. seealso:: The full list of "content types" can be found at:

                     https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#gaa30572d1e5d9d589e1cd3bfc1e2318d6
