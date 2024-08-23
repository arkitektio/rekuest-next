from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.hooks.standard import id_shrink
from rekuest_next.api.schema import (
    TemplateFragment,
    NodeFragment,
    Search_templatesQuery,
    Search_nodesQuery,
    Search_testcasesQuery,
    Search_testresultsQuery,
    TestCaseFragment,
    TestResultFragment,
    AssignationEventFragment,
    aget_agent,
    aget_event,
    aget_template,
    aget_testcase,
    aget_testresult,
    aget_template,
    afind,
    PortScope,
)
from rekuest_next.widgets import SearchWidget


def register_structures(structure_reg):
    structure_reg.register_as_structure(
        TemplateFragment,
        "@rekuest/template",
        scope=PortScope.GLOBAL,
        aexpand=aget_template,
        ashrink=id_shrink,
        default_widget=SearchWidget(
            query=Search_templatesQuery.Meta.document, ward="rekuest"
        ),
    )

    structure_reg.register_as_structure(
        NodeFragment,
        "@rekuest/node",
        scope=PortScope.GLOBAL,
        aexpand=afind,
        ashrink=id_shrink,
        default_widget=SearchWidget(
            query=Search_nodesQuery.Meta.document, ward="rekuest"
        ),
    )

    structure_reg.register_as_structure(
        TestCaseFragment,
        "@rekuest/testcase",
        scope=PortScope.GLOBAL,
        aexpand=aget_testcase,
        ashrink=id_shrink,
        default_widget=SearchWidget(
            query=Search_testcasesQuery.Meta.document, ward="rekuest"
        ),
    )

    structure_reg.register_as_structure(
        TestResultFragment,
        "@rekuest/testresult",
        scope=PortScope.GLOBAL,
        aexpand=aget_testresult,
        ashrink=id_shrink,
        default_widget=SearchWidget(
            query=Search_testresultsQuery.Meta.document, ward="rekuest"
        ),
    )

    structure_reg.register_as_structure(
        AssignationEventFragment,
        identifier="@rekuest/assignationevent",
        aexpand=aget_event,
        ashrink=id_shrink,
    )
