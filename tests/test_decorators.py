from typing import Tuple

from rekuest_next import startup, context, background, state
import pytest


@pytest.mark.gggg
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
