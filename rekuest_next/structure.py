"""Default structures for Rekuest Next"""

from rekuest_next.structures.default import get_default_structure_registry, id_shrink
from rekuest_next.api.schema import (
    Implementation,
    Action,
    Search_implementationsQuery,
    SearchActionsQuery,
    Search_testcasesQuery,
    Search_testresultsQuery,
    SearchShortcutsQuery,
    Shortcut,
    TestCase,
    TestResult,
    AssignationEvent,
    aget_event,
    aget_shortcut,
    aget_testcase,
    aget_testresult,
    aget_implementation,
    afind,
)
from rekuest_next.widgets import SearchWidget

structure_reg = get_default_structure_registry()
structure_reg.register_as_structure(
    Implementation,
    "@rekuest/implementation",
    aexpand=aget_implementation,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=Search_implementationsQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    Action,
    "@rekuest/action",
    aexpand=afind,
    ashrink=id_shrink,
    default_widget=SearchWidget(query=SearchActionsQuery.Meta.document, ward="rekuest"),
)

structure_reg.register_as_structure(
    Shortcut,
    "@rekuest/shortcut",
    aexpand=aget_shortcut,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=SearchShortcutsQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    TestCase,
    "@rekuest/testcase",
    aexpand=aget_testcase,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=Search_testcasesQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    TestResult,
    "@rekuest/testresult",
    aexpand=aget_testresult,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=Search_testresultsQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    AssignationEvent,
    identifier="@rekuest/assignationevent",
    aexpand=aget_event,
    ashrink=id_shrink,
)
