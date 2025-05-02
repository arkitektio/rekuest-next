from rekuest_next.actors.types import Shelver
from rekuest_next.api.schema import DefinitionInput, PortKind
import pytest
from .structures import SecondSerializableObject, SerializableObject
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry, PortScope
from .funcs import (
    plain_basic_function,
    plain_structure_function,
    union_structure_function,
    nested_basic_function,
    nested_structure_function,
    annotated_basic_function,
    annotated_nested_structure_function,
    null_function,
    nested_model_with_annotations,
)
from rekuest_next.definition.validate import auto_validate
from rekuest_next.structures.serialization.postman import ashrink_args


@pytest.fixture
def simple_registry():
    reg = StructureRegistry()
    reg.register_as_structure(SerializableObject, "SerializableObject", scope=PortScope.LOCAL)
    reg.register_as_structure(
        SecondSerializableObject, "SecondSerializableObject", scope=PortScope.LOCAL
    )

    return reg


@pytest.mark.define
def assert_definition_hash(simple_registry):
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)
    function_two_definition = prepare_definition(null_function, structure_registry=simple_registry)

    assert hash(functional_definition) == hash(function_two_definition)

    x = {}
    x[functional_definition] = "test"

    assert x[function_two_definition] == "test"


@pytest.mark.define
def test_define_null(simple_registry):
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Karl", "Doesnt conform to standard Naming Scheme"
    assert functional_definition.args[0].nullable, "Should be nullable"


@pytest.mark.define
def test_define_basic(simple_registry):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Karl", "Doesnt conform to standard Naming Scheme"


@pytest.mark.define
def test_define_structure(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Karl", "Doesnt conform to standard Naming Scheme"
    assert functional_definition.args[0].identifier == "SerializableObject"


@pytest.mark.define
def test_nested_model_with_annotations(simple_registry):
    functional_definition = prepare_definition(
        nested_model_with_annotations, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"

    assert functional_definition.args[0].kind == PortKind.LIST

    assert functional_definition.args[0].children[0].kind == PortKind.MODEL

    model_port = functional_definition.args[0].children[0]

    intport = model_port.children[0]
    assert intport.kind == PortKind.INT
    assert intport.validators is not None, "Validators should not be None"
    assert intport.validators[0].function == "(x) => x > 3"


@pytest.mark.define
def test_define_union_structure(simple_registry):
    functional_definition = prepare_definition(
        union_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Karl", "Doesnt conform to standard Naming Scheme"
    assert functional_definition.args[0].kind == PortKind.UNION

    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE

    assert functional_definition.returns[0].kind == PortKind.UNION


@pytest.mark.define
def test_define_nested_basic_function(simple_registry):
    functional_definition = prepare_definition(
        nested_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Structure Karl", (
        "Doesnt conform to standard Naming Scheme"
    )
    assert len(functional_definition.args) == 3, "Wrong amount of Arguments"
    assert functional_definition.args[0].kind == PortKind.LIST, "Wasn't defined as a List"
    assert functional_definition.args[1].kind == PortKind.DICT, "Wasn't defined as a Dict"
    assert functional_definition.args[1].children[0].kind == PortKind.INT, (
        "Child of List is not of type IntArgPort"
    )
    assert functional_definition.args[0].children[0].kind == PortKind.STRING, (
        "Child of Dict is not of type StringArgPort"
    )
    assert functional_definition.args[2].kind == PortKind.STRING, (
        "Kwarg wasn't defined as a StringKwargPort"
    )
    assert len(functional_definition.returns) == 2, "Wrong amount of Returns"
    assert functional_definition.returns[0].kind == PortKind.LIST, "Needs to Return List"


@pytest.mark.define
def test_define_nested_structure_function(simple_registry):
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Structured Karl", (
        "Doesnt conform to standard Naming Scheme"
    )
    assert len(functional_definition.args) == 2, "Wrong amount of Arguments"
    assert functional_definition.args[0].kind == PortKind.LIST, "Wasn't defined as a List"
    assert functional_definition.args[1].kind == PortKind.DICT, "Wasn't defined as a Dict"
    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE, (
        "Child of List is not of type IntArgPort"
    )
    assert functional_definition.args[0].children[0].identifier == "SerializableObject", (
        "Child of List is not of type IntArgPort"
    )
    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE, (
        "Child of Dict is not of type StringArgPort"
    )
    assert len(functional_definition.returns) == 2, "Wrong amount of Returns"
    assert functional_definition.returns[0].kind == PortKind.STRING
    assert functional_definition.returns[1].kind == PortKind.DICT
    assert functional_definition.returns[1].children[0].kind == PortKind.STRUCTURE
    assert functional_definition.returns[1].children[0].identifier == "SecondSerializableObject"


@pytest.mark.define
def test_define_annotated_basic_function(simple_registry):
    functional_definition = prepare_definition(
        annotated_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "Node is not Node"
    assert functional_definition.name == "Annotated Karl", (
        "Doesnt conform to standard Naming Scheme"
    )


@pytest.mark.define
def test_define_annotated_nested_function(simple_registry):
    functional_definition = prepare_definition(
        annotated_nested_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "Node is not Node"
    assert functional_definition.name == "Annotated Karl", (
        "Doesnt conform to standard Naming Scheme"
    )


@pytest.fixture
def arkitekt_rath():
    return MockRequestRath()


@pytest.mark.define
@pytest.mark.asyncio
async def test_shrinking(simple_registry: StructureRegistry, mock_shelver: Shelver):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await ashrink_args(
        definition, ("hallo", "zz"), {}, structure_registry=simple_registry, shelver=mock_shelver
    )
    assert args == {"name": "zz", "rep": "hallo"}
