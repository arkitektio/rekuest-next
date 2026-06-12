"""The ``@structure`` decorator.

A *global structure* is a class whose instances are serialized by reference: an
``ashrink`` turns an instance into a string id and an ``aexpand`` resolves that id
back into an instance. Historically a class became a global structure by
implementing three methods (``get_identifier``/``ashrink``/``aexpand``) and relying
on lazy auto-registration, or by an explicit
:meth:`~rekuest_next.structures.registry.StructureRegistry.register_as_structure`
call.

``@structure`` is the ergonomic front door: it removes the ``get_identifier``
boilerplate (the identifier is passed to the decorator) and registers the class
eagerly in a structure registry. The class only needs ``ashrink`` and ``aexpand``.

Examples:
    Register a class that is serialized by reference::

        @structure(identifier="myapp/image")
        class Image:
            id: str

            async def ashrink(self) -> str:
                return self.id

            @classmethod
            async def aexpand(cls, value: str) -> "Image":
                return await cls.load_from_server(value)
"""

from typing import Any, Callable, Optional, Type, TypeVar, Union, overload

from rekuest_next.api.schema import AssignWidgetInput, ReturnWidgetInput
from rekuest_next.structures.convert import cls_to_identifier
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.errors import StructureDefinitionError
from rekuest_next.structures.registry import StructureRegistry

T = TypeVar("T")


@overload
def structure(identifier: Type[T]) -> Type[T]: ...


@overload
def structure(
    identifier: Optional[str] = None,
    *,
    registry: Optional[StructureRegistry] = None,
    predicate: Optional[Callable[[Any], bool]] = None,
    default_widget: Optional[AssignWidgetInput] = None,
    default_returnwidget: Optional[ReturnWidgetInput] = None,
) -> Callable[[Type[T]], Type[T]]: ...


def structure(
    identifier: Union[str, Type[T], None] = None,
    *,
    registry: Optional[StructureRegistry] = None,
    predicate: Optional[Callable[[Any], bool]] = None,
    default_widget: Optional[AssignWidgetInput] = None,
    default_returnwidget: Optional[ReturnWidgetInput] = None,
) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """Register a class as a global (serialize-by-reference) structure.

    Usable as a bare decorator (``@structure``) or with configuration
    (``@structure(identifier=...)``). The decorated class must expose ``ashrink``
    (instance method) and ``aexpand`` (classmethod). When ``identifier`` is omitted
    the decorator falls back to the class's ``get_identifier`` if present, otherwise
    derives one from the module and class name.

    Args:
        identifier: Stable structure identifier sent to the rekuest server. When
            used bare (``@structure``) this position receives the class instead.
        registry: Structure registry to populate. Defaults to the global registry.
        predicate: Optional instance check. Defaults to an ``isinstance`` check.
        default_widget: Optional default assign widget for ports of this type.
        default_returnwidget: Optional default return widget for ports of this type.

    Returns:
        The decorated class unchanged, or a decorator producing it.
    """
    # Bare-decorator form: @structure applied directly to a class.
    if isinstance(identifier, type):
        return _register_structure(identifier, None, get_default_structure_registry())

    explicit_identifier = identifier
    reg = registry or get_default_structure_registry()

    def wrapper(cls: Type[T]) -> Type[T]:
        return _register_structure(
            cls,
            explicit_identifier,
            reg,
            predicate=predicate,
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )

    return wrapper


def _register_structure(
    cls: Type[T],
    identifier: Optional[str],
    registry: StructureRegistry,
    *,
    predicate: Optional[Callable[[Any], bool]] = None,
    default_widget: Optional[AssignWidgetInput] = None,
    default_returnwidget: Optional[ReturnWidgetInput] = None,
) -> Type[T]:
    """Validate the structure protocol and eagerly register the class."""
    if not hasattr(cls, "ashrink") or not hasattr(cls, "aexpand"):
        raise StructureDefinitionError(
            f"@structure class {cls.__name__!r} must define both an async "
            "`ashrink` (instance) and `aexpand` (classmethod) method."
        )

    ident: str
    if identifier is not None:
        ident = identifier
    elif hasattr(cls, "get_identifier"):
        ident = getattr(cls, "get_identifier")()
    else:
        ident = cls_to_identifier(cls)

    registry.register_as_structure(
        cls,
        ident,
        aexpand=getattr(cls, "aexpand"),
        ashrink=getattr(cls, "ashrink"),
        predicate=predicate,
        default_widget=default_widget,
        default_returnwidget=default_returnwidget,
    )
    return cls
