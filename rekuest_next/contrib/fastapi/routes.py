"""FastAPI route configuration for rekuest_next agents.

This module provides utilities to configure a FastAPI app with agent routes,
including WebSocket endpoints, assignation management, and auto-generated
routes for registered implementations.
"""

import asyncio
import contextlib
import logging
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from rekuest_next.api.schema import (
    ImplementationInput,
    PortInput,
    PortKind,
    StateSchemaInput,
)
from rekuest_next.app import AppRegistry
from rekuest_next.messages import Assign

from .agent import FastApiAgent


logger = logging.getLogger(__name__)


def port_to_json_schema(port: PortInput) -> Dict[str, Any]:
    """Convert a Port definition to a JSON Schema object, handling nested children."""
    schema: Dict[str, Any] = {}

    # Add title and description
    if port.label:
        schema["title"] = port.label
    if port.description:
        schema["description"] = port.description

    # Map PortKind to JSON Schema types
    if port.kind == PortKind.INT:
        schema["type"] = "integer"
    elif port.kind == PortKind.STRING:
        schema["type"] = "string"
    elif port.kind == PortKind.BOOL:
        schema["type"] = "boolean"
    elif port.kind == PortKind.FLOAT:
        schema["type"] = "number"
    elif port.kind == PortKind.LIST:
        schema["type"] = "array"
        if port.children:
            schema["items"] = port_to_json_schema(port.children[0])
        else:
            schema["items"] = {}
    elif port.kind == PortKind.DICT or port.kind == PortKind.STRUCTURE:
        schema["type"] = "object"
        if port.children:
            schema["properties"] = {
                child.key: port_to_json_schema(child) for child in port.children
            }
            required = [
                child.key for child in port.children if not child.nullable and child.default is None
            ]
            if required:
                schema["required"] = required
        else:
            schema["additionalProperties"] = True
    else:
        schema["type"] = ["string", "number", "boolean", "object", "array", "null"]

    # Handle identifier
    if port.identifier:
        schema["x-identifier"] = port.identifier

    # Handle choices (enum)
    if port.choices:
        schema["enum"] = [choice.value for choice in port.choices]

    # Handle default value
    if port.default is not None:
        schema["default"] = port.default

    # Handle nullable
    if port.nullable:
        if "type" in schema and isinstance(schema["type"], str):
            schema["type"] = [schema["type"], "null"]

    return schema


def create_json_schema_from_ports(
    ports: tuple[PortInput, ...], schema_title: str
) -> Dict[str, Any]:
    """Create a JSON Schema object from a list of ports."""
    if not ports:
        return {"type": "object", "title": schema_title, "properties": {}}

    properties = {}
    required = []

    for port in ports:
        properties[port.key] = port_to_json_schema(port)
        if not port.nullable and port.default is None:
            required.append(port.key)

    schema = {"type": "object", "title": schema_title, "properties": properties}
    if required:
        schema["required"] = required

    return schema


def _handle_provide_task_done(task: asyncio.Task) -> None:
    """Callback to handle provide task completion and log any errors."""
    try:
        exc = task.exception()
        if exc is not None:
            logger.error(f"Provide task failed with error: {exc}", exc_info=exc)
    except asyncio.CancelledError:
        logger.info("Provide task was cancelled")
    except asyncio.InvalidStateError:
        pass


def create_lifespan(agent: FastApiAgent, instance_id: str = "default"):
    """Create a lifespan context manager for a FastAPI app using the agent.

    Args:
        agent: The FastApiAgent to use.
        instance_id: The instance ID for the agent.

    Returns:
        An async context manager for FastAPI lifespan.
    """

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for FastAPI app using FastApiAgent."""
        app.state.agent = agent

        async with app.state.agent:
            provide_task = asyncio.create_task(app.state.agent.aprovide(instance_id=instance_id))
            provide_task.add_done_callback(_handle_provide_task_done)

            yield

            provide_task.cancel()
            try:
                await provide_task
            except asyncio.CancelledError:
                logger.info("Provide task cancelled during shutdown")
            except Exception as e:
                logger.error(f"Error during provide task shutdown: {e}", exc_info=True)

    return lifespan


def add_implementation_route(
    app: FastAPI,
    agent: FastApiAgent,
    implementation: ImplementationInput,
) -> None:
    """Add a route for a specific implementation to the FastAPI app.

    Args:
        app: The FastAPI application.
        agent: The FastApiAgent handling the implementation.
        implementation: The implementation to create a route for.
    """
    route_path = f"/{implementation.interface or implementation.definition.name}"

    # Create JSON schemas from the definition
    request_schema_name = f"{implementation.definition.name}Request"
    response_schema_name = f"{implementation.definition.name}Response"

    request_schema = create_json_schema_from_ports(
        implementation.definition.args, request_schema_name
    )
    response_schema = create_json_schema_from_ports(
        implementation.definition.returns, response_schema_name
    )

    # Store schemas for OpenAPI generation
    if not hasattr(app, "_custom_schemas"):
        app._custom_schemas = {}
    app._custom_schemas[request_schema_name] = request_schema
    app._custom_schemas[response_schema_name] = response_schema

    async def implementation_endpoint(request: Request) -> JSONResponse:
        """Execute the implementation with the provided payload."""
        payload = await request.json()

        assign = Assign(
            interface=implementation.interface or implementation.definition.name,
            extension="default",
            assignation=str(uuid.uuid4()),
            args=payload,
            user="fastapi",
            app="fastapi",
            action="api_call",
        )

        result = await agent.transport.asubmit(assign)
        return JSONResponse(content={"status": "submitted", "assignation": result})

    route = APIRoute(
        path=route_path,
        endpoint=implementation_endpoint,
        methods=["POST"],
        summary=implementation.definition.name,
        description=implementation.definition.description
        or f"Execute {implementation.definition.name} action",
        tags=list(implementation.definition.collections)
        if implementation.definition.collections
        else [],
        response_class=JSONResponse,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{request_schema_name}"}
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{response_schema_name}"}
                        }
                    },
                }
            },
        },
    )

    app.router.routes.append(route)


def add_agent_routes(
    app: FastAPI,
    agent: FastApiAgent,
    get_user_from_request: Optional[Callable[[Request], Any]] = None,
    ws_path: str = "/ws",
    assignations_path: str = "/assignations",
    assign_path: str = "/assign",
) -> None:
    """Add all agent-related routes to a FastAPI application.

    This adds:
    - WebSocket endpoint for receiving agent events
    - GET /assignations - list running assignations
    - GET /assignations/{id} - get specific assignation details
    - POST /assign/{interface} - assign an action by interface name

    Args:
        app: The FastAPI application to add routes to.
        agent: The FastApiAgent to use for handling requests.
        get_user_from_request: Optional function to extract user from request.
        ws_path: Path for the WebSocket endpoint.
        assignations_path: Path for the assignations endpoints.
        assign_path: Path for the assign endpoint.
    """
    if get_user_from_request is None:

        def get_user_from_request(request: Request) -> str:
            return "anonymous"

    @app.websocket(ws_path)
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for receiving agent events."""
        await agent.transport.handle_websocket(websocket)

    @app.get(assignations_path)
    async def get_assignations() -> dict:
        """Get the list of currently running assignations."""
        assignations = {}
        for assignation_id, assign_message in agent.managed_assignments.items():
            assignations[assignation_id] = {
                "interface": assign_message.interface,
                "extension": assign_message.extension,
                "user": assign_message.user,
                "app": assign_message.app,
                "action": assign_message.action,
                "args": assign_message.args,
            }

        return {
            "count": len(assignations),
            "assignations": assignations,
        }

    @app.get(f"{assignations_path}/{{assignation_id}}")
    async def get_assignation(assignation_id: str) -> dict:
        """Get details of a specific assignation."""
        if assignation_id not in agent.managed_assignments:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Assignation not found",
                    "assignation": assignation_id,
                },
            )

        assign_message = agent.managed_assignments[assignation_id]
        return {
            "assignation": assignation_id,
            "interface": assign_message.interface,
            "extension": assign_message.extension,
            "user": assign_message.user,
            "app": assign_message.app,
            "action": assign_message.action,
            "args": assign_message.args,
        }

    @app.post(f"{assign_path}/{{interface}}")
    async def assign_action(request: Request, interface: str, extension: str = "default") -> dict:
        """Assign an action to the agent for processing."""
        user = get_user_from_request(request)
        payload = await request.json()

        assignation_id = str(uuid.uuid4())
        assign_message = Assign(
            interface=interface,
            extension=extension,
            assignation=assignation_id,
            args=payload,
            user=str(user),
            app="fastapi",
            action="api_call",
        )

        await agent.transport.asubmit(assign_message)
        return {"status": "submitted", "assignation": assignation_id}


def add_implementation_routes(
    app: FastAPI,
    agent: FastApiAgent,
    extension: str = "default",
) -> None:
    """Add routes for all registered implementations in an extension.

    Args:
        app: The FastAPI application.
        agent: The FastApiAgent with registered implementations.
        extension: The extension name to get implementations from.
    """
    for implementation in agent.extension_registry.get(extension).get_static_implementations():
        add_implementation_route(app, agent, implementation)


def add_state_route(
    app: FastAPI,
    agent: FastApiAgent,
    interface: str,
    state_schema: StateSchemaInput,
    states_path: str = "/states",
) -> None:
    """Add a GET route for a specific state to the FastAPI app.

    Args:
        app: The FastAPI application.
        agent: The FastApiAgent with the state.
        interface: The interface name for the state.
        state_schema: The state schema input.
        states_path: Base path for state routes.
    """
    route_path = f"{states_path}/{interface}"

    # Create JSON schema from the state schema ports
    response_schema_name = f"{state_schema.name}State"
    response_schema = create_json_schema_from_ports(state_schema.ports, response_schema_name)

    # Store schema for OpenAPI generation
    if not hasattr(app, "_custom_schemas"):
        app._custom_schemas = {}
    app._custom_schemas[response_schema_name] = response_schema

    async def get_state_endpoint() -> JSONResponse:
        """Get the current state value."""
        if interface not in agent.states:
            return JSONResponse(
                status_code=404,
                content={"error": "State not initialized", "interface": interface},
            )

        # Return the shrunk (serialized) state if available
        if interface in agent._current_shrunk_states:
            return JSONResponse(content=agent._current_shrunk_states[interface])

        # Otherwise try to shrink it now
        try:
            shrunk = await agent.ashrink_state(interface, agent.states[interface])
            return JSONResponse(content=shrunk)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to serialize state: {str(e)}"},
            )

    route = APIRoute(
        path=route_path,
        endpoint=get_state_endpoint,
        methods=["GET"],
        summary=f"Get {state_schema.name} state",
        description=f"Get the current value of the {state_schema.name} state",
        tags=["States"],
        response_class=JSONResponse,
        openapi_extra={
            "responses": {
                "200": {
                    "description": "Current state value",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{response_schema_name}"}
                        }
                    },
                }
            },
        },
    )

    app.router.routes.append(route)


def add_schema_routes(
    app: FastAPI,
    agent: FastApiAgent,
    extension: str = "default",
) -> None:
    """Add routes to get implementation and state schemas.

    This adds:
    - GET /schemas/implementations - list all implementation schemas
    - GET /schemas/states - list all state schemas

    Args:
        app: The FastAPI application.
        agent: The FastApiAgent with registered implementations and states.
        extension: The extension name to get implementations from.
    """

    @app.get("/schemas/implementations")
    async def get_implementation_schemas() -> dict:
        """Get all implementation schemas for the specified extension."""
        implementations = {}
        for impl in agent.extension_registry.get(extension).get_static_implementations():
            implementations[impl.interface or impl.definition.name] = impl.definition

        return {
            "count": len(implementations),
            "implementations": implementations,
        }

    @app.get("/schemas/states")
    async def get_state_schemas() -> dict:
        """Get all registered state schemas."""
        state_schemas = {}
        for extension in agent.extension_registry.agent_extensions.values():
            for interface, schema in extension.get_state_schemas().items():
                state_schemas[interface] = schema

        return {
            "count": len(state_schemas),
            "states": state_schemas,
        }


def add_state_routes(
    app: FastAPI,
    agent: FastApiAgent,
    states_path: str = "/states",
    states_ws_path: str = "/states/ws",
) -> None:
    """Add routes for all registered states in the agent.

    This adds:
    - GET /states - list all available states
    - GET /states/{interface} - get the current value of a specific state
    - WebSocket /states/ws - subscribe to state updates

    Args:
        app: The FastAPI application.
        agent: The FastApiAgent with registered states.
        states_path: Base path for state routes.
        states_ws_path: Path for the state updates WebSocket.
    """

    # Collect state schemas from all extensions
    collected_state_schemas = {}
    for extension in agent.extension_registry.agent_extensions.values():
        collected_state_schemas.update(extension.get_state_schemas())

    # Add route to list all states
    @app.get(states_path)
    async def list_states() -> dict:
        """List all registered states and their current values."""
        states_info = {}
        # Collect state schemas from all extensions
        ext_state_schemas = {}
        for ext in agent.extension_registry.agent_extensions.values():
            ext_state_schemas.update(ext.get_state_schemas())

        for interface, schema in ext_state_schemas.items():
            state_data = {
                "name": schema.name,
                "interface": interface,
                "initialized": interface in agent.states,
            }

            # Include current value if initialized
            if interface in agent._current_shrunk_states:
                state_data["value"] = agent._current_shrunk_states[interface]

            states_info[interface] = state_data

        return {
            "count": len(states_info),
            "states": states_info,
        }

    # Collect state schemas from all extensions
    all_state_schemas = {}
    for extension in agent.extension_registry.agent_extensions.values():
        all_state_schemas.update(extension.get_state_schemas())

    # Add individual state routes for each registered state
    for interface, state_schema in all_state_schemas.items():
        add_state_route(app, agent, interface, state_schema, states_path)

    # Add WebSocket for state updates
    @app.websocket(states_ws_path)
    async def state_updates_websocket(websocket: WebSocket):
        """WebSocket endpoint for subscribing to state updates.

        Clients connect and receive real-time state change notifications.
        State updates are sent as JSON messages with the format:
        {"interface": "state_name", "value": {...}}
        """
        await agent.transport.connection_manager.connect(websocket)
        try:
            # Send current state values on connect
            # Collect state schemas from all extensions
            ext_state_schemas = {}
            for ext in agent.extension_registry.agent_extensions.values():
                ext_state_schemas.update(ext.get_state_schemas())

            for interface in ext_state_schemas:
                if interface in agent._current_shrunk_states:
                    await websocket.send_json(
                        {
                            "type": "STATE_INIT",
                            "interface": interface,
                            "value": agent._current_shrunk_states[interface],
                        }
                    )

            # Keep connection open - state updates will be broadcast separately
            while True:
                await websocket.receive()
        except Exception:
            pass
        finally:
            await agent.transport.connection_manager.disconnect(websocket)


def configure_openapi(app: FastAPI) -> None:
    """Configure custom OpenAPI schema generation to include implementation schemas.

    Args:
        app: The FastAPI application.
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        if hasattr(app, "_custom_schemas"):
            openapi_schema["components"]["schemas"].update(app._custom_schemas)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi


def configure_fastapi(
    app: FastAPI,
    app_registry: AppRegistry,
    get_user_from_request: Optional[Callable[[Request], Any]] = None,
    add_implementations: bool = True,
    add_schema: bool = True,
    add_states: bool = True,
    extension: str = "default",
    ws_path: str = "/ws",
    assignations_path: str = "/assignations",
    assign_path: str = "/assign",
    states_path: str = "/states",
    states_ws_path: str = "/states/ws",
    instance_id: str = "default",
) -> FastApiAgent:
    """Configure a FastAPI application with all agent routes, lifespan, and OpenAPI schemas.

    This is the main entry point for setting up a FastAPI app with a rekuest agent.
    It creates a FastApiAgent with a DefaultExtension using the provided AppRegistry,
    sets up the lifespan to manage the agent lifecycle, adds all routes (WebSocket,
    assignations, assign, implementation routes, and state routes) and configures
    OpenAPI schema generation.

    The lifespan is configured to:
    - Add implementation/state/schema routes at startup (after all functions are registered)
    - Start the agent and provide loop
    - Clean up on shutdown

    Args:
        app: The FastAPI application to configure.
        app_registry: The AppRegistry containing implementations, states, and hooks.
        get_user_from_request: Optional function to extract user from request.
        add_implementations: Whether to add routes for registered implementations.
        add_states: Whether to add routes for registered states.
        add_schema: Whether to add schema routes.
        extension: The extension name for implementations.
        ws_path: Path for the WebSocket endpoint.
        assignations_path: Path for the assignations endpoints.
        assign_path: Path for the assign endpoint.
        states_path: Path for the states endpoints.
        states_ws_path: Path for the states WebSocket endpoint.
        instance_id: The instance ID for the agent.

    Returns:
        The created FastApiAgent instance.

    Example:
        ```python
        from fastapi import FastAPI
        from rekuest_next.app import AppRegistry
        from rekuest_next.contrib.fastapi import configure_fastapi

        app_registry = AppRegistry()

        @app_registry.register
        def my_function(x: int) -> int:
            return x * 2

        app = FastAPI()
        agent = configure_fastapi(app, app_registry)
        # Lifespan is automatically configured - no additional setup needed
        ```
    """
    from rekuest_next.agents.extensions.default import DefaultExtension
    from rekuest_next.agents.registry import ExtensionRegistry

    # Create a DefaultExtension with the provided AppRegistry
    default_extension = DefaultExtension(app_registry=app_registry)

    # Create an ExtensionRegistry and register the extension
    extension_registry = ExtensionRegistry()
    extension_registry.register(default_extension)

    # Create the FastApiAgent with the extension registry
    agent = FastApiAgent(
        extension_registry=extension_registry,
    )

    # Add agent routes immediately (WebSocket, assignations, assign endpoints)
    add_agent_routes(
        app=app,
        agent=agent,
        get_user_from_request=get_user_from_request,
        ws_path=ws_path,
        assignations_path=assignations_path,
        assign_path=assign_path,
    )

    # Create and set the lifespan context manager
    @contextlib.asynccontextmanager
    async def lifespan(fastapi_app: FastAPI):
        """Lifespan context manager for FastAPI app using FastApiAgent."""
        # Add dynamic routes at startup (after all functions are registered)
        if add_implementations:
            add_implementation_routes(fastapi_app, agent, extension)

        if add_states:
            add_state_routes(fastapi_app, agent, states_path, states_ws_path)

        if add_schema:
            add_schema_routes(fastapi_app, agent, extension)

        configure_openapi(fastapi_app)

        # Set agent on app state
        fastapi_app.state.agent = agent

        async with agent:
            provide_task = asyncio.create_task(agent.aprovide(instance_id=instance_id))
            provide_task.add_done_callback(_handle_provide_task_done)

            yield

            provide_task.cancel()
            try:
                await provide_task
            except asyncio.CancelledError:
                logger.info("Provide task cancelled during shutdown")
            except Exception as e:
                logger.error(f"Error during provide task shutdown: {e}", exc_info=True)

    # Set the lifespan on the app's router
    app.router.lifespan_context = lifespan

    return agent
