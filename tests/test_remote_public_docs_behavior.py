import pytest

import rekuest_next.remote as remote
from rekuest_next.api.schema import Action


@pytest.mark.asyncio
async def test_aiterate_expands_raw_yield_payloads(monkeypatch) -> None:
    action = Action.model_construct(id="action-1")

    async def fake_ashrink_args(action_obj, args, kwargs, structure_registry=None):
        return {"value": 1}

    async def fake_aiterate_raw(**kwargs):
        yield ("raw",)

    async def fake_aexpand_returns(action_obj, returns, structure_registry=None):
        assert returns == ("raw",)
        return ("expanded",)

    monkeypatch.setattr(remote, "ashrink_args", fake_ashrink_args)
    monkeypatch.setattr(remote, "aiterate_raw", fake_aiterate_raw)
    monkeypatch.setattr(remote, "aexpand_returns", fake_aexpand_returns)
    monkeypatch.setattr(remote, "get_default_structure_registry", lambda: object())

    results = [item async for item in remote.aiterate(action, value=1)]

    assert results == ["expanded"]