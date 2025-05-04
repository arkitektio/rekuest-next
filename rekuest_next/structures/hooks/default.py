"""Hooks for Rekuest Next"""

from .enum import EnumHook
from collections import OrderedDict
from .memory_structure import MemoryStructureHook
from .global_structure import GlobalStructureHook
from .types import RegistryHook


def get_default_hooks() -> OrderedDict[str, RegistryHook]:
    """Get the default hooks for Rekuest Next."""
    return OrderedDict(
        enum=EnumHook(),
        global_structure=GlobalStructureHook(),
        local_structure=MemoryStructureHook(),
    )
