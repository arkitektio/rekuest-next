"""No-Docker checks for the agent <-> app-registry wiring.

These cover the structural change where the agent reads everything from a single
``AppRegistry`` (instead of the removed extension layer): ``collect_from_extensions``
gathers implementations from the registry, and the actor-builder used by the
spawn path is resolvable from the same registry.
"""

from rekuest_next.rekuest import RekuestNext


def test_collect_from_extensions_reads_app_registry(mock_rekuest: RekuestNext) -> None:
    def myfunc(x: int) -> int:
        """A simple function."""
        return x

    mock_rekuest.register(myfunc)

    agent = mock_rekuest.agent
    # collect_from_extensions must run cleanly against the app registry...
    agent.collect_from_extensions()

    # ...and the app registry is the single source the agent reads from.
    interfaces = {
        impl.interface or impl.definition.name
        for impl in agent.app_registry.get_implementations()
    }
    assert "myfunc" in interfaces


def test_actor_builder_resolvable_from_app_registry(mock_rekuest: RekuestNext) -> None:
    def myfunc(x: int) -> int:
        """A simple function."""
        return x

    mock_rekuest.register(myfunc)

    # The spawn path (aspawn_actor_from_assign) resolves the builder like this.
    builder = mock_rekuest.agent.app_registry.get_builder_for_interface("myfunc")
    assert callable(builder)
