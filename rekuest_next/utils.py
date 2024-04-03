from typing import Any
from rekuest_next.actors.vars import get_current_assignation_helper


def useUser() -> str:
    """Use the current User

    Returns:
        User: The current User
    """
    helper = get_current_assignation_helper()
    return helper.assignation.user
