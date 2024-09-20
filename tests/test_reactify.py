from rekuest_next.actors.actify import reactify
from rekuest_next.definition.define import prepare_definition
from rekuest_next.api.schema import NodeKind


def test_actify_function(simple_registry):
    def func():
        """This function

        This function is a test function

        """

        return 1

    defi, actorBuilder = reactify(func, simple_registry)
    assert defi.kind == NodeKind.FUNCTION


def test_actify_generator(simple_registry):
    def gen():
        """This function

        This function is a test function

        """

        yield 1

    defi, actorBuilder = reactify(gen, simple_registry)
    assert defi.kind == NodeKind.GENERATOR
