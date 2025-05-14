

from rekuest_next.agents.hooks.background import background
from rekuest_next.agents.context import context


@context
class Hallo:
    id: str

@background
def hello(hallo: Hallo) -> None:
    print("Hello", hallo.id)