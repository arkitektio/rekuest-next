"""Shared signature introspection for startup, shutdown and background hooks.

Every hook kind inspects the wrapped function for app-context, state and context
parameters the same way; they differ only in which of those the runtime can
actually inject at call time (see :attr:`WithVariables.injects_states`) and in
what they may return (see :meth:`WithVariables.validate_returns`).
"""

import inspect
from typing import Any, Dict

from rekuest_next.agents.context import prepare_context_variables
from rekuest_next.agents.errors import StateRequirementsNotMet
from rekuest_next.protocols import AnyFunction
from rekuest_next.state.utils import prepare_appcontext, prepare_state_variables


class WithVariables:
    """Base for wrapped hooks: resolves the function's injectable parameters.

    Subclasses set :attr:`hook_kind` (used in error messages) and, where the
    runtime cannot provide states/contexts at call time, ``injects_states``.
    """

    hook_kind: str = "Hook"
    #: Whether the runtime injects state and context variables when running the
    #: hook. Startup hooks run before any state exists, so only the app context
    #: can be injected there.
    injects_states: bool = True

    def __init__(self, func: AnyFunction) -> None:
        self.func = func
        self.state_variables, self.state_returns = prepare_state_variables(func)
        self.app_context_variables, self.app_context_returns = prepare_appcontext(func)
        self.context_variables, self.context_returns = prepare_context_variables(func)
        self.pass_app_context = self.app_context_variables.count > 0

        self._validate_arguments(func)
        self.validate_returns(func)

    # ------------------------------------------------------------------ checks

    def _validate_arguments(self, func: AnyFunction) -> None:
        parameters = inspect.signature(func).parameters
        injectable = list(self.app_context_variables.app_context_variables.keys())
        if self.injects_states:
            injectable += list(self.state_variables.variable_keys) + list(
                self.context_variables.context_variables.keys()
            )

        if len(parameters) > len(injectable):
            incorrect_args = set(parameters.keys()) - set(injectable)
            what = (
                "app-context, state and context variables"
                if self.injects_states
                else "app-context variables (states and contexts do not exist yet when it runs)"
            )
            raise ValueError(
                f"{self.hook_kind} function {func.__name__} has more arguments than the {what}. "
                f"Expected at most {len(injectable)} arguments, but got {len(parameters)}. "
                f"{incorrect_args} are not valid argument names."
            )

    def validate_returns(self, func: AnyFunction) -> None:
        """Hook for subclasses to constrain what the function may return."""

    # ----------------------------------------------------------------- kwargs

    def get_kwargs(
        self,
        contexts: Dict[str, Any],
        states: Dict[str, Any],
        app_context: Any = None,  # noqa: ANN401
    ) -> Dict[str, Any]:
        """Build the call kwargs from the agent's live contexts, states and app context."""
        kwargs: Dict[str, Any] = {}
        for key, value in self.context_variables.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"Context requirements not met: {e}"
                ) from e

        for mapping in (
            self.state_variables.read_only_variables,
            self.state_variables.write_state_variables,
        ):
            for key, value in mapping.items():
                try:
                    kwargs[key] = states[value]
                except KeyError as e:
                    raise StateRequirementsNotMet(
                        f"State requirements not met: {e}. Available are {list(states.keys())}"
                    ) from e

        for key, value in self.app_context_variables.app_context_variables.items():
            if getattr(app_context, "__rekuest_app_context__", None) != value:
                raise StateRequirementsNotMet(
                    f"App context requirements not met: the agent was not started with a {value} app context"
                )
            kwargs[key] = app_context

        return kwargs
