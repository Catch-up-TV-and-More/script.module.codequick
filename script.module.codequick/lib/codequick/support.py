# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Standard Library Imports
import binascii
import logging
import inspect
import pickle
import time
import sys
import re

# Kodi imports
import xbmcaddon
import xbmcgui
import xbmc

# Package imports
from codequick.utils import parse_qs, ensure_native_str, urlparse, PY3, unicode_type

script_data = xbmcaddon.Addon("script.module.codequick")
addon_data = xbmcaddon.Addon()

plugin_id = addon_data.getAddonInfo("id")
logger_id = re.sub("[ .]", "-", addon_data.getAddonInfo("name"))

# Logger specific to this module
logger = logging.getLogger("%s.support" % logger_id)

# Dictionary of registered delayed execution callback
registered_delayed = []

# Dictionary of registered callback
registered_routes = {}

# Session data
selector = "root"
auto_sort = set()
params = {}
handle = -1


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
    __slots__ = ("parent", "func", "path", "is_playable", "is_folder")

    def __getstate__(self):
        return self.path

    def __setstate__(self, state):
        obj = registered_routes[state]
        self.is_playable = obj.is_playable
        self.is_folder = obj.is_folder
        self.parent = obj.parent
        self.func = obj.func
        self.path = obj.path

    def __eq__(self, other):
        return self.path == other.path

    def __init__(self, callback, parent):
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

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def execute(self, callback_params):
        parent_ins = self.parent()
        results = self.func(parent_ins, **callback_params)

        if hasattr(parent_ins, "_process_results"):
            # noinspection PyProtectedMember
            parent_ins._process_results(results)

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
    _, _, route, raw_params, _ = urlparse.urlsplit(sys.argv[0] + sys.argv[2])
    globals()["selector"] = route if len(route) > 1 else "root"
    globals()["handle"] = int(sys.argv[1])

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
        route.execute(callback_params)

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
        logger.debug("Route Execution Time: %ims", (time.time() - execute_time) * 1000)
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


# Setup kodi logging
kodi_logger = KodiLogHandler()
base_logger = logging.getLogger()
base_logger.addHandler(kodi_logger)
base_logger.setLevel(logging.DEBUG)
base_logger.propagate = False
