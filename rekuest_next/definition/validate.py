import hashlib
import json

from rekuest_next.api.schema import DefinitionFragment, DefinitionInput


def auto_validate(defintion: DefinitionInput) -> DefinitionFragment:
    """Validates a definition against its own schema

    This should always be the first step in the validation process
    but does not guarantee that the definition is valid on the connected
    arkitekt service. That means that the definition might be valid
    within this client (e.g. you can access and assign to actors in this
    context, but the arkitekt service might not be able to adress your actor
    or assign to it.)

    """

    hm = defintion.model_dump(by_alias=True)
    del hm["interfaces"]

    return DefinitionFragment(**hm)


def hash_definition(definition: DefinitionInput):
    hashable_definition = {
        key: value
        for key, value in definition.model_dump().items()
        if key in ["name", "description", "args", "returns"]
    }
    return hashlib.sha256(
        json.dumps(hashable_definition, sort_keys=True).encode()
    ).hexdigest()
