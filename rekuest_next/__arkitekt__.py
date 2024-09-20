import importlib
import os
import pkgutil
import traceback
from typing import Any, Dict
import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from rekuest_next.agents.extension import AgentExtension
    from rekuest_next.structures.registry import StructureRegistry


def check_and_import_extensions(
    structur_reg: "StructureRegistry",
) -> Dict[str, "AgentExtension"]:
    """Check and import extensions from local modules and installed packages.

    It will look for __rekuest__.py files in the current working directory and installed packages.
    If found, it will call the init_extensions function from the module and pass the structure registry to it.
    Also it will call the register_structures function from the module if it exists, registering structures in the structure registry.

    Args:
        structur_reg (StructureRegistry): The structure registry to pass to the extensions.

    Returns:
        Dict[str, AgentExtension]: A dictionary of the imported extensions.
    """

    results = {}

    # Function to load and call init_extensions from __rekuest__.py
    def load_and_call_init_extensions(module_name, rekuest_path):
        try:
            spec = importlib.util.spec_from_file_location(
                f"{module_name}.__rekuest__", rekuest_path
            )
            rekuest_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rekuest_module)
            at_least_one = False
            if hasattr(rekuest_module, "init_extensions"):
                at_least_one = True
                result = rekuest_module.init_extensions(structur_reg)
                results[module_name] = result
                logging.info(
                    f"Called init_extensions function from {module_name}.__rekuest__ with result: {result}"
                )
            if hasattr(rekuest_module, "register_structures"):
                at_least_one = True

                rekuest_module.register_structures(structur_reg)
                logging.info(
                    f"Called register_structures function from {module_name}.__rekuest__ with result"
                )
            if not at_least_one:
                logging.warning(
                    f"No init_extensions or register_structures function found in {module_name}.__rekuest__. This module will not be used."
                )

        except Exception as e:
            raise Exception(
                f"Failed to call init_extensions for {module_name}: {e}"
            ) from e

    # Check local modules in the current working directory
    current_directory = os.getcwd()
    for item in os.listdir(current_directory):
        item_path = os.path.join(current_directory, item)
        if os.path.isdir(item_path) and os.path.isfile(
            os.path.join(item_path, "__init__.py")
        ):
            rekuest_path = os.path.join(item_path, "__rekuest__.py")
            if os.path.isfile(rekuest_path):
                load_and_call_init_extensions(item, rekuest_path)

    # Check installed packages
    for _, module_name, _ in pkgutil.iter_modules():
        try:
            module_spec = importlib.util.find_spec(module_name)
            if module_spec and module_spec.origin:
                rekuest_path = os.path.join(
                    os.path.dirname(module_spec.origin), "__rekuest__.py"
                )
                if os.path.isfile(rekuest_path):
                    load_and_call_init_extensions(module_name, rekuest_path)
        except Exception as e:
            print(
                f"Failed to call init_extensions for installed package {module_name}: {e}"
            )
            traceback.print_exc()

    return results


def init_services(service_builder_registry):
    from rath.contrib.fakts.links.aiohttp import FaktsAIOHttpLink
    from rath.links.split import SplitLink
    from rath.contrib.fakts.links.graphql_ws import FaktsGraphQLWSLink
    from rath.contrib.herre.links.auth import HerreAuthLink
    from rekuest_next.rath import RekuestNextLinkComposition, RekuestNextRath
    from rekuest_next.rekuest import RekuestNext
    from graphql import OperationType
    from rekuest_next.contrib.arkitekt.websocket_agent_transport import (
        ArkitektWebsocketAgentTransport,
    )
    from rekuest_next.agents.base import BaseAgent
    from fakts import Fakts
    from herre import Herre
    from rekuest_next.postmans.graphql import GraphQLPostman
    from rekuest_next.agents.extensions.default import DefaultExtension

    from .structures.default import get_default_structure_registry
    from .api.schema import (
        AssignationEventFragment,
        aget_event,
        NodeFragment,
        afind,
        Search_nodesQuery,
    )
    from rekuest_next.structures.hooks.standard import id_shrink
    from rekuest_next.widgets import SearchWidget
    from arkitekt_next.model import Requirement

    from arkitekt_next.model import Manifest

    class ArkitektNextRekuestNext(RekuestNext):
        rath: RekuestNextRath
        agent: BaseAgent

    structur_reg = get_default_structure_registry()

    extensions = check_and_import_extensions(structur_reg)

    def builder(
        fakts: Fakts, herre: Herre, params: Dict[str, Any], manifest: Manifest
    ) -> ArkitektNextRekuestNext:
        instance_id = params.get("instance_id", "default")

        rath = RekuestNextRath(
            link=RekuestNextLinkComposition(
                auth=HerreAuthLink(herre=herre),
                split=SplitLink(
                    left=FaktsAIOHttpLink(
                        fakts_group="rekuest", fakts=fakts, endpoint_url="FAKE_URL"
                    ),
                    right=FaktsGraphQLWSLink(
                        fakts_group="rekuest", fakts=fakts, ws_endpoint_url="FAKE_URL"
                    ),
                    split=lambda o: o.node.operation != OperationType.SUBSCRIPTION,
                ),
            )
        )

        agent = BaseAgent(
            transport=ArkitektWebsocketAgentTransport(
                fakts_group="rekuest.agent",
                fakts=fakts,
                herre=herre,
                endpoint_url="FAKE_URL",
                instance_id=instance_id,
            ),
            instance_id=instance_id,
            rath=rath,
            name=f"{manifest.identifier}:{manifest.version}",
        )

        for extension_name, extension in extensions.items():
            agent.extensions[extension_name] = extension

        return ArkitektNextRekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
                instance_id=instance_id,
            ),
        )

    service_builder_registry.register(
        "rekuest",
        builder,
        Requirement(
            service="live.arkitekt.rekuest",
            description="An instance of ArkitektNext Rekuest to assign to nodes",
        ),
    )

    return None
