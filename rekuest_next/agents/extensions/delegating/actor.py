import logging
from rekuest_next.actors.base import Actor
from rekuest_next.actors.transport.types import AssignTransport
from rekuest_next.agents.extensions.delegating.protocol import (
    AssignMessage,
    DoneMessage,
    ErrorMessage,
)
from rekuest_next.agents.extensions.delegating.transport import ProcessTransport
from rekuest_next.api.schema import AssignationEventKind, DefinitionInput
from rekuest_next.collection.collector import Collector
from rekuest_next.messages import Assign
from rekuest_next.structures.parse_collectables import parse_collectable


logger = logging.getLogger(__name__)


class CLIActor(Actor):
    process_transport: ProcessTransport
    interface: str
    definition: DefinitionInput

    async def on_assign(
        self,
        assignment: Assign,
        collector: Collector,
        transport: AssignTransport,
    ):
        await transport.log_event(
            kind=AssignationEventKind.QUEUED,
            message="Queued for running",
        )

        async with self.sync:
            try:
                await transport.log_event(
                    kind=AssignationEventKind.ASSIGN,
                    message="Assigned to actor",
                )

                await self.process_transport.asend_message(
                    AssignMessage(interface=self.interface, kwargs={**assignment.args})
                )

                while True:
                    message = await self.process_transport.aget_next_message()

                    logger.info(f"Received message after assignment {message}")

                    if isinstance(message, DoneMessage):

                        collector.register(
                            assignment,
                            parse_collectable(self.definition, message.returns),
                        )
                        await transport.log_event(
                            kind=AssignationEventKind.YIELD,
                            returns=message.returns,
                        )

                        await transport.log_event(
                            kind=AssignationEventKind.DONE,
                        )
                    elif isinstance(message, ErrorMessage):
                        raise Exception("Received error message", message)

                    else:
                        raise Exception("Invalid message", message)

            except AssertionError as ex:
                logger.critical("Assignation error", exc_info=True)
                await transport.log_event(
                    kind=AssignationEventKind.CRITICAL,
                    message=str(ex),
                )

            except Exception as e:
                logger.critical("Assignation error", exc_info=True)
                await transport.log_event(
                    kind=AssignationEventKind.CRITICAL,
                    message=repr(e),
                )
