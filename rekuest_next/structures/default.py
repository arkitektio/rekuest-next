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
    aget_template,
    aget_testcase,
    aget_testresult,
    aget_template,
    afind,
    PortScope,
)
from rekuest_next.widgets import SearchWidget


DEFAULT_STRUCTURE_REGISTRY = None


def get_default_structure_registry() -> StructureRegistry:
    global DEFAULT_STRUCTURE_REGISTRY
    if not DEFAULT_STRUCTURE_REGISTRY:
        DEFAULT_STRUCTURE_REGISTRY = StructureRegistry()

        DEFAULT_STRUCTURE_REGISTRY.register_as_structure(
            TemplateFragment,
            "@rekuest_next/template",
            scope=PortScope.GLOBAL,
            aexpand=aget_template,
            ashrink=id_shrink,
            default_widget=SearchWidget(
                query=Search_templatesQuery.Meta.document, ward="rekuest_next"
            ),
        )

        DEFAULT_STRUCTURE_REGISTRY.register_as_structure(
            NodeFragment,
            "@rekuest_next/node",
            scope=PortScope.GLOBAL,
            aexpand=afind,
            ashrink=id_shrink,
            default_widget=SearchWidget(
                query=Search_nodesQuery.Meta.document, ward="rekuest_next"
            ),
        )

        DEFAULT_STRUCTURE_REGISTRY.register_as_structure(
            TestCaseFragment,
            "@rekuest_next/testcase",
            scope=PortScope.GLOBAL,
            aexpand=aget_testcase,
            ashrink=id_shrink,
            default_widget=SearchWidget(
                query=Search_testcasesQuery.Meta.document, ward="rekuest_next"
            ),
        )

        DEFAULT_STRUCTURE_REGISTRY.register_as_structure(
            TestResultFragment,
            "@rekuest_next/testresult",
            scope=PortScope.GLOBAL,
            aexpand=aget_testresult,
            ashrink=id_shrink,
            default_widget=SearchWidget(
                query=Search_testresultsQuery.Meta.document, ward="rekuest_next"
            ),
        )

    return DEFAULT_STRUCTURE_REGISTRY
