from rekuest_next.register import register
from rekuest_next.declare import agent_protocol


@agent_protocol
class Agent:
    """An example agent protocol with a static method."""

    @staticmethod
    def add(int: int) -> int:
        """A function that adds 1 to the input integer."""
        ...


@agent_protocol
class AnotherAgent:
    """Another example agent protocol with a static method."""

    @staticmethod
    def substract(int: int) -> int:
        """A function that substracts 1 from the input integer."""
        ...


@register(dependencies=[AnotherAgent, Agent])
def workflow(
    number: int,
) -> int:
    """A workflow that returns a static string."""

    x = Agent.add(number)
    y = AnotherAgent.substract(x)
    return y
