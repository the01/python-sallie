# -*- coding: UTF-8 -*-
""" TV information related tasks """

__author__ = "the01"
__email__ = "jungflor@gmail.com"
__copyright__ = "Copyright (C) 2014-20, Florian JUNG"
__license__ = "MIT"
__date__ = "2020-06-15"
# Created: 2015-02-26 03:39

import logging

from .__version__ import __version__
from .cli_main import main
from .next_tvdb import TVNextTVDB
from .tv_next import TVNext


logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
__all__ = [
    "__version__",
    "tv_next", "next_tvdb", "cli_main",
    "TVNext", "TVNextTVDB", "main",
]
