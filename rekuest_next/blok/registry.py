"""Turn registered blok declarations into the inputs the agent uploads."""

from typing import (
    TYPE_CHECKING,
    Any,
)
from collections.abc import Iterable, Sequence

from rekuest_next.api.schema import (
    ActionDependencyInput,
    AgentProbeInput,
    AgentDependencyInput,
    BlokImplementationInput,
    ComponentNodeInput,
    PortKind,
    ReturnPortInput,
    StateDependencyInput,
    UtilProbeInput,
)
from rekuest_next.blok.walk import BlokVisitor, action_key_for, walk_component
from rekuest_next.definition.dependencies import (
    build_action_dependency_input,
    build_state_dependency_input,
)

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry


def build_declared_bloks(
    app_registry: "AppRegistry",
) -> dict[str, BlokImplementationInput]:
    """Generate blok inputs from their declarations against an app registry."""
    declared_bloks: dict[str, BlokImplementationInput] = {}

    for blok_key, declaration in app_registry.registered_bloks.items():
        dependencies = _build_dependencies_for_component(
            declaration.component,
            app_registry,
            declaration.dependencies or (),
        )

        demo_state = declaration.demo_state
        if demo_state is None:
            demo_state = _autogenerate_demo_state(dependencies, app_registry)

        declared_bloks[blok_key] = BlokImplementationInput(
            key=blok_key,
            dependencies=tuple(dependencies),
            components=(declaration.component,),
            description=declaration.description,
            demo_state=demo_state,
        )

    return declared_bloks


class _ReferenceCollector(BlokVisitor):
    """Collects the dependency keys, actions and states a blok tree references."""

    def __init__(self, aliases: dict[str, str]) -> None:
        self.aliases = aliases
        self.actions: dict[str, set[str]] = {}
        self.states: dict[str, set[str]] = {}
        # A ``state.<key>`` reference that names no dependency; resolvable only
        # when the blok has exactly one dependency to attribute it to.
        self.implicit_states: set[str] = set()

    def canonical(self, key: str) -> str:
        return self.aliases.get(key, key)

    @property
    def dependency_keys(self) -> set[str]:
        return set(self.actions) | set(self.states)

    def visit_path(self, path: str, scope: dict[str, Any], context: str) -> None:
        path_parts = path.split(".")
        if not path_parts or path_parts[0] in scope:
            return

        root = path_parts[0]
        if root == "utils":
            return

        if root == "state":
            if len(path_parts) >= 3:
                self.states.setdefault(self.canonical(path_parts[1]), set()).add(
                    path_parts[2]
                )
            elif len(path_parts) >= 2:
                self.implicit_states.add(path_parts[1])
            return

        if len(path_parts) >= 2:
            self.states.setdefault(self.canonical(root), set()).add(path_parts[1])

    def visit_agent_call(
        self, call: AgentProbeInput, scope: dict[str, Any], context: str
    ) -> None:
        self.actions.setdefault(self.canonical(call.dependency), set()).add(
            action_key_for(call)
        )

    def visit_util_call(
        self, call: UtilProbeInput, scope: dict[str, Any], context: str
    ) -> None:
        return None

    def declare_foreach_local(
        self, name: str, items_path: str, scope: dict[str, Any], context: str
    ) -> None:
        # The item's schema is only knowable once dependencies exist, which is
        # what this pass is building. Declaring the name is enough here.
        self.visit_path(items_path, scope, context)
        return None


def _build_dependencies_for_component(
    component: ComponentNodeInput,
    app_registry: "AppRegistry",
    explicit_dependencies: Sequence[AgentDependencyInput],
) -> list[AgentDependencyInput]:
    """Resolve a blok's dependencies, preferring explicitly declared ones.

    Dependencies referenced by the tree but not declared explicitly are inferred
    from the agent's *own* implementations and states. A dependency satisfied by
    another app cannot be inferred that way -- pass it in via
    ``register_blok(dependencies=[...])``, typically from a declared protocol's
    ``to_dependency()``.
    """
    explicit_by_key = {
        dependency.key: dependency for dependency in explicit_dependencies
    }
    aliases = {
        dependency.app: dependency.key
        for dependency in explicit_dependencies
        if dependency.app is not None
    }

    collector = _ReferenceCollector(aliases)
    walk_component(component, collector)

    dependency_keys = collector.dependency_keys | set(explicit_by_key)

    if collector.implicit_states:
        if len(dependency_keys) != 1:
            raise ValueError(
                "Cannot resolve unscoped state references in blok without exactly one "
                f"explicit dependency key. Found dependencies: {sorted(dependency_keys)}"
            )

        dependency_key = next(iter(dependency_keys))
        collector.states.setdefault(dependency_key, set()).update(
            collector.implicit_states
        )

    dependencies: list[AgentDependencyInput] = []

    for dependency_key in sorted(dependency_keys):
        explicit = explicit_by_key.get(dependency_key)
        if explicit is not None:
            # The declared dependency already carries its own demands, resolved
            # against the protocol rather than this agent's implementations.
            dependencies.append(explicit)
            continue

        action_demands = tuple(
            _create_action_dependency(action_key, app_registry)
            for action_key in sorted(collector.actions.get(dependency_key, set()))
        )
        state_demands = tuple(
            _create_state_dependency(state_key, app_registry)
            for state_key in sorted(collector.states.get(dependency_key, set()))
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


def _create_action_dependency(
    action_key: str,
    app_registry: "AppRegistry",
) -> ActionDependencyInput:
    implementation = app_registry.implementations.get(action_key)
    if implementation is None:
        raise ValueError(
            f"Blok references unknown action '{action_key}'. It is not implemented "
            f"by this agent -- if another app provides it, declare the dependency "
            f"explicitly via register_blok(dependencies=[...])."
        )

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
        raise ValueError(
            f"Blok references unknown state '{state_key}'. It is not provided "
            f"by this agent -- if another app provides it, declare the dependency "
            f"explicitly via register_blok(dependencies=[...])."
        )

    return build_state_dependency_input(
        key=state_key,
        state_key=state_key,
        definition=state_implementation.definition,
    )


def _autogenerate_demo_state(
    dependencies: Iterable[AgentDependencyInput],
    app_registry: "AppRegistry",
) -> dict[str, Any]:
    """Synthesize a placeholder value for every state the blok reads.

    Values come from the state's declared *ports*, not from instantiating the
    state class: a state with required fields cannot be constructed with no
    arguments, and its ports already describe the shape the renderer needs.

    A dependency whose states have no local definition (one satisfied by another
    app) is omitted entirely -- a partial entry would fail the demo_state
    completeness check on ``BlokImplementationInput``.
    """
    demo_state: dict[str, Any] = {}

    for dependency in dependencies:
        dependency_demo_state: dict[str, Any] = {}
        complete = True

        for state_demand in dependency.state_dependencies or ():
            state_implementation = app_registry.states.get(state_demand.key)
            if state_implementation is None:
                complete = False
                break

            dependency_demo_state[state_demand.key] = {
                port.key: _demo_value_for_port(port)
                for port in state_implementation.definition.ports or ()
            }

        if complete and dependency_demo_state:
            demo_state[dependency.key] = dependency_demo_state

    return demo_state


_DEMO_SCALARS: dict[PortKind, Any] = {
    PortKind.STRING: "",
    PortKind.INT: 0,
    PortKind.FLOAT: 0.0,
    PortKind.QUANTITY: 0.0,
    PortKind.BOOL: False,
    PortKind.LIST: [],
    PortKind.DICT: {},
}


def _demo_value_for_port(port: ReturnPortInput) -> Any:
    """A placeholder value matching a port's declared shape."""
    if port.default is not None:
        return port.default

    if port.nullable:
        return None

    if port.kind == PortKind.ENUM:
        first_choice = next(iter(port.choices or ()), None)
        return first_choice.value if first_choice is not None else ""

    if port.kind in (PortKind.MODEL, PortKind.INTERFACE):
        return {child.key: _demo_value_for_port(child) for child in port.children or ()}

    return _DEMO_SCALARS.get(port.kind)
