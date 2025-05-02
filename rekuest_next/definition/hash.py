"""hash definitions"""

import hashlib
import json

from rekuest_next.api.schema import DefinitionInput


def hash_definition(definition: DefinitionInput) -> str:
    """Hash a definition"""
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
    return hashlib.sha256(json.dumps(hashable_definition, sort_keys=True).encode()).hexdigest()
