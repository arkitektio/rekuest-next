try:
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
    from reaktion_next.extension import ReaktionExtension

    from rekuest_next.agents.base import BaseAgent
    from fakts import Fakts
    from herre import Herre
    from rekuest_next.postmans.graphql import GraphQLPostman
    from arkitekt_next.service_registry import (
        get_default_service_builder_registry,
        Params,
    )
    from arkitekt_next.model import Requirement

    class ArkitektNextRekuestNext(RekuestNext):
        rath: RekuestNextRath
        agent: BaseAgent

    def builder(fakts: Fakts, herre: Herre, params: Params) -> ArkitektNextRekuestNext:
        instance_id = params.get("instance_id", "default")

        rath = RekuestNextRath(
            link=RekuestNextLinkComposition(
                auth=HerreAuthLink(herre=herre),
                split=SplitLink(
                    left=FaktsAIOHttpLink(fakts_group="rekuest", fakts=fakts),
                    right=FaktsGraphQLWSLink(fakts_group="rekuest", fakts=fakts),
                    split=lambda o: o.node.operation != OperationType.SUBSCRIPTION,
                ),
            )
        )

        agent = BaseAgent(
            transport=ArkitektWebsocketAgentTransport(
                fakts_group="rekuest.agent", fakts=fakts, herre=herre
            ),
            instance_id=instance_id,
            rath=rath,
        )

        try:
            from reaktion_next.extension import ReaktionExtension

            agent.extensions["reaktion"] = ReaktionExtension()
        except ImportError as e:
            raise e

        return ArkitektNextRekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
                instance_id=instance_id,
            ),
        )

    service_builder_registry = get_default_service_builder_registry()
    service_builder_registry.register(
        "rekuest",
        builder,
        Requirement(
            service="live.arkitekt.rekuest",
            description="An instance of ArkitektNext Rekuest to assign to nodes",
        ),
    )
    imported = True


except ImportError as e:
    imported = False
    raise e
