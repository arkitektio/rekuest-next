import types
import typing
from typing import get_origin


UNION_TYPE_PREDICATE = getattr(types, "UnionType", False)


def cls_is_union(cls):
    return get_origin(cls) is UNION_TYPE_PREDICATE or get_origin(cls) is typing.Union


def cls_is_list(cls):
    return get_origin(cls) is typing.List
