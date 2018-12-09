# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Standard Library Imports
from hashlib import sha1
import binascii
import logging
import inspect
import pickle
import time
import sys
import re
import os

# Kodi imports
import xbmcaddon
import xbmcgui
import xbmc

# Package imports
from codequick.utils import parse_qs, ensure_native_str, urlparse, PY3, unicode_type, ensure_unicode, string_map

script_data = xbmcaddon.Addon("script.module.codequick")
addon_data = xbmcaddon.Addon()

plugin_id = addon_data.getAddonInfo("id")
logger_id = re.sub("[ .]", "-", addon_data.getAddonInfo("name"))

# Logger specific to this module
logger = logging.getLogger("%s.support" % logger_id)
addon_logger = logging.getLogger(logger_id)

# Dictionary of registered delayed execution callback
registered_delayed = []

# Dictionary of registered callback
registered_routes = {}

# Session data
selector = "root"
auto_sort = set()
params = {}
handle = -1
session_id = None


class Settings(object):
    """Settings class to handle the getting and setting of "add-on" settings."""

    def __getitem__(self, key):
        """
        Returns the value of a setting as a "unicode string".

        :param str key: ID of the setting to access.

        :return: Setting as a "unicode string".
        :rtype: str
        """
        return addon_data.getSetting(key)

    def __setitem__(self, key, value):
        """
        Set add-on setting.

        :param str key: ID of the setting.
        :param str value: Value of the setting.
        """
        # noinspection PyTypeChecker
        addon_data.setSetting(key, ensure_unicode(value))

    def __delitem__(self, key):  # type: (str) -> None
        """
        Set an add-on setting to a blank string.

        :param str key: ID of the setting to delete.
        """
        addon_data.setSetting(key, "")

    @staticmethod
    def get_string(key, addon_id=None):
        """
        Returns the value of a setting as a "unicode string".

        :param str key: ID of the setting to access.
        :param str addon_id: [opt] ID of another add-on to extract settings from.

        :raises RuntimeError: If ``addon_id`` is given and there is no add-on with given ID.

        :return: Setting as a "unicode string".
        :rtype: str
        """
        if addon_id:
            return xbmcaddon.Addon(addon_id).getSetting(key)
        else:
            return addon_data.getSetting(key)

    @staticmethod
    def get_boolean(key, addon_id=None):
        """
        Returns the value of a setting as a "Boolean".

        :param str key: ID of the setting to access.
        :param str addon_id: [opt] ID of another add-on to extract settings from.

        :raises RuntimeError: If ``addon_id`` is given and there is no add-on with given ID.

        :return: Setting as a "Boolean".
        :rtype: bool
        """
        setting = Settings.get_string(key, addon_id).lower()
        return setting == u"true" or setting == u"1"

    @staticmethod
    def get_int(key, addon_id=None):
        """
        Returns the value of a setting as a "Integer".

        :param str key: ID of the setting to access.
        :param str addon_id: [opt] ID of another add-on to extract settings from.

        :raises RuntimeError: If ``addon_id`` is given and there is no add-on with given ID.

        :return: Setting as a "Integer".
        :rtype: int
        """
        return int(Settings.get_string(key, addon_id))

    @staticmethod
    def get_number(key, addon_id=None):
        """
        Returns the value of a setting as a "Float".

        :param str key: ID of the setting to access.
        :param str addon_id: [opt] ID of another addon to extract settings from.

        :raises RuntimeError: If ``addon_id`` is given and there is no addon with given ID.

        :return: Setting as a "Float".
        :rtype: float
        """
        return float(Settings.get_string(key, addon_id))


class Base(object):
    """Base class for all calback type."""
    is_playable = False
    is_folder = False

    CRITICAL = logging.CRITICAL
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    DEBUG = logging.DEBUG
    INFO = logging.INFO

    NOTIFY_WARNING = 'warning'
    NOTIFY_ERROR = 'error'
    NOTIFY_INFO = 'info'

    # Dictionary like interface of "add-on" settings.
    setting = Settings()

    # Underlining logger object, for advanced use. See :class:`logging.Logger` for more details.
    logger = addon_logger

    # Dictionary of all callback parameters, for advanced use.
    params = params

    def __init__(self):
        self._title = self.params.get(u"_title_", u"")
        self.handle = handle

    @classmethod
    def register(cls, func=None, **kwargs):
        """
        Decorator used to register callback functions.

        Can be called with or without arguments. If arguments are given, they have to be "keyword only" arguments.
        The keyword arguments are parameters that are used by the plugin class instance.
        e.g. autosort=False to disable auto sorting for Route callbacks

        :example:
            >>> from codequick import Route, Listitem
            >>>
            >>> @Route.register
            >>> def root(_):
            >>>     yield Listitem.from_dict("Extra videos", subfolder)
            >>>
            >>> @Route.register(cache_ttl=240, content_type="videos")
            >>> def subfolder(_):
            >>>     yield Listitem.from_dict("Play video",
                    "http://www.example.com/video1.mkv")

        :param function func: The callback function to register.
        :param kwargs: Keyword only arguments to pass to callback handler.
        :returns: A callback instance.
        :rtype: Callback
        """
        if inspect.isfunction(func):
            return Callback(func, parent=cls, data=kwargs)
        elif func is None:
            def wrapper(real_func):
                return Callback(real_func, parent=cls, data=kwargs)
            return wrapper
        else:
            raise ValueError("Only keyword arguments are allowed")

    @staticmethod
    def register_delayed(func, *args, **kwargs):
        """
        Registers a function that will be executed after Kodi has finished listing all "listitems".
        Since this function is called after the listitems have been shown, it will not slow down the
        listing of content. This is very useful for fetching extra metadata for later use.

        .. note::

            Functions will be called in reverse order to the order they are added (LIFO).

        :param func: Callable that will be called after "xbmcplugin.endOfDirectory" is called.
        :param args: "Positional" arguments that will be passed to function.
        :param kwargs: "Keyword" arguments that will be passed to function.
        """
        callback = (func, args, kwargs)
        registered_delayed.append(callback)

    @staticmethod
    def log(msg, args=None, lvl=10):
        """
        Logs a message with logging level of "lvl".

        Logging Levels.
            * :attr:`Script.DEBUG<codequick.script.Script.DEBUG>`
            * :attr:`Script.INFO<codequick.script.Script.INFO>`
            * :attr:`Script.WARNING<codequick.script.Script.WARNING>`
            * :attr:`Script.ERROR<codequick.script.Script.ERROR>`
            * :attr:`Script.CRITICAL<codequick.script.Script.CRITICAL>`

        :param msg: The message format string.
        :type args: list or tuple
        :param args: List of arguments which are merged into msg using the string formatting operator.
        :param int lvl: The logging level to use. default => 10 (Debug).

        .. note::

            When a log level of 50(CRITICAL) is given, all debug messages that were previously logged will
            now be logged as level 30(WARNING). This allows for debug messages to show in the normal Kodi
            log file when a CRITICAL error has occurred, without having to enable Kodi's debug mode.
        """
        if args:
            addon_logger.log(lvl, msg, *args)
        else:
            addon_logger.log(lvl, msg)

    @staticmethod
    def notify(heading, message, icon=None, display_time=5000, sound=True):
        """
        Send a notification to Kodi.

        Options for icon are.
            * :attr:`Script.NOTIFY_INFO<codequick.script.Script.NOTIFY_INFO>`
            * :attr:`Script.NOTIFY_ERROR<codequick.script.Script.NOTIFY_ERROR>`
            * :attr:`Script.NOTIFY_WARNING<codequick.script.Script.NOTIFY_WARNING>`

        :param str heading: Dialog heading label.
        :param str message: Dialog message label.
        :param str icon: [opt] Icon image to use. (default => 'add-on icon image')

        :param int display_time: [opt] Ttime in "milliseconds" to show dialog. (default => 5000)
        :param bool sound: [opt] Whether or not to play notification sound. (default => True)
        """
        # Ensure that heading, message and icon
        # is encoded into native str type
        heading = ensure_native_str(heading)
        message = ensure_native_str(message)
        icon = ensure_native_str(icon if icon else Base.get_info("icon"))

        dialog = xbmcgui.Dialog()
        dialog.notification(heading, message, icon, display_time, sound)

    @staticmethod
    def localize(string_id):
        """
        Retruns a translated UI string from addon localization files.

        .. note::

            :data:`utils.string_map<codequick.utils.string_map>`
            needs to be populated before you can pass in a string as the reference.

        :param string_id: The numeric ID or gettext string ID of the localized string
        :type string_id: str or int

        :returns: Localized unicode string.
        :rtype: str

        :raises Keyword: if a gettext string ID was given but the string is not found in English :file:`strings.po`.
        :example:
            >>> Base.localize(30001)
            "Toutes les vidéos"
            >>> Base.localize("All Videos")
            "Toutes les vidéos"
        """
        if isinstance(string_id, (str, unicode_type)):
            try:
                numeric_id = string_map[string_id]
            except KeyError:
                raise KeyError("no localization found for string id '%s'" % string_id)
            else:
                return addon_data.getLocalizedString(numeric_id)

        elif 30000 <= string_id <= 30999:
            return addon_data.getLocalizedString(string_id)
        elif 32000 <= string_id <= 32999:
            return script_data.getLocalizedString(string_id)
        else:
            return xbmc.getLocalizedString(string_id)

    @staticmethod
    def get_info(key, addon_id=None):
        """
        Returns the value of an add-on property as a unicode string.

        Properties.
            * author
            * changelog
            * description
            * disclaimer
            * fanart
            * icon
            * id
            * name
            * path
            * profile
            * stars
            * summary
            * type
            * version

        :param str key: "Name" of the property to access.
        :param str addon_id: [opt] ID of another add-on to extract properties from.

        :return: Add-on property as a unicode string.
        :rtype: str

        :raises RuntimeError: If add-on ID is given and there is no add-on with given ID.
        """
        if addon_id:
            # Extract property from a different add-on
            resp = xbmcaddon.Addon(addon_id).getAddonInfo(key)
        elif key == "path_global" or key == "profile_global":
            # Extract property from codequick addon
            resp = script_data.getAddonInfo(key[:key.find("_")])
        else:
            # Extract property from the running addon
            resp = addon_data.getAddonInfo(key)

        # Check if path needs to be translated first
        if resp[:10] == "special://":  # pragma: no cover
            resp = xbmc.translatePath(resp)

        # Convert response to unicode
        path = resp.decode("utf8") if isinstance(resp, bytes) else resp

        # Create any missing directory
        if key.startswith("profile"):
            if not os.path.exists(path):  # pragma: no cover
                os.mkdir(path)

        return path


class LoggingMap(dict):
    def __init__(self):
        super(LoggingMap, self).__init__()
        self[10] = xbmc.LOGDEBUG    # logger.debug
        self[20] = xbmc.LOGNOTICE   # logger.info
        self[30] = xbmc.LOGWARNING  # logger.warning
        self[40] = xbmc.LOGERROR    # logger.error
        self[50] = xbmc.LOGFATAL    # logger.critical

    def __missing__(self, key):
        """Return log notice for any unexpected log level."""
        return xbmc.LOGNOTICE


class KodiLogHandler(logging.Handler):
    """
    Custom Logger Handler to forward logs to Kodi.

    Log records will automatically be converted from unicode to utf8 encoded strings.
    All debug messages will be stored locally and outputed as warning messages if a critical error occurred.
    This is done so that debug messages will appear on the normal kodi log file without having to enable debug logging.

    :ivar debug_msgs: Local store of degub messages.
    """
    def __init__(self):
        super(KodiLogHandler, self).__init__()
        self.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        self.log_level_map = LoggingMap()
        self.debug_msgs = []

    def emit(self, record):  # type: (logging.LogRecord) -> None
        """Forward the log record to kodi, lets kodi handle the logging."""
        formatted_msg = ensure_native_str(self.format(record))
        log_level = record.levelno

        # Forward the log record to kodi with translated log level
        xbmc.log(formatted_msg, self.log_level_map[log_level])

        # Keep a history of all debug records so they can be logged later if a critical error occurred
        # Kodi by default, won't show debug messages unless debug logging is enabled
        if log_level == 10:
            self.debug_msgs.append(formatted_msg)

        # If a critical error occurred, log all debug messages as warnings
        elif log_level == 50 and self.debug_msgs:
            xbmc.log("###### debug ######", xbmc.LOGWARNING)
            for msg in self.debug_msgs:
                xbmc.log(msg, xbmc.LOGWARNING)
            xbmc.log("###### debug ######", xbmc.LOGWARNING)


class Callback(object):
    """
    Register callback function

    :param function callback: The callback function.
    :param parent: Parent class that will handle the callback, used when callback is a function.

    :ivar bool is_playable: True if callback is playable, else False.
    :ivar bool is_folder: True if callback is a folder, else False.
    :ivar function callback: The decorated function.
    :ivar Script parent: The parent class that will handle the response from callback.
    :ivar str path: The route path to function.
    """
    __slots__ = ("parent", "func", "path", "is_playable", "is_folder", "data")

    def __getstate__(self):
        return self.path

    def __setstate__(self, state):
        obj = registered_routes[state]
        self.is_playable = obj.is_playable
        self.is_folder = obj.is_folder
        self.parent = obj.parent
        self.func = obj.func
        self.path = obj.path

    def __init__(self, callback, parent, data):
        # Construct route path
        path = callback.__name__.lower()
        if path != "root":
            path = "/{}/{}/".format(callback.__module__.strip("_").replace(".", "/"), callback.__name__).lower()

        registered_routes[path] = self
        self.is_playable = parent.is_playable
        self.is_folder = parent.is_folder
        self.parent = parent
        self.func = callback
        self.path = path
        self.data = data

    def __eq__(self, other):
        return self.path == other.path

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def args_to_kwargs(self, args, kwargs):  # type: (tuple, dict) -> None
        """Convert positional arguments to keyword arguments and merge into callback parameters."""
        callback_args = self.arg_names()[1:]
        arg_map = zip(callback_args, args)
        kwargs.update(arg_map)

    def arg_names(self):  # type: () -> list
        """Return a list of argument names, positional and keyword arguments."""
        if PY3:
            return inspect.getfullargspec(self.func).args
        else:
            # noinspection PyDeprecation
            return inspect.getargspec(self.func).args

    def test(self, *args, **kwargs):
        """
        Function to allow callbacks to be easily called from unittests.
        Parent argument will be auto instantiated and passed to callback.
        This basically acts as a constructor to callback.

        You can pass an optional keyword only argument, 'execute_delayed'
        Set to true to execute any registered delayed callbacks.

        :param args: Positional arguments to pass to callback.
        :param kwargs: Keyword arguments to pass to callback.
        :returns: The response from the callback function.
        """
        execute_delayed = kwargs.pop("execute_delayed", False)

        # Ensure that all session parameters are reset before we start
        reset_session()

        # Change selector to the path of the callback been tested
        globals()["selector"] = self.path

        # Update global params with the positional args
        if args:
            self.args_to_kwargs(args, params)

        # Update global params with keyword args
        if kwargs:
            params.update(kwargs)

        # Instantiate the parent class
        parent_ins = self.parent()

        try:
            # Now we are ready to call the callback function that we want to test
            results = self.func(parent_ins, *args, **kwargs)

            # Ensure the we always have a list to work with
            if inspect.isgenerator(results):
                results = list(results)

            # Execute Delated callback functions if any ware registered
            if execute_delayed and registered_delayed:
                run_delayed()

            # Now we can return the results from the callback
            return results

        finally:
            # Just to be sure we will reset
            # the session parameters again
            reset_session()


def reset_session():
    """Reset Session data, required when setting reuselanguageinvoker to true"""
    globals()["selector"] = "root"
    kodi_logger.debug_msgs = []
    registered_delayed[:] = []
    auto_sort.clear()
    params.clear()


def get_callback(path=None):
    """
    Return the given route callback.

    :param Callback path: [opt] Path to callback
    :rtype: Callback
    """
    return registered_routes[path if path else selector]


def parse_args():
    """
    Extract arguments given by Kodi

    :returns: Callback related params
    :rtype: dict
    """
    global_vars = globals()
    url = sys.argv[0] + sys.argv[2]
    global_vars["session_id"] = sha1(url).hexdigest()

    _, _, route, raw_params, _ = urlparse.urlsplit(sys.argv[0] + sys.argv[2])
    global_vars["selector"] = route if len(route) > 1 else "root"
    global_vars["handle"] = int(sys.argv[1])

    logger.debug("Dispatching to route: '%s'", selector)

    if raw_params:
        current_params = parse_qs(raw_params)
        params.update(current_params)

        # Unpickle pickled data
        if "_pickle_" in params:
            unpickled = pickle.loads(binascii.unhexlify(params.pop("_pickle_")))
            params.update(unpickled)

    # Construct a separate dictionary for callback specific parameters
    return {key: value for key, value in params.items() if not (key.startswith(u"_") and key.endswith(u"_"))}


def build_path(callback=None, args=None, query=None, **extra_query):
    """
    Build addon url that can be passeed to kodi for kodi to use when calling listitems.

    :param Callback callback: [opt] The route path referencing the callback object. (default => current route selector)
    :param tuple args: [opt] Positional arguments that will be add to plugin path.
    :param dict query: [opt] A set of query key/value pairs to add to plugin path.
    :param extra_query: [opt] Keyword arguments if given will be added to the current set of querys.

    :return: Plugin url for kodi.
    :rtype: str
    """
    # Set callback to current callback if not given
    if callback is None:
        callback = get_callback()

    # Convert args to keyword args if required
    if args:
        callback.args_to_kwargs(args, query)

    # If extra querys are given then append the
    # extra querys to the current set of querys
    if extra_query:
        query = params.copy()
        query.update(extra_query)

    # Encode the query parameters using json
    if query:
        pickled = binascii.hexlify(pickle.dumps(query, protocol=pickle.HIGHEST_PROTOCOL))
        query = "_pickle_={}".format(pickled.decode("ascii") if PY3 else pickled)

    # Build kodi url with new path and query parameters
    return urlparse.urlunsplit(("plugin", plugin_id, callback.path, query, ""))


def run():
    """
    The starting point of the add-on.

    This function will handle the execution of "callback" functions.
    The callback function that will be executed, will be auto selected.

    The "root" callback, is the callback that will be the initial
    starting point for the add-on.
    """
    # Reset Session data
    reset_session()

    try:
        # Fetch params pass in by kodi
        callback_params = parse_args()
        logger.debug("Callback parameters: '%s'", callback_params)
        route = get_callback()

        # Execute callback
        execute_time = time.time()
        route.parent(route, callback_params)

    except Exception as e:
        try:
            msg = str(e)
        except UnicodeEncodeError:
            # This is python 2 only code
            # We only use unicode to fetch message when we
            # know that we are dealing with unicode data
            msg = unicode_type(e).encode("utf8")

        # Log the error in both the gui and the kodi log file
        dialog = xbmcgui.Dialog()
        dialog.notification(e.__class__.__name__, msg, xbmcgui.NOTIFICATION_ERROR)
        logger.critical(msg, exc_info=1)

    else:
        logger.info("Route Execution Time: %ims", (time.time() - execute_time) * 1000)
        run_delayed()


def run_delayed():
    """Execute all delayed callbacks, if any."""
    if registered_delayed:
        # Time before executing callbacks
        start_time = time.time()

        # Execute in order of last in first out (LIFO).
        while registered_delayed:
            func, args, kwargs = registered_delayed.pop()

            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.exception(str(e))

        # Log execution time of callbacks
        logger.debug("Callbacks Execution Time: %ims", (time.time() - start_time) * 1000)


# Setup kodi logging
kodi_logger = KodiLogHandler()
base_logger = logging.getLogger()
base_logger.addHandler(kodi_logger)
base_logger.setLevel(logging.DEBUG)
base_logger.propagate = False
