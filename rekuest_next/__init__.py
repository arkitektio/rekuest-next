__version__ = "0.1.1"


from rekuest_next.structures.hooks.standard import id_shrink
from rekuest_next.widgets import SearchWidget

from .utils import acall, afind, areserve, reserved, call, aiterate, iterate
from .api.schema import (
    AssignationEventFragment,
    aget_event,
    NodeFragment,
    afind,
    Search_nodesQuery,
)
from .structures.default import get_default_structure_registry
from .arkitekt import imported

structur_reg = get_default_structure_registry()


structur_reg.register_as_structure(
    AssignationEventFragment,
    identifier="@rekuest/assignationevent",
    aexpand=aget_event,
    ashrink=id_shrink,
)

structur_reg.register_as_structure(
    NodeFragment,
    identifier="@rekuest/node",
    aexpand=afind,
    ashrink=id_shrink,
    default_widget=SearchWidget(query=Search_nodesQuery.Meta.document, ward="rekuest"),
)


__all__ = [
    "acall",
    "afind",
    "areserve",
    "reserved",
    "call",
    "find",
    "reserve",
    "structur_reg",
    "imported",
    "iterate",
    "aiterate",
]
