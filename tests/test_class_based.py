"""Test the reactify function which converts a function or generator into an actor definition."""

from dataclasses import dataclass


from rekuest_next.agents.extensions.default import DefaultExtension
from rekuest_next.agents.hooks.startup import ThreadedStartupHook
from rekuest_next.agents.hooks.background import WrappedThreadedBackgroundTask
from rekuest_next.rekuest import RekuestNext
from rekuest_next.state.decorator import state


def test_actify_class_based_function(mock_rekuest: RekuestNext) -> None:
    """Test if the function is correctly buildable into an actor definition."""

    class ClassBase:
        def __init__(self, rekuest: RekuestNext) -> None:
            """Initialize the class."""
            self.rekuest = mock_rekuest
            self.rekuest.register(self.basic_function)

        def basic_function(self, x: int) -> int:
            """A basic function that returns the input multiplied by 2."""
            return x * 2

    class_instance = ClassBase(mock_rekuest)

    assert class_instance.basic_function(5) == 10
    default = mock_rekuest.agent.extension_registry.get("default")
    assert default is not None
    assert isinstance(default, DefaultExtension)

    assert "basic_function" in default.definition_registry.implementations
    implementation = default.definition_registry.implementations["basic_function"]

    assert len(implementation.definition.args) == 1


def test_actify_class_based_startup(mock_rekuest: RekuestNext) -> None:
    """Test if the function is correctly buildable into an actor definition."""

    @state
    @dataclass
    class DefaultState:
        """A default state for the class."""

        instance_id: str = ""

    class ClassBase:
        def __init__(self, rekuest: RekuestNext) -> None:
            """Initialize the class."""
            self.rekuest = mock_rekuest
            self.rekuest.register_startup(self.basic_startup)

        def basic_startup(self, instance_id: str) -> DefaultState:
            """A basic function that returns the input multiplied by 2."""
            return DefaultState(instance_id=instance_id)

    class_instance = ClassBase(mock_rekuest)

    default = mock_rekuest.agent.hook_registry.startup_hooks.get("basic_startup")
    assert default is not None
    assert isinstance(default, ThreadedStartupHook)


def test_actify_class_based_startup(mock_rekuest: RekuestNext) -> None:
    """Test if the function is correctly buildable into an actor definition."""

    @state
    @dataclass
    class DefaultState:
        """A default state for the class."""

        instance_id: str = ""

    class ClassBase:
        def __init__(self, rekuest: RekuestNext) -> None:
            """Initialize the class."""
            self.rekuest = mock_rekuest
            self.rekuest.register_background(self.basic_background)

        def basic_background(self, state: DefaultState) -> None:
            """A basic function that returns the input multiplied by 2."""
            while True:
                # Simulate some background work
                pass

    ClassBase(mock_rekuest)

    default = mock_rekuest.agent.hook_registry.background_worker.get("basic_background")
    assert default is not None
    assert isinstance(default, WrappedThreadedBackgroundTask)
