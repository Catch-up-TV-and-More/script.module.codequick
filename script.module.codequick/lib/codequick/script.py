# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Package imports
import codequick.support as support

__all__ = ["Script"]


class Script(support.Base):
    """
    This class is used to create "Script" callbacks. Script callbacks are callbacks
    that just execute code and return nothing.

    This class is also used as the base for all other types of callbacks i.e.
    :class:`codequick.Route` and :class:`codequick.Resolver`.
    """
    def execute(self, callback, callback_params):
        callback(self, **callback_params)
