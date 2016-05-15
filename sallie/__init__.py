# -*- coding: UTF-8 -*-
"""
TV information related tasks
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "the01"
__email__ = "jungflor@gmail.com"
__copyright__ = "Copyright (C) 2014-16, Florian JUNG"
__license__ = "MIT"
__version__ = "0.6.0b1"
__date__ = "2016-05-15"
# Created: 2015-02-26 03:39

import logging

from .tv_next import TVNext
from .next_tvdb import TVNextTVDB
from .cli_main import main

logger = logging.getLogger(__name__) # pylint: disable=invalid-name
__all__ = ["tv_next", "next_tvdb", "cli_main"]
