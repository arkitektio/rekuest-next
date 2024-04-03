from rekuest_next.api.schema import DefinitionInput, DefinitionFragment
import json
import hashlib


def auto_validate(defintion: DefinitionInput) -> DefinitionFragment:
    """Validates a definition against its own schema

    This should always be the first step in the validation process
    but does not guarantee that the definition is valid on the connected
    arkitekt service. That means that the definition might be valid
    within this client (e.g. you can access and assign to actors in this
    context, but the arkitekt service might not be able to adress your actor
    or assign to it.)

    """

    return DefinitionFragment(**defintion.dict(by_alias=True))


def hash_definition(definition: DefinitionInput):
    hashable_definition = {
        key: value
        for key, value in dict(definition.dict()).items()
        if key not in ["meta", "interface"]
    }
    return hashlib.sha256(
        json.dumps(hashable_definition, sort_keys=True).encode()
    ).hexdigest()
