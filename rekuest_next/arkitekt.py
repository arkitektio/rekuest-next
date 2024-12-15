import json
import os
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

from .structures.default import get_default_structure_registry
from arkitekt_next.base_models import Requirement
from arkitekt_next.service_registry import Params, BaseArkitektService
from arkitekt_next.base_models import Manifest
from arkitekt_next.service_registry import (
    get_default_service_registry,
)


if TYPE_CHECKING:
    pass


class ArkitektNextRekuestNext(RekuestNext):
    rath: RekuestNextRath
    agent: BaseAgent


def build_relative_path(*path: str) -> str:
    return os.path.join(os.path.dirname(__file__), *path)


class RekuestNextService(BaseArkitektService):

    def __init__(self):
        self.structure_reg = get_default_structure_registry()

    def get_service_name(self):
        return "rekuest"

    def build_service(
        self, fakts: Fakts, herre: Herre, params: Params, manifest: Manifest
    ):
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


get_default_service_registry().register(RekuestNextService())