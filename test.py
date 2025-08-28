from rekuest_next.register import register
from rekuest_next.declare import declare


@declare
def add(int: int) -> int:
    """A function that adds 1 to the input integer."""
    ...


@declare
def substract(int: int) -> int:
    """A function that adds 1 to the input integer."""
    ...


@register(dependencies=[add, substract])
def workflow(number: int) -> int:
    """A workflow that returns a static string."""

    x = add(1)
    y = substract(x)

    return y
