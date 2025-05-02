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
    EffectInput,
    PortInput,
    PortKind,
    PortScope,
    ReturnWidgetInput,
    ValidatorInput,
)
from rekuest_next.structures.utils import build_instance_predicate

from .errors import (
    StructureDefinitionError,
    StructureOverwriteError,
    StructureRegistryError,
)
from .hooks.default import get_default_hooks
from .hooks.errors import HookError
from .hooks.types import RegistryHook
from .types import FullFilledStructure, Predicator, Shrinker, Expander, DefaultConverter

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

    identifier_structure_map: Dict[str, Type] = Field(default_factory=dict, exclude=True)
    identifier_port_scope_map: Dict[str, PortScope] = Field(default_factory=dict, exclude=True)
    _identifier_expander_map: Dict[str, Shrinker] = {}
    _identifier_shrinker_map: Dict[str, Expander] = {}
    _identifier_predicate_map: Dict[str, Predicator] = {}

    _identifier_model_map: Dict[str, Type] = {}
    _model_identifier_map: Dict[Type, str] = {}

    _structure_convert_default_map: Dict[str, DefaultConverter] = {}
    _structure_identifier_map: Dict[Type, str] = {}
    _structure_default_widget_map: Dict[Type, AssignWidgetInput] = {}
    _structure_default_returnwidget_map: Dict[Type, ReturnWidgetInput] = {}
    _structure_annotation_map: Dict[Type, Type] = {}

    _fullfilled_structures_map: Dict[Type, FullFilledStructure] = {}

    _token: contextvars.Token = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_expander_for_identifier(self, identifier: str) -> Expander:
        """Get the expander for a given identifier.

        This will use the structure registry to find the correct
        expander for the given identifier.

        Args:
            identifier (str): The identifier to get the expander for.
        Returns:
            Expander: The expander for the given identifier.

        Raises:
            StructureRegistryError: If the identifier is not registered.
        """

        try:
            return self._identifier_expander_map[identifier]
        except KeyError as e:
            raise StructureRegistryError(f"Expander for {identifier} is not registered") from e

    def get_shrinker_for_identifier(self, identifier: str) -> Shrinker:
        """Get the shrinker for a given identifier.

        This will use the structure registry to find the correct
        shrinker for the given identifier.
        Args:
            identifier (str): The identifier to get the shrinker for.

        Returns:
            Shrinker: The shrinker for the given identifier.

        Raises:
            StructureRegistryError: If the identifier is not registered.
        """
        try:
            return self._identifier_shrinker_map[identifier]
        except KeyError as e:
            raise StructureRegistryError(f"Shrinker for {identifier} is not registered") from e

    def get_predicator_for_identifier(self, identifier: str) -> Predicator:
        """Get the predicators for a given identifier.

        This will use the structure registry to find the correct
        predicators for the given identifier.
        Args:
            identifier (str): The identifier to get the shrinker for.

        Returns:
            Predicator: The shrinker for the given identifier.

        Raises:
            StructureRegistryError: If the identifier is not registered.
        """
        try:
            return self._identifier_predicate_map[identifier]
        except KeyError as e:
            raise StructureRegistryError(f"Predicator for {identifier} is not registered") from e

    def auto_register(self, cls: Type) -> FullFilledStructure:
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
                        fullfilled_structure = hook.apply(cls)
                        self.fullfill_registration(fullfilled_structure)
                        return fullfilled_structure
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
            return self._structure_identifier_map[cls]
        except KeyError as e:
            raise StructureRegistryError(f"Identifier for {cls} is not registered") from e

    def get_port_scope_for_identifier(self, identifier: str) -> PortScope:
        """Get the port scope for a given identifier."""
        return self.identifier_port_scope_map[identifier]

    def get_default_converter_for_structure(self, cls: Type) -> Callable[[Any], str]:
        """Get the default converter for a given structure."""
        try:
            return self._structure_convert_default_map[cls]
        except KeyError as e:
            if self.allow_auto_register:
                try:
                    return self.auto_register[cls]
                except StructureDefinitionError as e:
                    raise StructureDefinitionError(
                        f"{cls} was not registered and not be no default converter"
                        " could be registered automatically."
                    ) from e
            else:
                raise StructureRegistryError(
                    f"{cls} is not registered and allow_auto_register is set to False."
                    " Please register a 'conver_default' function for this type"
                    " beforehand or set allow_auto_register to True. Otherwise you"
                    " cant use this type with a default"
                ) from e

    def register_as_model(self, cls: Type, identifier: str) -> None:
        self._identifier_model_map[identifier] = cls
        self._model_identifier_map[cls] = identifier

    def register_as_structure(
        self,
        cls: Type,
        identifier: str,
        scope: PortScope = PortScope.GLOBAL,
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
            scope=scope,
            aexpand=aexpand,
            ashrink=ashrink,
            convert_default=convert_default,
            predicate=predicate or build_instance_predicate(cls),
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
        self.fullfill_registration(fs)
        return fs

    def get_fullfilled_structure_for_cls(self, cls: Type) -> FullFilledStructure:
        """Get the fullfilled structure for a given class.
        This will use the structure registry to find the correct
        structure for the given class.

        """
        try:
            return self._fullfilled_structures_map[cls]
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
        fullfilled_structure: FullFilledStructure,
    ) -> None:
        """Fullfill the registration of a structure.

        Sets the structure in the registry and checks if the structure is already registered.
        If it is already registered, it will raise an error.

        Args:
            fullfilled_structure (FullFilledStructure): The fullfilled structure to register
        """
        if (
            fullfilled_structure.identifier in self.identifier_structure_map
            and not self.allow_overwrites
        ):
            raise StructureOverwriteError(
                f"{fullfilled_structure.identifier} is already registered. Previously registered"
                f" {self.identifier_structure_map[fullfilled_structure.identifier]}"
            )

        self._identifier_expander_map[fullfilled_structure.identifier] = (
            fullfilled_structure.aexpand
        )
        self._identifier_shrinker_map[fullfilled_structure.identifier] = (
            fullfilled_structure.ashrink
        )
        self._identifier_predicate_map[fullfilled_structure.identifier] = (
            fullfilled_structure.predicate
        )

        self.identifier_structure_map[fullfilled_structure.identifier] = fullfilled_structure.cls
        self.identifier_port_scope_map[fullfilled_structure.identifier] = fullfilled_structure.scope

        self._structure_identifier_map[fullfilled_structure.cls] = fullfilled_structure.identifier
        self._structure_default_widget_map[fullfilled_structure.cls] = (
            fullfilled_structure.default_widget
        )
        self._structure_default_returnwidget_map[fullfilled_structure.cls] = (
            fullfilled_structure.default_returnwidget
        )
        self._structure_convert_default_map[fullfilled_structure.cls] = (
            fullfilled_structure.convert_default
        )

        self._fullfilled_structures_map[fullfilled_structure.cls] = fullfilled_structure

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

        structure = self.get_fullfilled_structure_for_cls(cls)

        identifier = structure.identifier
        scope = structure.scope

        default_converter = structure.convert_default
        assign_widget = assign_widget or structure.default_widget
        return_widget = return_widget or structure.default_returnwidget

        try:
            return PortInput(
                kind=PortKind.STRUCTURE,
                identifier=identifier,
                assignWidget=assign_widget,
                scope=scope,
                returnWidget=return_widget,
                key=key,
                label=label,
                default=default_converter(default) if (default and default_converter) else None,
                nullable=nullable,
                effects=effects or [],
                description=description,
                validators=validators or [],
            )
        except Exception as e:
            raise StructureRegistryError(
                f"Could not create port for {cls} with fullfilled structure {structure}"
            ) from e


DEFAULT_STRUCTURE_REGISTRY: StructureRegistry | None = None


def get_current_structure_registry(allow_default=True) -> StructureRegistry:
    """Get the current structure registry."""
    return current_structure_registry.get(None)
