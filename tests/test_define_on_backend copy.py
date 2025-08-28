"""General Tests for defininin actions"""

import time
from rekuest_next.api.schema import (
    acreate_implementation,
    create_implementation,
    ImplementationInput,
)
import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from .funcs import (
    nested_basic_function,
)
from .annotated_funcs import annotated_x, annotated_choice_x
from .conftest import DeployedRekuest


@pytest.mark.integration
def test_create_implementations(
    simple_registry: StructureRegistry, deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""
    functional_definition = prepare_definition(
        nested_basic_function, structure_registry=simple_registry
    )

    # Create the implementation
    x = create_implementation(
        implementation=ImplementationInput(
            definition=functional_definition,
            interface="null_function",
            dependencies=tuple(),
            dynamic=False,
        ),
        instance_id=deployed_app.instance_id,
        extension="default",
    )

    assert x.interface == "null_function", "Interface is not set correctly"


@pytest.mark.integration
def test_create_implementations_with_annotations(
    simple_registry: StructureRegistry, deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    functional_definition = prepare_definition(annotated_x, structure_registry=simple_registry)

    # Create the implementation
    x = create_implementation(
        implementation=ImplementationInput(
            definition=functional_definition,
            interface="annotated_x",
            dependencies=tuple(),
            dynamic=False,
        ),
        instance_id=deployed_app.instance_id,
        extension="default",
    )

    assert x.interface == "annotated_x", "Interface is not set correctly"


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def asyncio_definition(
    simple_registry: StructureRegistry, async_deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""

    functional_definition = prepare_definition(annotated_x, structure_registry=simple_registry)

    # Create the implementation
    x = await acreate_implementation(
        implementation=ImplementationInput(
            definition=functional_definition,
            interface="annotated_x",
            dependencies=tuple(),
            dynamic=False,
        ),
        instance_id=async_deployed_app.instance_id,
        extension="default",
    )
    assert x.interface == "annotated_x", "Interface is not set correctly"
