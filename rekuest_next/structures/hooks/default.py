from .enum import EnumHook
from collections import OrderedDict
from .local_structure import LocalStructureHook
from .global_structure import GlobalStructureHook


def get_default_hooks():
    return OrderedDict(enum=EnumHook(), global_structure=GlobalStructureHook(), local_structure=LocalStructureHook(),) 
