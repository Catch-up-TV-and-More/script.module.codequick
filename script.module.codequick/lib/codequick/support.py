# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Standard Library Imports
from binascii import unhexlify
import urlparse
import logging
import json
import sys

# Kodi imports
import xbmc

# Package imports
from codequick.utils import parse_qs, ensure_str

# Level mapper to convert logging module levels to kodi logger levels
log_level_map = {10: xbmc.LOGDEBUG,    # logger.debug
                 20: xbmc.LOGNOTICE,   # logger.info
                 30: xbmc.LOGWARNING,  # logger.warning
                 40: xbmc.LOGERROR,    # logger.error
                 50: xbmc.LOGFATAL}    # logger.critical


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
        self.debug_msgs = []

    def emit(self, record):
        """
        Forward the log record to kodi, lets kodi handle the logging.

        :param logging.LogRecord record: The log event record.
        """
        log_level = record.levelno
        formatted_msg = self.format(record)

        # Kodi will not except unicode logs
        formatted_msg = ensure_str(formatted_msg)

        # Forward the log record to kodi with translated log level
        xbmc.log(formatted_msg, log_level_map[log_level])

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


class CacheProperty(object):
    """
    Converts a class method into a property. When property is accessed for the first time the result is computed
    and returned. The class property is then replaced with an instance attribute with the computed result.
    """

    def __init__(self, func):
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self._func = func

    def __get__(self, instance, owner):
        if instance:
            attr = self._func(instance)
            setattr(instance, self.__name__, attr)
            return attr
        else:
            return self


class Params(dict):
    """
    Parse the query string giving by kodi into a dictionary.
    Also splits the params into callback/support params.

    :param str params: The query string passeed in from kodi.
    :ivar dict callback_params: Parameters that will be forward to callback function.
    :ivar dict support_params: Parameters used for internal functions.
    """

    def __init__(self, params):
        super(Params, self).__init__()
        self.callback_params = {}
        self.support_params = {}

        if params:
            if params.startswith("_json_="):
                # Decode params using binascii & json
                params = json.loads(unhexlify(params[7:]))
            else:
                # Decode params using urlparse.parse_qs
                params = parse_qs(params)

            # Populate dict of params
            super(Params, self).__init__(params)

            # Construct separate dictionaries for callback and support params
            for key, value in self.iteritems():
                if key.startswith("_") and key.endswith("_"):
                    self.support_params[key] = value
                else:
                    self.callback_params[key] = value


def parse_sysargs():
    """
    Extract route selector & callback params from the command line arguments received from kodi.

    Selector is the path to the route callback.
    Handle is the id used for kodi to handle requests send from this addon.
    Params are the dictionary of parameters that controls the execution of this framework.

    :return: A tuple of (selector, handle, params)
    :rtype: tuple
    """
    # Only designed to work as a plugin
    if not sys.argv[0].startswith("plugin://"):
        raise RuntimeError("No parameters found, unable to execute script")

    # Extract command line arguments and remove leading '/' from selector
    _, _, selector, params, _ = urlparse.urlsplit(sys.argv[0] + sys.argv[2])
    selector = selector.split("/", 1)[-1]
    return selector if selector else "root", int(sys.argv[1]), Params(params)