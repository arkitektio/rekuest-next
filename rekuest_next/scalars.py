from graphql import (
    DocumentNode,
    parse,
    OperationDefinitionNode,
    OperationType,
    print_ast,
    print_source_location,
    GraphQLError,
)
from typing import Dict, Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
import re


NodeHash = str
InstanceId = str
QString = str

ValueMap = Dict[str, Any]


Args = Dict[str, Any]


class Interface(str):
    
    @classmethod
    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            self.validate, handler(str)
        )
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            if hasattr(v, "__name__"):
                return v.__name__
            else:
                raise ValueError("Interface must be either a str or function")
        return v

    pass


class Identifier(str):

    @classmethod
    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            self.validate, handler(str)
        )
    

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("Identifier must be a string")
        if "@" in v and "/" not in v:
            raise ValueError(
                "Identifier must contain follow '@package/module' when trying to mimic"
                " a global module "
            )
        return v

    def __repr__(self):
        return f"Identifier({repr(self)})"


class ValidatorFunction(str):

    @classmethod
    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            self.validate, handler(str)
        )

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("ValidatorFunction must be a string")
        
        if not (v.startswith("(") or ("=>" not in v)):
            raise ValueError("ValidatorFunction must be an arrow function or block function")
        
        args_match = re.match(r'\((.*?)\)', v)
        if args_match:
            args = [arg.strip() for arg in args_match.group(1).split(',') if arg.strip()]
            if not args:
                raise ValueError("Function must have at least one argument")

        return v
    
    
    def retrieve_args(self):
        args_match = re.match(r'\((.*?)\)', self)
        if args_match:
            return [arg.strip() for arg in args_match.group(1).split(',') if arg.strip()]
        return []

    def __repr__(self):
        return f"ValidatorFunction({repr(self)})"


def parse_or_raise(v: str):
    try:
        return parse(v)
    except GraphQLError as e:
        x = repr(e)
        x += "\n" + v + "\n"
        for l in e.locations:
            x += "\n" + print_source_location(e.source, l)
        raise ValueError("Could not parse to graphql: \n" + x)


class SearchQuery(str):
    
    @classmethod
    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            self.validate, handler(str)
        )

    @classmethod
    def validate(cls, v, *info):
        if not isinstance(v, str) and not isinstance(v, DocumentNode):
            raise TypeError(
                "Search query must be either a str or a graphql DocumentNode"
            )
        if isinstance(v, str):
            v = parse_or_raise(v)

        if not v.definitions or len(v.definitions) > 1:
            raise ValueError("Only one definintion allowed")

        if not isinstance(v.definitions[0], OperationDefinitionNode):
            raise ValueError("Needs an operation")

        definition = v.definitions[0]
        if not definition:
            raise ValueError("Specify an operation")

        if not definition.operation == OperationType.QUERY:
            raise ValueError("Needs to be operation")

        assert len(definition.variable_definitions) >= 2, (
            "At least two arguments should be provided ($search: String, $values:"
            f" [ID])): Was given: {print_ast(v)}"
        )

        if (
            definition.variable_definitions[0].variable.name.value != "search"
            or definition.variable_definitions[0].type.kind != "named_type"
        ):
            raise ValueError(
                "First parameter of search function should be '$search: String' if you"
                " provide arguments for your options. This parameter will be filled"
                f" with userinput: Was given: {print_ast(v)}"
            )

        if (
            definition.variable_definitions[1].variable.name.value != "values"
            or definition.variable_definitions[0].type.kind != "named_type"
        ):
            raise ValueError(
                "Seconrd parameter of search function should be '$values: [ID]' if you"
                " provide arguments for your options. This parameter will be filled"
                f" with the default values: Was given: {print_ast(v)}"
            )

        wrapped_query = definition.selection_set.selections[0]

        options_value = (
            wrapped_query.alias.value
            if wrapped_query.alias
            else wrapped_query.name.value
        )
        if options_value != "options":
            raise ValueError(
                "First element of query should be 'options':  Was given:"
                f" {print_ast(v)}"
            )

        wrapped_selection = wrapped_query.selection_set.selections
        aliases = [
            field.alias.value if field.alias else field.name.value
            for field in wrapped_selection
        ]
        if "value" not in aliases:
            raise ValueError(
                "Searched query needs to contain a 'value' not that corresponds to the"
                " selected value"
            )
        if "label" not in aliases:
            raise ValueError(
                "Searched query needs to contain a 'label' that corresponds to the"
                " displayed value to the user"
            )

        return print_ast(v)

    def __repr__(self):
        return f"SearchQuery({repr(self)})"
