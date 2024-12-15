import importlib
import os
import pkgutil
import traceback
import logging
from rekuest_next.structures.registry import StructureRegistry

DEFAULT_STRUCTURE_REGISTRY = None


async def id_shrink(object: object) -> str:
    try:
        return object.id
    except AttributeError:
        raise Exception(f"Object {object} does not have an id attribute")


def check_and_import_structures(
    structur_reg: "StructureRegistry",
) -> "StructureRegistry":
    """Check and import extensions from local modules and installed packages.

    It will look for __rekuest__.py files in the current working directory and installed packages.
    If found, it will call the init_extensions function from the module and pass the structure registry to it.
    Also it will call the register_structures function from the module if it exists, registering structures in the structure registry.

    Args:
        structur_reg (StructureRegistry): The structure registry to pass to the extensions.

    Returns:
        Dict[str, AgentExtension]: A dictionary of the imported extensions.
    """

    # Function to load and call init_extensions from __rekuest__.py
    def load_and_call_init_extensions(module_name, rekuest_path):
        try:
            spec = importlib.util.spec_from_file_location(
                f"{module_name}.__rekuest__", rekuest_path
            )
            rekuest_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rekuest_module)
            at_least_one = False
            if hasattr(rekuest_module, "register_structures"):
                at_least_one = True

                rekuest_module.register_structures(structur_reg)
                logging.info(
                    f"Called register_structures function from {module_name}.__rekuest__ with result"
                )

            if hasattr(rekuest_module, "init_extensions"):
                at_least_one = True
                logging.info(
                    f"Called init_extensions function from {module_name}.__rekuest__"
                )

            if not at_least_one:
                logging.warning(
                    f"No init_extensions or register_structures function found in {module_name}.__rekuest__. This module will not be used."
                )

        except Exception as e:
            raise Exception(
                f"Failed to call init_extensions for {module_name}: {e}"
            ) from e

    # Check local modules in the current working directory
    current_directory = os.getcwd()
    for item in os.listdir(current_directory):
        item_path = os.path.join(current_directory, item)
        if os.path.isdir(item_path) and os.path.isfile(
            os.path.join(item_path, "__init__.py")
        ):
            rekuest_path = os.path.join(item_path, "__rekuest__.py")
            if os.path.isfile(rekuest_path):
                load_and_call_init_extensions(item, rekuest_path)

    # Check installed packages
    for _, module_name, _ in pkgutil.iter_modules():
        try:
            module_spec = importlib.util.find_spec(module_name)
            if module_spec and module_spec.origin:
                rekuest_path = os.path.join(
                    os.path.dirname(module_spec.origin), "__rekuest__.py"
                )
                if os.path.isfile(rekuest_path):
                    load_and_call_init_extensions(module_name, rekuest_path)
        except Exception as e:
            print(
                f"Failed to call init_extensions for installed package {module_name}: {e}"
            )
            traceback.print_exc()

    return structur_reg


def get_default_structure_registry() -> StructureRegistry:
    global DEFAULT_STRUCTURE_REGISTRY
    if not DEFAULT_STRUCTURE_REGISTRY:
        DEFAULT_STRUCTURE_REGISTRY = StructureRegistry()

        DEFAULT_STRUCTURE_REGISTRY = check_and_import_structures(
            DEFAULT_STRUCTURE_REGISTRY
        )

    return DEFAULT_STRUCTURE_REGISTRY
