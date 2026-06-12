"""Default structures for Rekuest Next"""

from rekuest_next.structures.default import get_default_structure_registry, id_shrink
from rekuest_next.api.schema import (
    Implementation,
    Action,
    SearchImplementationsQuery,
    SearchActionsQuery,
    SearchTestCasesQuery,
    SearchTestResultsQuery,
    SearchShortcutsQuery,
    Shortcut,
    TestCase,
    TestResult,
    AssignationEvent,
    aget_event,
    aget_shortcut,
    aget_test_case,
    aget_test_result,
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
        query=SearchImplementationsQuery.Meta.document, ward="rekuest"
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
    aexpand=aget_test_case,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=SearchTestCasesQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    TestResult,
    "@rekuest/testresult",
    aexpand=aget_test_result,
    ashrink=id_shrink,
    default_widget=SearchWidget(
        query=SearchTestResultsQuery.Meta.document, ward="rekuest"
    ),
)

structure_reg.register_as_structure(
    AssignationEvent,
    identifier="@rekuest/assignationevent",
    aexpand=aget_event,
    ashrink=id_shrink,
)
