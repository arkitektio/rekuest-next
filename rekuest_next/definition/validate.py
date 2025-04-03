import hashlib
import json

from rekuest_next.api.schema import Definition, DefinitionInput


def auto_validate(defintion: DefinitionInput) -> Definition:
    """Validates a definition against its own schema

    This should always be the first step in the validation process
    but does not guarantee that the definition is valid on the connected
    arkitekt service. That means that the definition might be valid
    within this client (e.g. you can access and assign to actors in this
    context, but the arkitekt service might not be able to adress your actor
    or assign to it.)

    """

    hm = defintion.model_dump(by_alias=True)
    
    # Get rid of the widgets (th)
    for arg in hm["args"]:
        arg["assignWidget"] = None
        arg["returnWidget"] = None
        
    for re in hm["returns"]:
        re["assignWidget"] = None
        re["returnWidget"] = None
        
        
    print(hm)
    # Caveat: The following fields are not necessary for the actor
    # definition and are by default set to rekuest_next instances (i.e GraphQL Objects)
    # in the definition. As such we set them to empty lists here
    hm["interfaces"] = []
    hm["collections"] = []
    hm["isTestFor"] = []

    return Definition(**hm)


def hash_definition(definition: DefinitionInput):
    hashable_definition = {
        key: value
        for key, value in definition.model_dump().items()
        if key
        in [
            "name",
            "description",
            "args",
            "returns",
            "stateful",
            "is_test_for",
            "collections",
        ]
    }
    return hashlib.sha256(
        json.dumps(hashable_definition, sort_keys=True).encode()
    ).hexdigest()
