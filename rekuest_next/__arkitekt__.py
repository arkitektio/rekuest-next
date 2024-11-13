import importlib
import json
import os
import pkgutil
import traceback
from typing import Any, Dict
import logging
from typing import TYPE_CHECKING
from rath.links.split import SplitLink
from fakts_next.contrib.rath.aiohttp import FaktsAIOHttpLink
from fakts_next.contrib.rath.graphql_ws import FaktsGraphQLWSLink
from herre_next.contrib.rath.auth_link import HerreAuthLink
from rekuest_next.rath import RekuestNextLinkComposition, RekuestNextRath
from rekuest_next.rekuest import RekuestNext
from graphql import OperationType
from rekuest_next.contrib.arkitekt.websocket_agent_transport import (
    ArkitektWebsocketAgentTransport,
)
from rekuest_next.agents.base import BaseAgent
from fakts_next import Fakts
from herre_next import Herre
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.agents.extensions.default import DefaultExtension

from .structures.default import get_default_structure_registry
from rekuest_next.structures.hooks.standard import id_shrink
from rekuest_next.widgets import SearchWidget
from arkitekt_next.base_models import Requirement
from arkitekt_next.service_registry import (
    Params,
    BaseArkitektService
)
from arkitekt_next.base_models import Manifest


if TYPE_CHECKING:
    from rekuest_next.agents.extension import AgentExtension
    from rekuest_next.structures.registry import StructureRegistry

class ArkitektNextRekuestNext(RekuestNext):
    rath: RekuestNextRath
    agent: BaseAgent




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


def build_relative_path(*path: str) -> str:
    return os.path.join(os.path.dirname(__file__), *path)



class RekuestNextService(BaseArkitektService):


    def __init__(self):
        self.structure_reg = get_default_structure_registry()
        self.extensions = check_and_import_extensions(self.structure_reg)

    def get_service_name(self):
        return "rekuest"
    
    def build_service(self, fakts: Fakts, herre: Herre, params: Params, manifest: Manifest):
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

        for extension_name, extension in self.extensions.items():
            agent.extensions[extension_name] = extension

        return ArkitektNextRekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
                instance_id=instance_id,
            ),
        )
    
    def get_requirements(self):
        return [
            Requirement(
                key="rekuest",
                service="live.arkitekt.rekuest",
                description="An instance of ArkitektNext Rekuest to assign to nodes",
            )
        ]
    
    def get_graphql_schema(self):
        schema_graphql_path = build_relative_path("api", "schema.graphql")
        with open(schema_graphql_path) as f:
            return f.read()
        
    def get_turms_project(self):
        turms_prject = build_relative_path("api", "project.json")
        with open(turms_prject) as f:
            return json.loads(f.read())




def build_services():
    return [RekuestNextService()]