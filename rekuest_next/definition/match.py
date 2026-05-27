from rekuest_next.api.schema import ArgPortInput, PortMatchInput, ReturnPortInput


def build_port_match(
    index: int,
    port: ArgPortInput | ReturnPortInput,
) -> PortMatchInput:
    return PortMatchInput(
        at=index,
        key=port.key,
        identifier=port.identifier,
        kind=port.kind,
        nullable=port.nullable,
        children=build_port_matches(port.children or ()),
    )


def build_port_matches(
    ports: tuple[ArgPortInput, ...] | tuple[ReturnPortInput, ...],
) -> tuple[PortMatchInput, ...] | None:
    return (
        tuple(build_port_match(index, port) for index, port in enumerate(ports)) or None
    )
