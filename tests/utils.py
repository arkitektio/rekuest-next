"""Some utility functions for the tests"""

import os

DIR_NAME = os.path.dirname(os.path.realpath(__file__))


def build_relative(path: str) -> str:
    """Build a relative path to the test directory"""
    return os.path.join(DIR_NAME, path)
