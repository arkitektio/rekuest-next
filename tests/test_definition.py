"""General Tests for defininin actions"""

from rekuest_next.api.schema import DefinitionInput, PortKind
import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
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


@pytest.mark.define
def assert_definition_hash(simple_registry: StructureRegistry) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)
    function_two_definition = prepare_definition(null_function, structure_registry=simple_registry)

    assert hash(functional_definition) == hash(function_two_definition), "Hashes are not equal"


@pytest.mark.define
def test_if_usable_as_hash(simple_registry: StructureRegistry) -> None:
    """Test if the function is usable as a hash."""
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)
    x = {}
    x[functional_definition] = "test"


@pytest.mark.define
def test_define_null(simple_registry: StructureRegistry) -> None:
    """Test if the function is correctly registered in the registry."""
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Null Function", (
        "Name should be inferred from the function name, not the docstring title"
    )
    assert functional_definition.description is not None
    assert functional_definition.description.startswith("Karl"), (
        "Description should be taken from the docstring"
    )
    assert functional_definition.args[0].nullable, "Should be nullable"


@pytest.mark.define
def test_define_basic(simple_registry: StructureRegistry) -> None:
    """Test if a basic function is correctly registered in the registry."""
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Plain Basic Function", (
        "Name should be inferred from the function name, not the docstring title"
    )


@pytest.mark.define
def test_define_structure(simple_registry: StructureRegistry) -> None:
    """Test if a structure function is correctly registered in the registry."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Plain Structure Function", (
        "Name should be inferred from the function name, not the docstring title"
    )
    assert functional_definition.args[0].identifier == "mock/serializable"


@pytest.mark.define
def test_nested_model_with_annotations(simple_registry: StructureRegistry) -> None:
    """Test if a structure function is correctly registered in the registry."""
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
def test_define_union_structure(simple_registry: StructureRegistry) -> None:
    """Test if a structure function is correctly registered in the registry."""
    functional_definition = prepare_definition(
        union_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Union Structure Function", (
        "Name should be inferred from the function name, not the docstring title"
    )
    assert functional_definition.args[0].kind == PortKind.UNION

    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE

    assert functional_definition.returns[0].kind == PortKind.UNION


@pytest.mark.define
def test_define_nested_basic_function(simple_registry: StructureRegistry) -> None:
    """Test if a nested basic function is correctly registered in the registry."""
    functional_definition = prepare_definition(
        nested_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Nested Basic Function", (
        "Name should be inferred from the function name, not the docstring title"
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
def test_define_nested_structure_function(simple_registry: StructureRegistry) -> None:
    """Test if a nested function with structures is correctly registered in the registry."""
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "output is not a definition"
    assert functional_definition.name == "Nested Structure Function", (
        "Name should be inferred from the function name, not the docstring title"
    )
    assert len(functional_definition.args) == 2, "Wrong amount of Arguments"
    assert functional_definition.args[0].kind == PortKind.LIST, "Wasn't defined as a List"
    assert functional_definition.args[1].kind == PortKind.DICT, "Wasn't defined as a Dict"
    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE, (
        "Child of List is not of type IntArgPort"
    )
    assert functional_definition.args[0].children[0].identifier == "mock/serializable", (
        "Child of List is not of type IntArgPort"
    )
    assert functional_definition.args[0].children[0].kind == PortKind.STRUCTURE, (
        "Child of Dict is not of type StringArgPort"
    )
    assert len(functional_definition.returns) == 2, "Wrong amount of Returns"
    assert functional_definition.returns[0].kind == PortKind.STRING
    assert functional_definition.returns[1].kind == PortKind.DICT
    assert functional_definition.returns[1].children[0].kind == PortKind.STRUCTURE
    assert functional_definition.returns[1].children[0].identifier == "mock/secondserializable"


@pytest.mark.define
def test_define_annotated_basic_function(simple_registry: StructureRegistry) -> None:
    """Test if a basic annotated function is correctly registered in the registry."""
    functional_definition = prepare_definition(
        annotated_basic_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "Node is not Node"
    assert functional_definition.name == "Annotated Basic Function", (
        "Name should be inferred from the function name, not the docstring title"
    )


@pytest.mark.define
def test_define_annotated_nested_function(simple_registry: StructureRegistry) -> None:
    """Test if a annotated and nested function correctly registered in the registry."""
    functional_definition = prepare_definition(
        annotated_nested_structure_function, structure_registry=simple_registry
    )
    assert isinstance(functional_definition, DefinitionInput), "Node is not Node"
    assert functional_definition.name == "Annotated Nested Structure Function", (
        "Name should be inferred from the function name, not the docstring title"
    )


@pytest.mark.define
def test_name_never_inferred_from_docstring(simple_registry: StructureRegistry) -> None:
    """The registered name must come from the function name, never the docstring."""

    def my_misleading_action(x: int) -> int:
        """A Very Fancy Title People Misuse As A Name

        But this paragraph is the actual description of the action.
        """
        return x

    functional_definition = prepare_definition(
        my_misleading_action, structure_registry=simple_registry
    )
    assert functional_definition.name == "My Misleading Action", (
        "Name must be derived from the function name, not the docstring summary"
    )
    assert functional_definition.description is not None
    assert "A Very Fancy Title" in functional_definition.description, (
        "The docstring summary should land in the description instead"
    )
    assert "actual description" in functional_definition.description


@pytest.mark.define
def test_explicit_name_takes_precedence(simple_registry: StructureRegistry) -> None:
    """An explicit ``name`` argument still overrides the function name."""

    def some_action(x: int) -> int:
        """A summary line."""
        return x

    functional_definition = prepare_definition(
        some_action, structure_registry=simple_registry, name="Custom Name"
    )
    assert functional_definition.name == "Custom Name"


@pytest.mark.define
def test_google_style_docstring_description(simple_registry: StructureRegistry) -> None:
    """Google-style docstrings should still yield a usable description."""

    def google_action(x: int) -> int:
        """Summarize a thing.

        A longer explanation of what this does.

        Args:
            x (int): the input value
        """
        return x

    functional_definition = prepare_definition(
        google_action, structure_registry=simple_registry
    )
    assert functional_definition.name == "Google Action"
    assert functional_definition.description is not None
    assert functional_definition.description.startswith("Summarize a thing.")
    assert "longer explanation" in functional_definition.description
