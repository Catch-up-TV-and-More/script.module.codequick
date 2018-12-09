Script
======
This module is used for creating "Script" callback's, which are also used as the base for all other types of callbacks.

.. autofunction:: codequick.run

.. autoclass:: codequick.Script()
    :members:
    :inherited-members:

    .. attribute:: handle
        :annotation: = -1

        The Kodi handle that this add-on was started with.

    .. attribute:: DEBUG
        :annotation: = 10

        Debug logging level, maps to "xbmc.LOGDEBUG".

    .. attribute:: INFO
        :annotation: = 20

        Info logging level, maps to "xbmc.LOGNOTICE".

    .. attribute:: WARNING
        :annotation: = 30

        Warning logging level, maps to "xbmc.LOGWARNING".

    .. attribute:: ERROR
        :annotation: = 40

        Error logging level, maps to "xbmc.LOGERROR".

    .. attribute:: CRITICAL
        :annotation: = 50

        Critical logging level, maps to "xbmc.LOGFATAL".

    .. attribute:: NOTIFY_WARNING
        :annotation: = 'warning'

        Kodi notification warning image.

    .. attribute:: NOTIFY_ERROR
        :annotation: = 'error'

        Kodi notification error image.

    .. attribute:: NOTIFY_INFO
        :annotation: = 'info'

        Kodi notification info image.

    .. attribute:: setting
        :annotation: = Settings()

        Dictionary like interface of "add-on" settings.
        See :class:`script.Settings<codequick.support.Settings>` for more details.


.. autoclass:: codequick.support.Settings
    :members:
    :special-members:
