"""No-Docker checks for the agent <-> app-registry wiring.

These cover the structural change where the agent reads everything from a single
``AppRegistry`` (instead of the removed extension layer): ``collect_from_registry``
gathers implementations from the registry, and the actor-builder used by the
spawn path is resolvable from the same registry.
"""

import pytest

from rekuest_next.rekuest import RekuestNext


def test_collect_from_registry_reads_app_registry(mock_rekuest: RekuestNext) -> None:
    def myfunc(x: int) -> int:
        """A simple function."""
        return x

    mock_rekuest.register(myfunc)

    agent = mock_rekuest.agent
    # collect_from_registry must run cleanly against the app registry...
    agent.collect_from_registry()

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


@pytest.mark.asyncio
async def test_definition_hash_is_stable_and_definition_sensitive(
    mock_rekuest: RekuestNext,
) -> None:
    """``aget_hash`` must be reproducible, or the agent re-registers on every start.

    The backend stores the hash the agent sends and hands it back, so the only thing
    that makes the skip-re-registration check work is that an unchanged definition
    hashes the same twice, and a changed one does not.
    """
    agent = mock_rekuest.agent

    before = await agent.aget_hash()
    assert before == await agent.aget_hash(), "the same definition must hash the same"

    # A name no other test registers: `mock_rekuest` shares the process-default
    # registry, so a name already registered would make this a no-op.
    def hash_probe_func(x: int) -> int:
        """A simple function."""
        return x

    mock_rekuest.register(hash_probe_func)

    assert await agent.aget_hash() != before, (
        "registering an implementation must change the definition hash"
    )


@pytest.mark.asyncio
async def test_agent_supplies_its_session_and_takeover_policy(
    mock_rekuest: RekuestNext,
) -> None:
    """The agent is the handshake provider, so Register can carry the session id.

    The session id lives on the agent and the Register frame is built by the transport,
    which is why it went unsent until the handshake became an explicit seam.
    """
    agent = mock_rekuest.agent

    params = await agent.aget_handshake_params()
    assert params.session_id == agent.current_session
    assert params.force is None, "no opinion by default, so the transport policy stands"

    # `run(force=True)` is a per-run override of an agent-level registration policy.
    mock_rekuest._maybe_override_force(True)
    assert (await agent.aget_handshake_params()).force is True
