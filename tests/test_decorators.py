from typing import Tuple

import pytest

from rekuest_next import startup, shutdown, context, state


def test_startup_decorator():
    @startup
    def my_startup_hook():
        pass

    @context
    class Hallo:
        pass

    @state
    class HalloState:
        pass

    @startup
    def my_startup_hook_returns_context() -> Hallo:
        return Hallo()
        pass

    @startup
    def my_startup_hook_returns_context_and_state() -> Tuple[Hallo, HalloState]:
        return Hallo(), HalloState()
        pass


def test_shutdown_decorator():
    @context
    class Tschau:
        pass

    @state
    class TschauState:
        pass

    @shutdown
    def my_shutdown_hook():
        pass

    @shutdown
    async def my_async_shutdown_hook(tschau: Tschau, tschau_state: TschauState) -> None:
        pass

    with pytest.raises(ValueError):

        @shutdown
        def my_shutdown_hook_returns_state() -> TschauState:
            return TschauState()

    with pytest.raises(ValueError):

        @shutdown
        def my_shutdown_hook_with_unknown_arg(unknown: int) -> None:
            pass
