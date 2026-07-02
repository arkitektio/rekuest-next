"""Hooks for the agent"""

from dataclasses import fields, is_dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Set,
)

from rekuest_next.api.schema import (
    ActionArgumentInput,
    ActionDependencyInput,
    AgentCallInput,
    AgentDependencyInput,
    BlokImplementationInput,
    ComponentNodeInput,
    ComponentPropInput,
    StateDependencyInput,
    UtilCallInput,
)
from rekuest_next.definition.dependencies import (
    build_action_dependency_input,
    build_state_dependency_input,
)

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry


def build_declared_bloks(
    app_registry: "AppRegistry",
) -> Dict[str, BlokImplementationInput]:
    """Generate blok inputs from their declarations against an app registry."""
    declared_bloks: Dict[str, BlokImplementationInput] = {}

    for blok_key, component in app_registry.registered_bloks.items():
        dependencies = _build_dependencies_for_component(component, app_registry)

        demo_state = app_registry.registered_blok_demo_states.get(blok_key)
        if demo_state is None:
            demo_state = _autogenerate_demo_state(dependencies, app_registry)

        declared_bloks[blok_key] = BlokImplementationInput(
            key=blok_key,
            dependencies=tuple(dependencies),
            components=(component,),
            description=app_registry.registered_blok_descriptions.get(blok_key),
            demo_state=demo_state,
        )

    return declared_bloks


def _build_dependencies_for_component(
    component: ComponentNodeInput,
    app_registry: "AppRegistry",
) -> list[AgentDependencyInput]:
    referenced_actions, referenced_states, implicit_states = (
        _collect_component_references(
            component,
            inherited_locals=set(),
        )
    )

    dependency_keys = set(referenced_actions) | set(referenced_states)

    if implicit_states:
        if len(dependency_keys) != 1:
            raise ValueError(
                "Cannot resolve unscoped state references in blok without exactly one "
                f"explicit dependency key. Found dependencies: {sorted(dependency_keys)}"
            )

        dependency_key = next(iter(dependency_keys))
        referenced_states.setdefault(dependency_key, set()).update(implicit_states)

    dependencies: list[AgentDependencyInput] = []

    for dependency_key in sorted(dependency_keys):
        action_demands = tuple(
            _create_action_dependency(action_key, app_registry)
            for action_key in sorted(referenced_actions.get(dependency_key, set()))
        )
        state_demands = tuple(
            _create_state_dependency(state_key, app_registry)
            for state_key in sorted(referenced_states.get(dependency_key, set()))
        )

        dependencies.append(
            AgentDependencyInput(
                key=dependency_key,
                app=None,
                optional=False,
                auto_resolvable=False,
                action_dependencies=action_demands or None,
                state_dependencies=state_demands or None,
            )
        )

    return dependencies


def _collect_component_references(
    node: ComponentNodeInput,
    inherited_locals: Set[str],
) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str]]:
    available_locals = set(inherited_locals)
    referenced_actions: dict[str, set[str]] = {}
    referenced_states: dict[str, set[str]] = {}
    implicit_states: set[str] = set()

    for prop in node.props or ():
        if prop.declares_value:
            available_locals.add(prop.declares_value)

    for prop in node.props or ():
        _collect_prop_references(
            prop,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )

    for child in node.children or ():
        child_actions, child_states, child_implicit_states = (
            _collect_component_references(
                child,
                available_locals,
            )
        )
        _merge_reference_maps(referenced_actions, child_actions)
        _merge_reference_maps(referenced_states, child_states)
        implicit_states.update(child_implicit_states)

    return referenced_actions, referenced_states, implicit_states


def _collect_prop_references(
    prop: ComponentPropInput,
    available_locals: Set[str],
    referenced_actions: dict[str, set[str]],
    referenced_states: dict[str, set[str]],
    implicit_states: set[str],
) -> None:
    if prop.dynamic_value is not None and prop.dynamic_value.path is not None:
        _collect_path_reference(
            prop.dynamic_value.path,
            available_locals,
            referenced_states,
            implicit_states,
        )

    if prop.agent_call is not None:
        _collect_agent_call_references(
            prop.agent_call,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )

    if prop.util_call is not None:
        _collect_util_call_references(
            prop.util_call,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )


def _collect_agent_call_references(
    agent_call: AgentCallInput,
    available_locals: Set[str],
    referenced_actions: dict[str, set[str]],
    referenced_states: dict[str, set[str]],
    implicit_states: set[str],
) -> None:
    referenced_actions.setdefault(agent_call.dependency, set()).add(
        agent_call.operation.split(".")[-1]
    )

    for argument in agent_call.arguments or ():
        _collect_argument_references(
            argument,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )


def _collect_util_call_references(
    util_call: UtilCallInput,
    available_locals: Set[str],
    referenced_actions: dict[str, set[str]],
    referenced_states: dict[str, set[str]],
    implicit_states: set[str],
) -> None:
    for argument in util_call.arguments or ():
        _collect_argument_references(
            argument,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )


def _collect_argument_references(
    argument: ActionArgumentInput,
    available_locals: Set[str],
    referenced_actions: dict[str, set[str]],
    referenced_states: dict[str, set[str]],
    implicit_states: set[str],
) -> None:
    if argument.value_path is not None:
        _collect_path_reference(
            argument.value_path,
            available_locals,
            referenced_states,
            implicit_states,
        )

    if argument.agent_call is not None:
        _collect_agent_call_references(
            argument.agent_call,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )

    if argument.util_call is not None:
        _collect_util_call_references(
            argument.util_call,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )

    for nested_argument in argument.value_list or ():
        _collect_argument_references(
            nested_argument,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )

    for nested_argument in argument.value_dict or ():
        _collect_argument_references(
            nested_argument,
            available_locals,
            referenced_actions,
            referenced_states,
            implicit_states,
        )


def _collect_path_reference(
    path: str,
    available_locals: Set[str],
    referenced_states: dict[str, set[str]],
    implicit_states: set[str],
) -> None:
    path_parts = path.split(".")
    if not path_parts or path_parts[0] in available_locals:
        return

    root = path_parts[0]
    if root == "utils":
        return

    if root == "state":
        if len(path_parts) >= 3:
            referenced_states.setdefault(path_parts[1], set()).add(path_parts[2])
        elif len(path_parts) >= 2:
            implicit_states.add(path_parts[1])
        return

    if len(path_parts) >= 2:
        referenced_states.setdefault(root, set()).add(path_parts[1])


def _create_action_dependency(
    action_key: str,
    app_registry: "AppRegistry",
) -> ActionDependencyInput:
    implementation = app_registry.implementations.get(action_key)
    if implementation is None:
        raise ValueError(f"Blok references unknown action '{action_key}'")

    return build_action_dependency_input(
        key=action_key,
        definition=implementation.definition,
        action_key=action_key,
    )


def _create_state_dependency(
    state_key: str,
    app_registry: "AppRegistry",
) -> StateDependencyInput:
    state_implementation = app_registry.states.get(state_key)
    if state_implementation is None:
        raise ValueError(f"Blok references unknown state '{state_key}'")

    return build_state_dependency_input(
        key=state_key,
        state_key=state_key,
        definition=state_implementation.definition,
    )


def _merge_reference_maps(
    target: dict[str, set[str]],
    source: dict[str, set[str]],
) -> None:
    for dependency_key, referenced_keys in source.items():
        target.setdefault(dependency_key, set()).update(referenced_keys)


def _autogenerate_demo_state(
    dependencies: list[AgentDependencyInput],
    app_registry: "AppRegistry",
) -> Dict[str, Any]:
    demo_state: Dict[str, Any] = {}

    for dependency in dependencies:
        dependency_demo_state: Dict[str, Any] = {}

        for state_demand in dependency.state_dependencies or ():
            state_key = state_demand.key
            state_cls = app_registry.state_interface_classes.get(state_key)
            if state_cls is None:
                raise ValueError(
                    f"Cannot autogenerate demo_state for state '{state_key}': state class not registered"
                )

            try:
                state_instance = state_cls()
            except Exception as e:
                raise ValueError(
                    f"Cannot autogenerate demo_state for state '{state_key}': {e}"
                ) from e

            dependency_demo_state[state_key] = _serialize_state_instance(state_instance)

        if dependency_demo_state:
            demo_state[dependency.key] = dependency_demo_state

    return demo_state


def _serialize_state_instance(state_instance: Any) -> Any:
    if state_instance is None or isinstance(state_instance, (str, int, float, bool)):
        return state_instance

    if isinstance(state_instance, list):
        return [_serialize_state_instance(item) for item in state_instance]

    if isinstance(state_instance, tuple):
        return [_serialize_state_instance(item) for item in state_instance]

    if isinstance(state_instance, dict):
        return {
            str(key): _serialize_state_instance(value)
            for key, value in state_instance.items()
        }

    if hasattr(state_instance, "model_dump") and callable(state_instance.model_dump):
        return _serialize_state_instance(
            state_instance.model_dump(exclude_none=False, by_alias=True)
        )

    if is_dataclass(state_instance):
        return {
            field.name: _serialize_state_instance(getattr(state_instance, field.name))
            for field in fields(state_instance)
        }

    if hasattr(state_instance, "__dict__"):
        return {
            key: _serialize_state_instance(value)
            for key, value in vars(state_instance).items()
            if not key.startswith("_")
        }

    return state_instance
