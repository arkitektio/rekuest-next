__version__ = "0.1.1"


from rekuest_next.structures.hooks.standard import id_shrink

from .api.schema import AssignationEventFragment, aget_event
from .structures.default import get_default_structure_registry
from .arkitekt import imported

structur_reg = get_default_structure_registry()


structur_reg.register_as_structure(
    AssignationEventFragment,
    identifier="@rekuest/assignationevent",
    aexpand=aget_event,
    ashrink=id_shrink,
)
