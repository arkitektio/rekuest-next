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
    ChildPortInput,
    EffectInput,
    PortInput,
    PortKind,
    PortScope,
    ReturnWidgetInput,
    ValidatorInput,
)

from .errors import (
    StructureDefinitionError,
    StructureOverwriteError,
    StructureRegistryError,
)
from .hooks.default import get_default_hooks
from .hooks.errors import HookError
from .hooks.types import RegistryHook
from .types import FullFilledStructure, PortBuilder

current_structure_registry = contextvars.ContextVar("current_structure_registry")


T = TypeVar("T")

Identifier = str
""" A unique identifier of this structure on the arkitekt platform"""
GroupMap = Dict[str, List[str]]
WidgetMap = Dict[str, List[AssignWidgetInput]]
ReturnWidgetMap = Dict[str, List[ReturnWidgetInput]]
EffectsMap = Dict[str, List[EffectInput]]


def cls_to_identifier(cls: Type) -> Identifier:
    return f"{cls.__module__.lower()}.{cls.__name__.lower()}"


def build_async_model_expander(cls: Type):
    async def expander(values):
        return cls(**values)

    return expander


class StructureRegistry(BaseModel):
    copy_from_default: bool = False
    allow_overwrites: bool = True
    allow_auto_register: bool = True
    cls_to_identifier: Callable[[Type], Identifier] = cls_to_identifier

    identifier_structure_map: Dict[str, Type] = Field(
        default_factory=dict, exclude=True
    )
    identifier_port_scope_map: Dict[str, PortScope] = Field(
        default_factory=dict, exclude=True
    )
    _identifier_expander_map: Dict[str, Callable[[str], Awaitable[Any]]] = {}
    _identifier_shrinker_map: Dict[str, Callable[[Any], Awaitable[str]]] = {}
    _identifier_collecter_map: Dict[str, Callable[[Any], Awaitable[None]]] = {}
    _identifier_predicate_map: Dict[str, Callable[[Any], bool]] = {}
    _identifier_builder_map: Dict[str, PortBuilder] = {}

    _identifier_model_map: Dict[str, Type] = {}
    _model_identifier_map: Dict[Type, str] = {}

    _structure_convert_default_map: Dict[str, Callable[[Any], str]] = {}
    _structure_identifier_map: Dict[Type, str] = {}
    _structure_default_widget_map: Dict[Type, AssignWidgetInput] = {}
    _structure_default_returnwidget_map: Dict[Type, ReturnWidgetInput] = {}
    _structure_annotation_map: Dict[Type, Type] = {}

    registry_hooks: OrderedDict[str, RegistryHook] = Field(
        default_factory=get_default_hooks
    )
    _fullfilled_structures_map: Dict[Type, FullFilledStructure] = {}

    _token: contextvars.Token = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_expander_for_identifier(self, key):
        try:
            return self._identifier_expander_map[key]
        except KeyError as e:
            raise StructureRegistryError(f"Expander for {key} is not registered") from e

    def get_collector_for_identifier(self, key):
        try:
            return self._identifier_collecter_map[key]
        except KeyError as e:
            raise StructureRegistryError(
                f"Collector for {key} is not registered"
            ) from e

    def get_shrinker_for_identifier(self, key):
        try:
            return self._identifier_shrinker_map[key]
        except KeyError as e:
            raise StructureRegistryError(f"Shrinker for {key} is not registered") from e

    def register_expander(self, key, expander):
        self._identifier_expander_map[key] = expander

    def get_widget_input(self, cls) -> Optional[AssignWidgetInput]:
        return self._structure_default_widget_map.get(cls, None)

    def get_returnwidget_input(self, cls) -> Optional[ReturnWidgetInput]:
        return self._structure_default_returnwidget_map.get(cls, None)

    def get_predicator_for_identifier(
        self, identifier: str
    ) -> Optional[Callable[[Any], bool]]:
        return self._identifier_predicate_map[identifier]

    def get_identifier_for_structure(self, cls):
        try:
            return self._structure_identifier_map[cls]
        except KeyError as e:
            if self.allow_auto_register:
                try:
                    self.register_as_structure(cls)
                    return self._structure_identifier_map[cls]
                except StructureDefinitionError as e:
                    raise StructureDefinitionError(
                        f"{cls} was not registered and could not be registered"
                        " automatically"
                    ) from e
            else:
                raise StructureRegistryError(
                    f"{cls} is not registered and allow_auto_register is set to False."
                    " Please make sure to register this type beforehand or set"
                    " allow_auto_register to True"
                ) from e

    def get_port_scope_for_identifier(self, identifier: str):
        return self.identifier_port_scope_map[identifier]

    def get_default_converter_for_structure(self, cls):
        try:
            return self._structure_convert_default_map[cls]
        except KeyError as e:
            if self.allow_auto_register:
                try:
                    self.register_as_structure(cls)
                    return self._structure_convert_default_map[cls]
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

    def retrieve_model_expander(self, identifier: str):
        return build_async_model_expander(self._identifier_model_map[identifier])

    def register_as_model(self, cls: Type, identifier: str) -> None:
        self._identifier_model_map[identifier] = cls
        self._model_identifier_map[cls] = identifier

    def register_as_structure(
        self,
        cls: Type,
        identifier: str = None,
        scope: PortScope = PortScope.LOCAL,
        aexpand: Callable[
            [
                str,
            ],
            Awaitable[Any],
        ] = None,
        ashrink: Callable[
            [
                any,
            ],
            Awaitable[str],
        ] = None,
        acollect: Callable[
            [
                str,
            ],
            Awaitable[Any],
        ] = None,
        predicate: Callable[[Any], bool] = None,
        convert_default: Callable[[Any], str] = None,
        default_widget: Optional[AssignWidgetInput] = None,
        default_returnwidget: Optional[ReturnWidgetInput] = None,
    ):
        fullfilled_structure = None
        for key, hook in self.registry_hooks.items():
            try:
                if hook.is_applicable(cls):
                    try:
                        fullfilled_structure = hook.apply(
                            cls,
                            identifier=identifier,
                            scope=scope,
                            aexpand=aexpand,
                            ashrink=ashrink,
                            acollect=acollect,
                            predicate=predicate,
                            convert_default=convert_default,
                            default_widget=default_widget,
                            default_returnwidget=default_returnwidget,
                        )
                        break  # we found a hook that applies
                    except HookError as e:
                        raise StructureDefinitionError(
                            f"Hook {key} failed to apply to {cls}"
                        ) from e
            except Exception as e:
                raise StructureDefinitionError(
                    f"Hook {key} does not correctly implement its interface. Please contact the developer of this hook."
                ) from e

        if fullfilled_structure is None:
            raise StructureDefinitionError(
                f"No hook was able to apply to {cls}. Please check your hooks {self.registry_hooks}"
            )

        self.fullfill_registration(fullfilled_structure)

    def get_fullfilled_structure_for_cls(self, cls: Type) -> FullFilledStructure:
        try:
            return self._fullfilled_structures_map[cls]
        except KeyError:
            if self.allow_auto_register:
                try:
                    self.register_as_structure(cls)
                    return self._fullfilled_structures_map[cls]
                except StructureDefinitionError as e:
                    raise StructureDefinitionError(
                        f"{cls} was not registered and could not be registered"
                        " automatically"
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
    ):
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
        self._identifier_collecter_map[fullfilled_structure.identifier] = (
            fullfilled_structure.acollect
        )
        self._identifier_shrinker_map[fullfilled_structure.identifier] = (
            fullfilled_structure.ashrink
        )
        self._identifier_predicate_map[fullfilled_structure.identifier] = (
            fullfilled_structure.predicate
        )

        self.identifier_structure_map[fullfilled_structure.identifier] = (
            fullfilled_structure.cls
        )
        self.identifier_port_scope_map[fullfilled_structure.identifier] = (
            fullfilled_structure.scope
        )

        self._structure_identifier_map[fullfilled_structure.cls] = (
            fullfilled_structure.identifier
        )
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

    def get_converter_for_annotation(self, annotation):
        try:
            return self._structure_annotation_map[annotation]
        except KeyError as e:
            raise StructureRegistryError(f"{annotation} is not registered") from e
        
        
    def get_identifier_for_cls(self, cls: Type) -> Identifier:
        try:
            return self.get_fullfilled_structure_for_cls(cls).identifier
        except KeyError as e:
            raise StructureRegistryError(f"{cls} is not registered") from e

    def get_port_for_cls(
        self,
        cls: Type,
        key: str,
        nullable: bool = False,
        description: Optional[str] = None,
        effects: Optional[EffectsMap] = None,
        label: Optional[str] = None,
        validators: Optional[List[ValidatorInput]] = None,
        default: Any = None,
        assign_widget: Optional[AssignWidgetInput] = None,
        return_widget: Optional[ReturnWidgetInput] = None,
    ) -> PortInput:
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
                default=default_converter(default) if default else None,
                nullable=nullable,
                effects=effects,
                description=description,
                validators=validators,
            )
        except Exception as e:
            raise StructureRegistryError(
                f"Could not create port for {cls} with fullfilled structure {structure}"
            ) from e

    def get_child_port_and_default_converter_for_cls(
        self,
        cls: Type,
        key: str,
        nullable: bool = False,
        description: Optional[str] = None,
        assign_widget: Optional[AssignWidgetInput] = None,
        return_widget: Optional[ReturnWidgetInput] = None,
    ) -> PortInput:
        identifier = self.get_identifier_for_structure(cls)
        scope = self.get_port_scope_for_identifier(identifier)
        identifier = self.get_identifier_for_structure(cls)
        default_converter = self.get_default_converter_for_structure(cls)
        assign_widget = assign_widget or self.get_widget_input(cls)
        return_widget = return_widget or self.get_returnwidget_input(cls)

        return (
            ChildPortInput(
                key=key,
                kind=PortKind.STRUCTURE,
                identifier=identifier,
                scope=scope,
                nullable=nullable,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                description=description,
            ),
            default_converter,
        )

    async def __aenter__(self):
        current_structure_registry.set(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        current_structure_registry.set(None)



DEFAULT_STRUCTURE_REGISTRY = None


def get_current_structure_registry(allow_default=True) -> StructureRegistry:
    return current_structure_registry.get(None)
