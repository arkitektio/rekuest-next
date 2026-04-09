from rekuest_next.register import register
from rekuest_next.declare import agent_protocol


@agent_protocol("Agent")
class Agent:
    """An example agent protocol with a static method."""

    @staticmethod
    def add(int: int) -> int:
        """A function that adds 1 to the input integer."""
        ...


@agent_protocol("AnotherAgent")
class AnotherAgent:
    """Another example agent protocol with a static method."""

    @staticmethod
    def substract(int: int) -> int:
        """A function that substracts 1 from the input integer."""
        ...


@register
def workflow(
    agent_a: Agent,
    agent_b: AnotherAgent,
    number: int,
) -> int:
    """A workflow that returns a static string."""

    x = Agent.add(number)
    y = AnotherAgent.substract(x)
    return y
