from .enum import EnumHook
from collections import OrderedDict
from .standard import StandardHook


def get_default_hooks():
    return OrderedDict(enum=EnumHook(), standard=StandardHook())
