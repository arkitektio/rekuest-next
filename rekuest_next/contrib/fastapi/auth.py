"""Transport-agnostic user expansion for the FastAPI integration.

HTTP requests carry credentials in headers, but browsers cannot set headers on a
`WebSocket` constructor. The websocket therefore authenticates *in band*: the init
payload every client already sends after connecting carries an optional `token`.

Both paths funnel into a single user-supplied callable so an application defines its
auth rules once:

```python
def expand_user(source: UserSource) -> str:
    if isinstance(source, Request):
        credential = source.headers.get("authorization")
    else:
        credential = source.token
    if not is_valid(credential):
        raise AuthenticationError("invalid credentials")
    return "some-user"

configure_fastapi(app, registry, expand_user_from_request=expand_user)
```

Rejection is signalled by raising `AuthenticationError`. The transport decides how to
surface it: HTTP answers `401`, the websocket closes with code `1008`.
"""

from typing import Any
from collections.abc import Callable

from fastapi import Request

from rekuest_next.contrib.fastapi.models import WebSocketSubscriptionInit

#: Either arm of the union a user-expansion hook may be handed.
UserSource = Request | WebSocketSubscriptionInit

#: Signature of the unified user-expansion hook.
ExpandUserFromRequest = Callable[[UserSource], Any]


class AuthenticationError(Exception):
    """Raised by an expansion hook to reject a request or websocket handshake."""


def default_expand_user_from_request(source: UserSource) -> str:
    """Expand every caller to `"anonymous"`.

    Deliberately permissive: the FastAPI integration is unauthenticated unless an
    application opts in, so an app that never passes a hook keeps working unchanged.
    """
    return "anonymous"


def wrap_legacy_get_user_from_request(
    get_user_from_request: Callable[[Request], Any],
) -> ExpandUserFromRequest:
    """Adapt a legacy HTTP-only `get_user_from_request` to the unified signature.

    The legacy hook only ever saw a `Request`, so it cannot judge a websocket init
    payload. Websockets fall back to the permissive default rather than being handed a
    payload the callable was never written to accept.
    """

    def _expand(source: UserSource) -> Any:
        if isinstance(source, WebSocketSubscriptionInit):
            return default_expand_user_from_request(source)
        return get_user_from_request(source)

    return _expand


def resolve_expand_user_from_request(
    expand_user_from_request: ExpandUserFromRequest | None,
    get_user_from_request: Callable[[Request], Any] | None,
) -> ExpandUserFromRequest:
    """Pick the effective hook, newest wins, falling back to the permissive default."""
    if expand_user_from_request is not None:
        return expand_user_from_request
    if get_user_from_request is not None:
        return wrap_legacy_get_user_from_request(get_user_from_request)
    return default_expand_user_from_request


__all__ = [
    "AuthenticationError",
    "ExpandUserFromRequest",
    "UserSource",
    "default_expand_user_from_request",
    "resolve_expand_user_from_request",
    "wrap_legacy_get_user_from_request",
]
