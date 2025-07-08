from rekuest_next.agents.hooks.background import background
from rekuest_next.agents.context import context


@context
class Hallo:
    id: str


@background
def hello(hallo: Hallo) -> None:
    """A background function that prints the id of Hallo."""
    print("Hello", hallo.id)
