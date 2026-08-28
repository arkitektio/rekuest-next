"""Testing utilities for FastAPI agent integration.

This module provides helper classes and functions for testing FastAPI
applications that use the rekuest_next agent system.
"""

import asyncio
import contextlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Callable, Any, Generator, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.testclient import WebSocketTestSession

from rekuest_next.app import AppRegistry

from .agent import FastApiAgent


@dataclass
class BufferedEvent:
    """A buffered event received from the WebSocket.

    Attributes:
        raw: The raw JSON string received from the WebSocket.
        data: The parsed JSON data as a dictionary.
        event_type: The type of the event (e.g., "DONE", "YIELD", "ERROR").
        task: The task ID this event belongs to, if present.
    """

    raw: str
    data: dict[str, Any]
    event_type: str
    task: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str) -> "BufferedEvent":
        """Create a BufferedEvent from a JSON string."""
        data = json.loads(json_str)
        return cls(
            raw=json_str,
            data=data,
            event_type=data.get("type", "UNKNOWN"),
            task=data.get("task"),
        )

    def is_done(self) -> bool:
        """Check if this is a DONE event."""
        return self.event_type == "DONE"

    def is_end_state(self) -> bool:
        """Check if this is an end state event (DONE or ERROR)."""
        return self.event_type in {"DONE", "ERROR", "CRITICAL", "CANCELLED"}

    def is_yield(self) -> bool:
        """Check if this is a YIELD event."""
        return self.event_type == "YIELD"

    def is_error(self) -> bool:
        """Check if this is an ERROR event."""
        return self.event_type == "ERROR"

    def is_criticial(self) -> bool:
        """Check if this is a CRITICAL event."""
        return self.event_type == "CRITICAL"

    def is_progress(self) -> bool:
        """Check if this is a PROGRESS event."""
        return self.event_type == "PROGRESS"

    def is_log(self) -> bool:
        """Check if this is a LOG event."""
        return self.event_type == "LOG"

    def get_returns(self) -> Optional[dict[str, Any]]:
        """Get the returns from a YIELD event."""
        return self.data.get("returns")


@dataclass
class AssignmentResult:
    """Result of an assignment request.

    Attributes:
        status: The status returned by the server (e.g., "submitted").
        task_id: The unique ID assigned to this assignment.
        response_data: The full response data from the server.
    """

    status: str
    task_id: str
    response_data: dict[str, Any]


class _EventBuffer:
    """Thread-safe store of websocket events shared by both test clients.

    The sync client appends from a listener thread and the async client from a
    coroutine; a plain lock covers both since no holder ever blocks while holding it.
    """

    def __init__(self) -> None:
        self._buffer = _EventBuffer()

    def add(self, event: BufferedEvent) -> None:
        """Append one event."""
        self._buffer.add(event)

    def all(self) -> list[BufferedEvent]:
        """Snapshot of every buffered event."""
        with self._lock:
            return list(self._events)

    def where(self, predicate: Callable[[BufferedEvent], bool]) -> list[BufferedEvent]:
        """Snapshot of the events matching ``predicate``."""
        with self._lock:
            return [e for e in self._events if predicate(e)]

    def clear(self) -> None:
        """Drop every buffered event."""
        with self._lock:
            self._buffer.clear()


class _EventAccessors:
    """Read-side helpers over an ``_EventBuffer``; mixed into both clients."""

    _buffer: _EventBuffer

    def add_event(self, event: BufferedEvent) -> None:
        """Add an event to the buffer (thread-safe)."""
        self._buffer.add(event)

    def get_all_events(self) -> list[BufferedEvent]:
        """Get all buffered events."""
        return self._buffer.all()

    def get_events_for_task(self, task_id: str) -> list[BufferedEvent]:
        """Get all events for a specific task."""
        return self._buffer.where(lambda e: e.task == task_id)

    def get_done_events(self) -> list[BufferedEvent]:
        """Get all DONE events."""
        return self._buffer.where(lambda e: e.is_done())

    def get_yield_events(self) -> list[BufferedEvent]:
        """Get all YIELD events."""
        return self._buffer.where(lambda e: e.is_yield())

    def get_error_events(self) -> list[BufferedEvent]:
        """Get all ERROR events."""
        return self._buffer.where(lambda e: e.is_error())

    def clear_events(self) -> None:
        """Clear all buffered events."""
        self._buffer.clear()

    def has_done_for(self, task_id: str) -> bool:
        """Check if a DONE event was received for the given task."""
        return any(e.is_done() for e in self.get_events_for_task(task_id))

    def has_error_for(self, task_id: str) -> bool:
        """Check if an ERROR event was received for the given task."""
        return any(e.is_error() for e in self.get_events_for_task(task_id))


def _build_assign_request(
    interface: str, args: dict[str, Any], use_implementation_route: bool
) -> tuple[str, dict[str, Any]]:
    """Return the ``(path, json_payload)`` for an assign against the real routes.

    Every assign route (``/{interface}``, ``/assign/{interface}`` and ``/assign``)
    validates its body as an ``AssignInput``, so the args must be nested under
    ``"args"`` rather than posted bare.
    """
    path = f"/{interface}" if use_implementation_route else f"/assign/{interface}"
    return path, {"args": args, "interface": interface}


class AgentTestClient(_EventAccessors):
    """A test client wrapper that provides WebSocket event buffering for agent testing.

    This class wraps FastAPI's TestClient and connects to the WebSocket endpoint,
    buffering all events for later inspection. It supports user authentication via
    the `as_user` parameter, which sends headers on HTTP requests and an init
    message on WebSocket connect.

    The WebSocket connection is managed in a background thread, allowing HTTP
    requests to be made while still receiving WebSocket events.

    Example:
        ```python
        app, agent = create_my_app()

        with AgentTestClient(app, agent, as_user="test-user") as client:
            # Make an assignment (header x-session-user will be set)
            result = client.assign("my_function", {"x": 1, "y": 2})

            # Collect events for a short period
            events = client.collect_events(timeout=1.0)
            assert any(e.is_done() for e in events)
        ```

    Attributes:
        app: The FastAPI application under test.
        agent: The FastApiAgent instance.
        ws_path: The WebSocket endpoint path (default: "/ws").
        as_user: The user to impersonate for requests and WebSocket init.
    """

    def __init__(
        self,
        app: FastAPI,
        ws_path: str = "/ws",
        as_user: Optional[str] = None,
    ) -> None:
        """Initialize the AgentTestClient.

        Args:
            app: The FastAPI application to test.
            agent: The FastApiAgent instance used by the app.
            ws_path: The path to the WebSocket endpoint.
            as_user: Optional user identifier. When set, HTTP requests will
                include `x-session-user` header and WebSocket will send an
                init message with the user info.
        """
        self.app = app
        self.ws_path = ws_path
        self.as_user = as_user
        self._client: Optional[TestClient] = None
        self._websocket: Optional[WebSocketTestSession] = None
        self._buffer = _EventBuffer()

    def __enter__(self) -> "AgentTestClient":
        """Enter the context manager, starting the test client and WebSocket connection."""
        self._client = TestClient(self.app)
        self._client.__enter__()

        deadline = time.time() + 5.0
        while time.time() < deadline:
            agent = getattr(self.app.state, "agent", None)
            transport = getattr(agent, "transport", None)
            if transport is not None and getattr(transport, "connected", False):
                break
            time.sleep(0.01)

        # Connect to WebSocket with headers if as_user is set
        headers: dict[str, str] = {}
        if self.as_user:
            headers["x-session-user"] = self.as_user

        self._websocket = self._client.websocket_connect(self.ws_path, headers=headers)
        self._websocket.__enter__()

        init_message = {"type": "INIT"}
        if self.as_user:
            init_message["user"] = self.as_user
        self._websocket.send_text(json.dumps(init_message))

        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit the context manager, cleaning up connections."""
        # Close WebSocket if open
        if self._websocket is not None:
            try:
                self._websocket.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
            self._websocket = None

        # Close test client
        if self._client is not None:
            self._client.__exit__(exc_type, exc_val, exc_tb)
            self._client = None

        self._buffer.clear()

    @property
    def client(self) -> TestClient:
        """Get the underlying TestClient."""
        if self._client is None:
            raise RuntimeError(
                "AgentTestClient is not in a context. Use 'with' statement."
            )
        return self._client

    def _get_headers(
        self, extra_headers: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Get headers for HTTP requests, including x-session-user if as_user is set."""
        headers: dict[str, str] = {}
        if self.as_user:
            headers["x-session-user"] = self.as_user
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make a POST request to the app.

        If `as_user` is set, the `x-session-user` header will be included.

        Args:
            path: The URL path to POST to.
            json: JSON data to send in the request body.
            headers: Additional headers to include.
            **kwargs: Additional arguments passed to TestClient.post().

        Returns:
            The response from the server.
        """
        return self.client.post(
            path, json=json, headers=self._get_headers(headers), **kwargs
        )

    def get(
        self,
        path: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make a GET request to the app.

        If `as_user` is set, the `x-session-user` header will be included.

        Args:
            path: The URL path to GET.
            headers: Additional headers to include.
            **kwargs: Additional arguments passed to TestClient.get().

        Returns:
            The response from the server.
        """
        return self.client.get(path, headers=self._get_headers(headers), **kwargs)

    def assign(
        self,
        interface: str,
        args: dict[str, Any],
        use_implementation_route: bool = True,
    ) -> AssignmentResult:
        """Assign work to the agent.

        If `as_user` is set, the `x-session-user` header will be included.

        Args:
            interface: The interface name (function name) to call.
            args: The arguments to pass to the function.
            use_implementation_route: If True, uses the direct implementation route
                (e.g., /my_function). If False, uses the generic assign endpoint
                (e.g., /assign/my_function).

        Returns:
            An AssignmentResult with the status and task ID.

        Raises:
            RuntimeError: If the assignment request fails.
        """
        path, payload = _build_assign_request(interface, args, use_implementation_route)
        response = self.post(path, json=payload)

        if response.status_code != 200:
            raise RuntimeError(
                f"Assignment failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        return AssignmentResult(
            status=data.get("status", "unknown"),
            task_id=data.get("task", ""),
            response_data=data,
        )

    def receive_event(self) -> BufferedEvent:
        """Receive a single event from the WebSocket.

        This blocks until an event is received from the WebSocket.
        The event is automatically added to the buffer.

        Returns:
            The received event.

        Raises:
            RuntimeError: If WebSocket is not connected.
        """
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")

        data = self._websocket.receive_text()
        event = BufferedEvent.from_json(data)
        self._buffer.add(event)
        return event

    def collect_events(
        self,
        count: Optional[int] = None,
        timeout: float = 1.0,
    ) -> list[BufferedEvent]:
        """Collect events from the WebSocket.

        This collects events until either the count is reached or timeout expires.
        Due to how the TestClient WebSocket works, this uses a threaded approach
        with a time-based collection.

        Args:
            count: Maximum number of events to collect. If None, collect all
                events that arrive within the timeout period.
            timeout: Maximum time to wait in seconds.

        Returns:
            A list of collected events. Events are also added to the buffer.
        """
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")

        collected: list[BufferedEvent] = []
        start_time = time.time()

        def collector() -> None:
            nonlocal collected
            try:
                while True:
                    if count is not None and len(collected) >= count:
                        break
                    if time.time() - start_time > timeout:
                        break
                    try:
                        assert self._websocket is not None
                        data = self._websocket.receive_text()
                        event = BufferedEvent.from_json(data)
                        self._buffer.add(event)
                        collected.append(event)
                    except Exception:
                        break
            except Exception:
                pass

        # Run collection in a thread with timeout
        thread = threading.Thread(target=collector, daemon=True)
        thread.start()
        thread.join(timeout=timeout + 0.5)

        return collected

    def collect_until_done(
        self,
        task_id: str,
        timeout: float = 5.0,
    ) -> list[BufferedEvent]:
        """Collect events until a DONE event is received for the task.

        Args:
            task_id: The task ID to wait for.
            timeout: Maximum time to wait in seconds.

        Returns:
            A list of all events collected (including the DONE event).
        """
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")

        collected: list[BufferedEvent] = []
        start_time = time.time()
        done_received = threading.Event()

        def collector() -> None:
            nonlocal collected
            try:
                while not done_received.is_set():
                    if time.time() - start_time > timeout:
                        break
                    try:
                        assert self._websocket is not None
                        data = self._websocket.receive_text()
                        event = BufferedEvent.from_json(data)
                        self._buffer.add(event)
                        collected.append(event)

                        if event.task == task_id and event.is_done():
                            done_received.set()
                            break
                    except Exception:
                        break
            except Exception:
                pass

        thread = threading.Thread(target=collector, daemon=True)
        thread.start()
        thread.join(timeout=timeout + 0.5)

        return collected


class AsyncAgentTestClient(_EventAccessors):
    """An async test client that provides WebSocket event buffering for agent testing.

    This class uses httpx AsyncClient for HTTP requests and runs a background
    task to listen for WebSocket events. This allows for proper async handling
    of concurrent HTTP requests and WebSocket message reception.

    Example:
        ```python
        app, agent = create_my_app()

        async with AsyncAgentTestClient(app, agent, as_user="test-user") as client:
            # Make an assignment (header x-session-user will be set)
            result = await client.assign("my_function", {"x": 1, "y": 2})

            # Wait for events
            events = await client.collect_until_done(result.task_id)
            assert any(e.is_done() for e in events)
        ```

    Attributes:
        app: The FastAPI application under test.
        agent: The FastApiAgent instance.
        ws_path: The WebSocket endpoint path (default: "/ws").
        as_user: The user to impersonate for requests and WebSocket init.
    """

    def __init__(
        self,
        app: FastAPI,
        ws_path: str = "/ws",
        as_user: Optional[str] = None,
        base_url: str = "http://test",
    ) -> None:
        """Initialize the AsyncAgentTestClient.

        Args:
            app: The FastAPI application to test.
            agent: The FastApiAgent instance used by the app.
            ws_path: The path to the WebSocket endpoint.
            as_user: Optional user identifier. When set, HTTP requests will
                include `x-session-user` header and WebSocket will send an
                init message with the user info.
            base_url: The base URL for HTTP requests.
        """
        self.app = app
        self.ws_path = ws_path
        self.as_user = as_user
        self.base_url = base_url
        self._http_client: Optional[AsyncClient] = None
        self._buffer = _EventBuffer()
        self._event_queue: asyncio.Queue[BufferedEvent] = asyncio.Queue()
        self._ws_task: Optional[asyncio.Task[None]] = None
        self._stop_ws = asyncio.Event()
        self._test_client: Optional[TestClient] = None
        self._websocket: Optional[WebSocketTestSession] = None

    async def __aenter__(self) -> "AsyncAgentTestClient":
        """Enter the async context manager."""
        # Use TestClient for lifespan handling
        self._test_client = TestClient(self.app)
        self._test_client.__enter__()

        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            agent = getattr(self.app.state, "agent", None)
            transport = getattr(agent, "transport", None)
            if transport is not None and getattr(transport, "connected", False):
                break
            await asyncio.sleep(0.01)

        # Create async HTTP client
        transport = ASGITransport(app=self.app)  # type: ignore
        self._http_client = AsyncClient(transport=transport, base_url=self.base_url)

        # Connect to WebSocket
        headers: dict[str, str] = {}
        if self.as_user:
            headers["x-session-user"] = self.as_user

        self._websocket = self._test_client.websocket_connect(
            self.ws_path, headers=headers
        )
        self._websocket.__enter__()

        init_message = {"type": "INIT"}
        if self.as_user:
            init_message["user"] = self.as_user
        self._websocket.send_text(json.dumps(init_message))

        # Start WebSocket listener task
        self._stop_ws.clear()
        self._ws_task = asyncio.create_task(self._ws_listener())

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit the async context manager."""
        # Stop WebSocket listener
        self._stop_ws.set()
        if self._ws_task is not None:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        # Close WebSocket
        if self._websocket is not None:
            try:
                self._websocket.__exit__(None, None, None)
            except Exception:
                pass
            self._websocket = None

        # Close HTTP client
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

        # Close test client
        if self._test_client is not None:
            self._test_client.__exit__(None, None, None)
            self._test_client = None

        self._buffer.clear()

    async def _ws_listener(self) -> None:
        """Background task that listens for WebSocket messages."""
        loop = asyncio.get_event_loop()

        def receive_sync() -> Optional[str]:
            try:
                if self._websocket is not None:
                    return self._websocket.receive_text()
            except Exception:
                pass
            return None

        while not self._stop_ws.is_set():
            try:
                # Run blocking receive in thread pool
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, receive_sync), timeout=0.1
                )
                if data is not None:
                    event = BufferedEvent.from_json(data)
                    self._buffer.add(event)
                    await self._event_queue.put(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                break

    def _get_headers(
        self, extra_headers: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Get headers for HTTP requests, including x-session-user if as_user is set."""
        headers: dict[str, str] = {}
        if self.as_user:
            headers["x-session-user"] = self.as_user
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make an async POST request to the app.

        Args:
            path: The URL path to POST to.
            json: JSON data to send in the request body.
            headers: Additional headers to include.
            **kwargs: Additional arguments passed to AsyncClient.post().

        Returns:
            The response from the server.
        """
        if self._http_client is None:
            raise RuntimeError("Client not connected")
        return await self._http_client.post(
            path, json=json, headers=self._get_headers(headers), **kwargs
        )

    async def get(
        self,
        path: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make an async GET request to the app.

        Args:
            path: The URL path to GET.
            headers: Additional headers to include.
            **kwargs: Additional arguments passed to AsyncClient.get().

        Returns:
            The response from the server.
        """
        if self._http_client is None:
            raise RuntimeError("Client not connected")
        return await self._http_client.get(
            path, headers=self._get_headers(headers), **kwargs
        )

    async def assign(
        self,
        interface: str,
        args: dict[str, Any],
        use_implementation_route: bool = False,
    ) -> AssignmentResult:
        """Assign work to the agent.

        Args:
            interface: The interface name (function name) to call.
            args: The arguments to pass to the function.
            use_implementation_route: If True, uses the direct implementation route.

        Returns:
            An AssignmentResult with the status and task ID.
        """
        path, payload = _build_assign_request(interface, args, use_implementation_route)
        response = await self.post(path, json=payload)

        if response.status_code != 200:
            raise RuntimeError(
                f"Assignment failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        return AssignmentResult(
            status=data.get("status", "unknown"),
            task_id=data.get("task", ""),
            response_data=data,
        )

    async def receive_event(self, timeout: float = 5.0) -> Optional[BufferedEvent]:
        """Receive a single event from the WebSocket.

        Args:
            timeout: Maximum time to wait for an event.

        Returns:
            The received event, or None if timeout.
        """
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def collect_events(
        self,
        count: Optional[int] = None,
        timeout: float = 1.0,
    ) -> list[BufferedEvent]:
        """Collect events from the WebSocket.

        Args:
            count: Maximum number of events to collect.
            timeout: Maximum time to wait in seconds.

        Returns:
            A list of collected events.
        """
        collected: list[BufferedEvent] = []
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            if count is not None and len(collected) >= count:
                break

            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=min(remaining, 0.1)
                )
                collected.append(event)
            except asyncio.TimeoutError:
                continue

        return collected

    async def _collect_until(
        self,
        predicate: Callable[[BufferedEvent], bool],
        task_id: str,
        timeout: float,
        raise_on_timeout: bool,
    ) -> list[BufferedEvent]:
        """Collect events until one for ``task_id`` satisfies ``predicate``.

        On timeout either raises ``TimeoutError`` or returns what was collected.
        """
        collected: list[BufferedEvent] = []
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                if raise_on_timeout:
                    raise TimeoutError(f"Timeout waiting for event on task {task_id}")
                return collected

            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=min(remaining, 0.5)
                )
            except asyncio.TimeoutError:
                continue
            collected.append(event)
            if event.task == task_id and predicate(event):
                return collected

    async def collect_until_end_state(
        self,
        task_id: str,
        timeout: float = 5.0,
    ) -> list[BufferedEvent]:
        """Collect events until a DONE or ERROR event is received for the task.

        Raises ``TimeoutError`` if neither arrives within ``timeout``.
        """
        return await self._collect_until(
            lambda e: e.is_end_state(), task_id, timeout, raise_on_timeout=True
        )

    async def collect_until_done(
        self,
        task_id: str,
        timeout: float = 5.0,
    ) -> list[BufferedEvent]:
        """Collect events until a DONE event is received for the task.

        Returns whatever was collected if the timeout elapses first.
        """
        return await self._collect_until(
            lambda e: e.is_done(), task_id, timeout, raise_on_timeout=False
        )

    async def collect_until_error(
        self,
        task_id: str,
        timeout: float = 5.0,
    ) -> list[BufferedEvent]:
        """Collect events until an ERROR event is received for the task.

        Returns whatever was collected if the timeout elapses first.
        """
        return await self._collect_until(
            lambda e: e.is_error(), task_id, timeout, raise_on_timeout=False
        )


@contextlib.contextmanager
def create_test_lifespan(
    agent: FastApiAgent,
) -> Generator[contextlib.AbstractAsyncContextManager[None], None, None]:
    """Create a test lifespan context manager for FastAPI.

    This creates a lifespan that only connects the transport without
    running the full provide loop (which would require a backend connection).

    Args:
        agent: The FastApiAgent to use.

    Yields:
        An async context manager suitable for FastAPI's lifespan parameter.
    """

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agent = agent
        await agent.transport.aconnect()
        try:
            yield
        finally:
            await agent.transport.adisconnect()

    yield lifespan


def create_test_app_and_agent(
    app_registry: Optional["AppRegistry"] = None,
) -> tuple[FastAPI, FastApiAgent, AppRegistry]:
    """Create a fresh FastAPI app and agent for testing.

    This is a convenience function that sets up all the necessary registries
    and creates a properly configured FastAPI app using configure_fastapi.

    Returns:
        A tuple of (app, agent, app_registry).

    Example:
        ```python
        from rekuest_next.contrib.fastapi import (
            create_test_app_and_agent,
            AsyncAgentTestClient,
        )

        app, agent, app_registry = create_test_app_and_agent()

        @app_registry.register
        def my_function(x: int) -> int:
            return x * 2

        async with AsyncAgentTestClient(app, agent, as_user="test-user") as client:
            result = await client.assign("my_function", {"x": 5})
            # Collect events after assignment
            events = await client.collect_until_done(result.task_id)
            assert any(e.is_done() for e in events)
        ```

    Note:
        Implementation routes are added dynamically when the lifespan starts.
        The agent routes (task/state/lock websockets and task commands) are added immediately.
    """
    from rekuest_next.app import AppRegistry
    from rekuest_next.contrib.fastapi.routes import configure_fastapi

    app_registry = app_registry or AppRegistry()

    app = FastAPI(
        title="Test API",
        description="Test API for FastAPI agent testing",
        version="1.0.0",
    )

    agent = configure_fastapi(
        app=app,
        app_registry=app_registry,
    )

    return app, agent, app_registry


__all__ = [
    "AgentTestClient",
    "AsyncAgentTestClient",
    "AssignmentResult",
    "BufferedEvent",
    "create_test_app_and_agent",
    "create_test_lifespan",
]
