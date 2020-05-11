#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
# from __future__ import unicode_literals

__author__ = "d01 <Florian Jung>"
__email__ = "jungflor@gmail.com"
__copyright__ = "Copyright (C) 2015-20, Florian JUNG"
__license__ = "MIT"
__version__ = "0.2.2"
__date__ = "2020-05-11"
# Created: ?


from io import open
import os
import sys

import setuptools
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import sys
import os
import re


# Package meta-data.
NAME = "sallie"
DESCRIPTION = "TV episodes checker"
URL = "https://github.com/the01/python-sallie"
EMAIL = "jungflor@gmail.com"
AUTHOR = "the01"
REQUIRES_PYTHON = ">=3.6"
VERSION = None
LICENSE = "MIT License"


def get_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# What packages are required for this module to be executed?
try:
    REQUIRED = get_file("requirements.txt").split("\n")
except:
    REQUIRED = []

# What packages are required to execute tests?
try:
    REQUIRED_TEST = get_file("requirements-test.txt").split("\n")
except:
    REQUIRED_TEST = []

# What packages are optional?
EXTRAS = {
    # 'fancy feature': ['django'],
}

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    long_description = "\n" + get_file(os.path.join(here, "README.rst"))
except FileNotFoundError:
    long_description = DESCRIPTION
try:
    long_description += "\n\n" + get_file(os.path.join(here, "HISTORY.rst"))
except FileNotFoundError:
    pass

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")

    exec(get_file(os.path.join(here, "src/" + project_slug, "__version__.py")), about)
else:
    about['__version__'] = VERSION


if sys.argv[-1] == "build":
    quit(os.system("python setup.py clean bdist_wheel sdist --formats=zip"))


def split_external_requirements(requirements):
    external = []
    # External dependencies
    pypi = []
    # Dependencies on pypi

    for req in requirements:
        if req.startswith("-e git+"):
            # External git link
            external.append(req.lstrip("-e git+"))
        else:
            pypi.append(req)
    return pypi, external


setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    python_requires=REQUIRES_PYTHON,
    install_requires=REQUIRED,
    tests_require=REQUIRED_TEST,
    extras_require=EXTRAS,
    # dependency_links=external,

    packages=setuptools.find_packages("src"),
    package_dir={
        '': "src",
    },
    #scripts=["scripts/sallie"],
    entry_points={
        'console_scripts': [
            "sallie=sallie.cli_main:main",
        ]
    },
    include_package_data=True,
    zip_safe=False,
    license=LICENSE,
    keywords="sallie tv shows tvdb",
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
    ]
)
