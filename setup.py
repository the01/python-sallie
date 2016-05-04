#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
# from __future__ import unicode_literals

__author__ = "d01 <Florian Jung>"
__email__ = "jungflor@gmail.com"
__copyright__ = "Copyright (C) 2015-16, Florian JUNG"
__license__ = "MIT"
__version__ = "0.2.0"
__date__ = "2016-05-04"
# Created: ?

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import sys
import os
import re


if sys.argv[-1] == "build":
    os.system("python setup.py clean sdist bdist bdist_egg bdist_wheel")


def get_version():
    """
    Parse the version information from the init file
    """
    version_file = os.path.join("sallie", "__init__.py")
    initfile_lines = open(version_file, "rt").readlines()
    version_reg = r"^__version__ = ['\"]([^'\"]*)['\"]"
    for line in initfile_lines:
        mo = re.search(version_reg, line, re.M)
        if mo:
            return mo.group(1)
    raise RuntimeError(
        u"Unable to find version string in {}".format(version_file)
    )


def get_file(path):
    with open(path, "r") as f:
        return f.read()


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


version = get_version()
readme = get_file("README.rst")
history = get_file("HISTORY.rst")
pypi, external = split_external_requirements(
    get_file("requirements.txt").split("\n")
)

assert version is not None
assert readme is not None
assert history is not None
assert pypi is not None
assert external is not None

setup(
    name="sallie",
    version=version,
    description="TV episodes checker",
    long_description=readme + "\n\n" + history,
    author="the01",
    author_email="jungflor@gmail.com",
    url="https://github.com/the01/python-sallie",
    packages=[
        "sallie"
    ],
    install_requires=pypi,
    dependency_links=external,
    scripts=["scripts/sallie"],
    license="MIT License",
    keywords="sallie tv shows tvdb",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
    ]
)
