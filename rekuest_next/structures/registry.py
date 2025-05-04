"""The structure registry is a registry for all structures that are used in the system."""

import contextvars
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    OrderedDict,
    Type,
    TypeVar,
)

from pydantic import BaseModel, ConfigDict, Field

from rekuest_next.api.schema import (
    AssignWidgetInput,
    ChoiceInput,
    EffectInput,
    PortInput,
    PortKind,
    ReturnWidgetInput,
    ValidatorInput,
)
from rekuest_next.structures.utils import build_instance_predicate

from .errors import (
    StructureDefinitionError,
    StructureRegistryError,
)
from .hooks.default import get_default_hooks
from .hooks.errors import HookError
from .hooks.types import RegistryHook
from .types import (
    FullFilledStructure,
    FullFilledType,
    FullFilledEnum,
    FullFilledModel,
    FullFilledMemoryStructure,
    Predicator,
)

current_structure_registry = contextvars.ContextVar("current_structure_registry")


T = TypeVar("T")


class StructureRegistry(BaseModel):
    """A registry for structures.

    Structure registries are used to provide a mapping from "identifier" to python
    classes and vice versa.

    When an actors receives a request from the arkitekt server with a specific
    id Y and identifier X, it will look up the structure registry for the identifier X
    and use the corresponding python class to deserialize the data.

    The structure registry is also used to provide a mapping from python classes to identifiers

    """

    copy_from_default: bool = False
    allow_overwrites: bool = True
    allow_auto_register: bool = True
    registry_hooks: OrderedDict[str, RegistryHook] = Field(
        default_factory=get_default_hooks,
        description="""If the structure registry is challenged, 
        with a new structure (i.e a python Object that is not yet registered, it will try to find a hook 
        that is able to register this structure. If no hook is found, it will raise an error.
        The default hooks are the enum and the dataclass hook. You can add your own hooks by adding them to this list.""",
    )
    identifier_structure_map: Dict[str, FullFilledStructure] = Field(
        default_factory=dict, exclude=True
    )
    identifier_enum_map: Dict[str, FullFilledStructure] = Field(default_factory=dict, exclude=True)
    identifier_memory_structure_map: Dict[str, FullFilledMemoryStructure] = Field(
        default_factory=dict, exclude=True
    )
    identifier_model_map: Dict[str, Type] = Field(default_factory=dict, exclude=True)
    cls_fullfilled_type_map: Dict[Type, FullFilledType] = Field(
        default_factory=dict, exclude=True
    )  # Map from class to fullfilled type

    _token: contextvars.Token = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_fullfilled_structure(self, identifier: str) -> FullFilledStructure:
        """Get the fullfilled structure for a given identifier."""
        return self.identifier_structure_map[identifier]

    def get_fullfilled_enum(self, identifier: str) -> FullFilledEnum:
        """Get the fullfilled enum for a given identifier."""
        return self.identifier_enum_map[identifier]

    def get_fullfilled_model(self, identifier: str) -> FullFilledModel:
        """Get the fullfilled model for a given identifier."""
        return self.identifier_model_map[identifier]

    def get_fullfilled_memory_structure(self, identifier: str) -> FullFilledMemoryStructure:
        """Get the fullfilled memory structure for a given identifier."""
        return self.identifier_memory_structure_map[identifier]

    def auto_register(self, cls: Type) -> FullFilledType:
        """Auto register a class.

        This uses the registry hooks to find a hook that is able to register the class.
        If no hook is found, it will raise an error.

        Args:
            cls (Type): The class to register.

        Returns:
            FullFilledStructure: The fullfilled structure that was created.


        Raises:
            StructureDefinitionError: If no hook was able to register the class.
        """
        for key, hook in self.registry_hooks.items():
            try:
                if hook.is_applicable(cls):
                    try:
                        fullfilled_type = hook.apply(cls)
                        self.fullfill_registration(fullfilled_type)
                        return fullfilled_type
                    except HookError as e:
                        raise StructureDefinitionError(
                            f"Hook {key} failed to apply to {cls}"
                        ) from e
            except Exception as e:
                raise StructureDefinitionError(
                    f"Hook {key} does not correctly implement its interface. Please contact the developer of this hook."
                ) from e

        raise StructureDefinitionError(
            f"No hook was able to register {cls}. Please make sure to register this type beforehand or set allow_auto_register to True"
        )

    def get_identifier_for_cls(self, cls: Type) -> str:
        """Get the identifier for a given class.

        This will use the structure registry to find the correct
        identifier for the given class.

        Args:
            cls (Type): The class to get the identifier for.
        Returns:
            str: The identifier for the given class.
        Raises:
            StructureRegistryError: If the class is not registered.
        """
        try:
            return self.cls_fullfilled_type_map[cls].identifier
        except KeyError as e:
            raise StructureRegistryError(f"Identifier for {cls} is not registered") from e

    def register_as_model(
        self,
        cls: Type,
        identifier: str,
        predicate: Predicator | None = None,
    ) -> None:
        """Register a class as a model."""

        fullfile_type = FullFilledModel(
            cls=cls,
            identifier=identifier,
            predicate=predicate or build_instance_predicate(cls),
        )

        self.fullfill_registration(fullfile_type)

    def register_as_enum(self, cls: Type, identifier: str, choices: list[ChoiceInput]) -> None:
        """Register a class as an enum."""
        fullfile_type = FullFilledEnum(
            cls=cls,
            identifier=identifier,
            choices=choices,
            predicate=build_instance_predicate(cls),
        )

        self.fullfill_registration(fullfile_type)

    def register_as_structure(
        self,
        cls: Type,
        identifier: str,
        aexpand: Callable[
            [
                str,
            ],
            Awaitable[Any],
        ]
        | None = None,
        ashrink: Callable[
            [
                Any,
            ],
            Awaitable[str],
        ]
        | None = None,
        predicate: Callable[[Any], bool] | None = None,
        convert_default: Callable[[Any], str] | None = None,
        description: Optional[str] = None,
        default_widget: Optional[AssignWidgetInput] = None,
        default_returnwidget: Optional[ReturnWidgetInput] = None,
    ) -> FullFilledStructure:
        """Register a class as a structure.

        This will create a new structure and register it in the registry.
        This function should be called when you want to specifically register a class
        as a structure. This will mainly be used for classes that are global
        and should be registered as a structure.

        Args:
            cls (Type): The class to register
            identifier (str): The identifier of the class. This should be unique and will be send to the rekuest server
            scope (PortScope, optional): The scope of the port. Defaults to PortScope.LOCAL.
            aexpand (Callable[ [ str, ], Awaitable[Any], ] | None, optional): An expander (needs to be set for a GLOBAL). Defaults to None.
            ashrink (Callable[ [ Any, ], Awaitable[str], ] | None, optional): A shrinker (needs to be set for a GLOBAL). Defaults to None.
            predicate (Callable[[Any], bool] | None, optional): A predicate that will check if its an instance of this type (will autodefault to the issinstance check). Defaults to None.
            convert_default (Callable[[Any], str] | None, optional): A way to convert the default. Defaults to None.
            default_widget (Optional[AssignWidgetInput], optional): A widget that will be used as a default. Defaults to None.
            default_returnwidget (Optional[ReturnWidgetInput], optional): A return widget that will be used as a default. Defaults to None.

        Returns:
            FullFilledStructure: The fullfilled structure that was created
        """
        fs = FullFilledStructure(
            cls=cls,
            identifier=identifier,
            aexpand=aexpand,
            ashrink=ashrink,
            description=description,
            convert_default=convert_default,
            predicate=predicate or build_instance_predicate(cls),
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
        self.fullfill_registration(fs)
        return fs

    def get_fullfilled_type_for_cls(self, cls: Type) -> FullFilledType:
        """Get the fullfilled structure for a given class.
        This will use the structure registry to find the correct
        structure for the given class.

        """
        try:
            return self.cls_fullfilled_type_map[cls]
        except KeyError:
            if self.allow_auto_register:
                try:
                    return self.auto_register(cls)
                except StructureDefinitionError as e:
                    raise StructureDefinitionError(
                        f"{cls} was not registered and could not be registered automatically"
                    ) from e
            else:
                raise StructureRegistryError(
                    f"{cls} is not registered and allow_auto_register is set to False."
                    " Please make sure to register this type beforehand or set"
                    " allow_auto_register to True"
                )

    def fullfill_registration(
        self,
        fullfilled_type: FullFilledType,
    ) -> None:
        """Fullfill the registration of a structure.

        Sets the structure in the registry and checks if the structure is already registered.
        If it is already registered, it will raise an error.

        Args:
            fullfilled_structure (FullFilledStructure): The fullfilled structure to register
        """
        self.cls_fullfilled_type_map[fullfilled_type.cls] = fullfilled_type

        if isinstance(fullfilled_type, FullFilledModel):
            self.identifier_model_map[fullfilled_type.identifier] = fullfilled_type
            return

        if isinstance(fullfilled_type, FullFilledEnum):
            self.identifier_enum_map[fullfilled_type.identifier] = fullfilled_type
            return

        if isinstance(fullfilled_type, FullFilledMemoryStructure):
            self.identifier_memory_structure_map[fullfilled_type.identifier] = fullfilled_type
            return

        if isinstance(fullfilled_type, FullFilledStructure):
            self.identifier_structure_map[fullfilled_type.identifier] = fullfilled_type
            return

        raise StructureRegistryError(
            f"Could not register {fullfilled_type} as it is not a FullFilledStructure"
            f" or a FullFilledEnum or a FullFilledMemoryStructure"
        )

    def get_port_for_cls(
        self,
        cls: Type,
        key: str,
        nullable: bool = False,
        description: Optional[str] = None,
        effects: Optional[list[EffectInput]] = None,
        label: Optional[str] = None,
        validators: Optional[List[ValidatorInput]] = None,
        default: Any = None,  # noqa: ANN401
        assign_widget: Optional[AssignWidgetInput] = None,
        return_widget: Optional[ReturnWidgetInput] = None,
    ) -> PortInput:
        """Create a port for a given class

        This will use the structure registry to find the correct
        structure for the given class. It will then create a port
        for this class. You can pass overwrites if the port
        should not be created with the default values.
        """

        fullfilled_type = self.get_fullfilled_type_for_cls(cls)

        if isinstance(fullfilled_type, FullFilledModel):
            return PortInput(
                kind=PortKind.MODEL,
                identifier=fullfilled_type.identifier,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                key=key,
                label=label,
                default=fullfilled_type.convert_default(default) if default is not None else None,
                nullable=nullable,
                effects=effects or [],
                description=fullfilled_type.description,
                validators=validators or [],
            )

        elif isinstance(fullfilled_type, FullFilledEnum):
            return PortInput(
                kind=PortKind.ENUM,
                identifier=fullfilled_type.identifier,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                choices=fullfilled_type.choices,
                key=key,
                label=label,
                default=fullfilled_type.convert_default(default) if default is not None else None,
                nullable=nullable,
                effects=effects or [],
                description=fullfilled_type.description,
                validators=validators or [],
            )

        elif isinstance(fullfilled_type, FullFilledMemoryStructure):
            return PortInput(
                kind=PortKind.MEMORY_STRUCTURE,
                identifier=fullfilled_type.identifier,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                key=key,
                label=label,
                default=fullfilled_type.convert_default(default) if default is not None else None,
                nullable=nullable,
                effects=effects or [],
                description=fullfilled_type.description,
                validators=validators or [],
            )

        elif isinstance(fullfilled_type, FullFilledStructure):
            return PortInput(
                kind=PortKind.STRUCTURE,
                identifier=fullfilled_type.identifier,
                assignWidget=assign_widget or fullfilled_type.default_widget,
                returnWidget=return_widget or fullfilled_type.default_returnwidget,
                key=key,
                label=label,
                default=fullfilled_type.convert_default(default) if default is not None else None,
                nullable=nullable,
                effects=effects or [],
                description=description or fullfilled_type.description,
                validators=validators or [],
            )

        else:
            raise StructureRegistryError(
                f"Could not create port for {cls} as it is not a FullFilledStructure"
                f" or a FullFilledEnum or a FullFilledMemoryStructure"
            )


DEFAULT_STRUCTURE_REGISTRY: StructureRegistry | None = None
