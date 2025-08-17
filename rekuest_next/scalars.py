"""This module mirros exactly the scalars used in the  rekuest_next library."""

from graphql import (
    DocumentNode,
    FieldNode,
    parse,
    OperationDefinitionNode,
    OperationType,
    print_ast,
    print_source_location,
    GraphQLSyntaxError,
)
from typing import Callable, Dict, Any, Union

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
import re


ActionHash = str
InstanceID = str
QString = str

ValueMap = Dict[str, Any]

ValidatorFunctionCoercible = str
SearchQueryCoercible = str | DocumentNode

Args = Dict[str, Any]


class Interface(str):
    """An interface is a string that is used to identify a function on a
    extension"""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,  # noqa: ANN401
    ) -> CoreSchema:
        """Get the pydantic core schema for the interface"""
        return core_schema.no_info_after_validator_function(cls.validate, handler(str))

    @classmethod
    def validate(cls, v: Union[str, Callable[[Any], Any]]) -> str:
        """Validate the interface"""
        if not isinstance(v, str):
            if hasattr(v, "__name__"):
                return v.__name__
            else:
                raise ValueError("Interface must be either a str or function")
        return v

    pass


class Identifier(str):
    """An identifier is a string that is used to identify a structure
    uniquely. Structures are core data types that are used to define the
    interface of a function. They are used to define the input and output
    types of a function.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,  # noqa: ANN401
    ) -> CoreSchema:
        """Get the pydantic core schema for the identifier"""
        return core_schema.no_info_after_validator_function(cls.validate, handler(str))

    @classmethod
    def validate(cls, v: str) -> "Identifier":
        """Validate the identifier"""
        if "@" in v and "/" not in v:
            raise ValueError(
                "Identifier must contain follow '@package/module' when trying to mimic a global module "
            )
        return Identifier(v)


class ValidatorFunction(str):
    """A validator function a string that represents a javascript function, That can handle
    some validation logic on the frontend"""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,  # noqa: ANN401
    ) -> CoreSchema:
        """Get the pydantic core schema for the validator function"""
        return core_schema.no_info_after_validator_function(cls.validate, handler(str))

    @classmethod
    def validate(cls, v: ValidatorFunctionCoercible) -> "ValidatorFunction":
        """Validate the validator function"""

        v = str(v).strip()
        if not v:
            raise ValueError("ValidatorFunction cannot be empty")

        if (not v.startswith("(")) or ("=>" not in v):
            raise ValueError(
                "ValidatorFunction must be an arrow function or block function"
            )

        args_match = re.match(r"\((.*?)\)", v)
        if args_match:
            args = [
                arg.strip() for arg in args_match.group(1).split(",") if arg.strip()
            ]

            if not args:
                raise ValueError("Function must have at least one argument")

        return cls(v)

    def retrieve_args(self) -> list[str]:
        """Retrieve the arguments of the validator function"""
        args_match = re.match(r"\((.*?)\)", self)
        if args_match:
            return [
                arg.strip() for arg in args_match.group(1).split(",") if arg.strip()
            ]
        return []


def parse_or_raise(v: str) -> DocumentNode:
    """Parse a string to a graphql DocumentAction. If it fails, raise a ValueError
    with the error message and the source location of the error.

    Args:
        v (str): The string to parse.
    Raises:
        ValueError: If the string cannot be parsed to a DocumentAction.
    """
    try:
        return parse(v)
    except GraphQLSyntaxError as e:
        x = repr(e)
        x += "\n" + v + "\n"
        if e.locations:
            for loc in e.locations:
                if e.source:
                    x += "\n" + print_source_location(e.source, loc)
        raise ValueError("Could not parse to graphql: \n" + x) from e


class SearchQuery(str):
    """A search query is a string that represents a graphql query that can be used
    to search for a specific value in a list of values. The query must be a valid
    graphql query and must contain the following elements:

    - A single operation definition
    - A single selection set
    - A single field with the name 'options'
    - A variable "$search" of type String
    - A variable "$values" of type [ID]



    Optionally the query can also contain the following elements:

    - Multiple variables of arribtary type that will be validated against
    the dependencies of the widget.
    """

    def __get__(self, instance, owner) -> "SearchQuery": ...  # type: ignore  # noqa: ANN001, ANN401, D105

    def __set__(self, instance, value: "SearchQueryCoercible") -> None: ...  # type: ignore  # noqa: ANN001, ANN401, D105

    @classmethod
    def __get_pydantic_core_schema__(  # noqa: D105
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,  # noqa: ANN401
    ) -> CoreSchema:
        """Get the pydantic core schema for the search query"""
        return core_schema.no_info_after_validator_function(cls.validate, handler(str))

    @classmethod
    def validate(cls, v: SearchQueryCoercible) -> "SearchQuery":
        """Validate the search query"""
        if not isinstance(v, str) and not isinstance(v, DocumentNode):  # type: ignore
            raise ValueError(
                "Search query must be either a str or a graphql DocumentAction"
            )
        if isinstance(v, str):
            v = parse_or_raise(v)

        if not v.definitions or len(v.definitions) > 1:
            raise ValueError("Only one definintion allowed")

        if len(v.definitions) == 0:
            raise ValueError("No definition found")

        definition = v.definitions[0]
        if not definition:
            raise ValueError("Specify an operation")

        if not isinstance(definition, OperationDefinitionNode):
            raise ValueError("Needs an operation")

        if not definition.operation == OperationType.QUERY:
            raise ValueError("Needs to be operation")

        if len(definition.variable_definitions) < 2:
            raise ValueError(
                f"At least two arguments should be provided ($search: String, $values: [ID])): Was given: {print_ast(v)}"
            )

        if (
            definition.variable_definitions[0].variable.name.value != "search"
            or definition.variable_definitions[0].type.kind != "named_type"
        ):
            raise ValueError(
                f"First parameter of search function should be '$search: String' if you provide arguments for your options. This parameter will be filled with userinput: Was given: {print_ast(v)}"
            )

        if (
            definition.variable_definitions[1].variable.name.value != "values"
            or definition.variable_definitions[0].type.kind != "named_type"
        ):
            raise ValueError(
                f"Seconrd parameter of search function should be '$values: [ID]' if you provide arguments for your options. This parameter will be filled with the default values: Was given: {print_ast(v)}"
            )

        wrapped_query = definition.selection_set.selections[0]

        if not isinstance(wrapped_query, FieldNode):
            raise ValueError(
                f"Wrapped query should be a field node: Was given: {print_ast(v)}"
            )

        options_value = (
            wrapped_query.alias.value
            if wrapped_query.alias
            else wrapped_query.name.value
        )
        if options_value != "options":
            raise ValueError(
                f"First element of query should be 'options':  Was given: {print_ast(v)}"
            )

        if not wrapped_query.selection_set:
            raise ValueError(
                f"Wrapped query should contain a selection set: Was given: {print_ast(v)}"
            )

        wrapped_selection = wrapped_query.selection_set.selections

        aliases = [
            field.alias.value if field.alias else field.name.value
            for field in wrapped_selection
            if isinstance(field, FieldNode)
        ]
        if "value" not in aliases:
            raise ValueError(
                "Searched query needs to contain a 'value' not that corresponds to the selected value"
            )
        if "label" not in aliases:
            raise ValueError(
                "Searched query needs to contain a 'label' that corresponds to the displayed value to the user"
            )

        return SearchQuery(print_ast(v))
