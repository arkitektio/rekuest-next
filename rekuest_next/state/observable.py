import dataclasses
from typing import Any, Generic, Iterable, TypeVar, overload, SupportsIndex

from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.state.lock import get_acquired_locks
from rekuest_next.state.publish import Patch, get_current_publisher
from rekuest_next.structures.registry import StructureRegistry

# --- JSON Pointer Utilities (RFC 6901) ---


def _escape_json_pointer(key: str) -> str:
    """Escape special characters for JSON Pointer (RFC 6901).

    Per RFC 6901:
    - '~' is escaped as '~0'
    - '/' is escaped as '~1'
    """
    return key.replace("~", "~0").replace("/", "~1")


def _make_path(base: str, key: str | int) -> str:
    """Create a JSON Pointer path by appending a key to a base path."""
    escaped_key = _escape_json_pointer(str(key)) if isinstance(key, str) else str(key)
    return f"{base}/{escaped_key}"


# --- Configuration ---


@dataclasses.dataclass
class EventedConfig:
    """Configuration for evented objects, storing the state interface name and schema."""

    state_name: str
    state_schema: StateSchemaInput
    structure_registry: StructureRegistry
    publish_interval: float = 0.1  # Optional: Minimum interval between patches to prevent flooding
    required_locks: list[str] = dataclasses.field(default_factory=list)


def _publish_patch(config: EventedConfig, patch: Patch) -> None:
    """Helper to publish a patch through the current publisher."""
    publisher = get_current_publisher()
    if publisher and hasattr(publisher, "publish_patch"):
        publisher.publish_patch(config.state_name, patch)  # type: ignore


# --- JSON Patch Compliant EventedDict (RFC 6902) ---

K = TypeVar("K")
V = TypeVar("V")


class EventedDict(dict[K, V], Generic[K, V]):
    """A dictionary wrapper that emits JSON Patch operations on modification.

    Supports all standard dict mutation methods with proper JSON Patch semantics:
    - add: When a new key is added
    - remove: When a key is deleted
    - replace: When an existing key's value is changed
    """

    def __init__(self, data: dict[K, V], config: EventedConfig, path: str):
        super().__init__(data)
        self._config = config
        self._path = path

    def __check_if_has_required_locks(self) -> None:
        acquired_locks = get_acquired_locks()
        missing_locks = [lock for lock in self._config.required_locks if lock not in acquired_locks]
        if missing_locks:
            raise RuntimeError(
                f"Cannot modify state '{self._config.state_name}' at path '{self._path}' without required locks: {missing_locks}"
            )

    def __setitem__(self, key: Any, value: Any) -> None:
        self.__check_if_has_required_locks()
        full_path = _make_path(self._path, key)
        exists = key in self
        old_value = self.get(key) if exists else None

        # Wrap new complex objects so future changes are caught
        value = make_evented(value, self._config, full_path)

        super().__setitem__(key, value)

        # JSON Patch: "add" for new keys, "replace" for existing
        op = "replace" if exists else "add"
        _publish_patch(
            self._config,
            Patch(op=op, path=full_path, value=value, old_value=old_value),
        )

    def __delitem__(self, key: Any) -> None:
        self.__check_if_has_required_locks()
        full_path = _make_path(self._path, key)
        old_value = self[key]

        super().__delitem__(key)
        _publish_patch(
            self._config,
            Patch(op="remove", path=full_path, value=None, old_value=old_value),
        )

    def pop(self, key: Any, *default: Any) -> Any:
        """Remove specified key and return the corresponding value.

        Emits a 'remove' patch if the key exists.
        """
        self.__check_if_has_required_locks()
        if key in self:
            full_path = _make_path(self._path, key)
            old_value = self[key]
            result = super().pop(key)
            _publish_patch(
                self._config,
                Patch(op="remove", path=full_path, value=None, old_value=old_value),
            )
            return result
        elif default:
            return default[0]
        else:
            raise KeyError(key)

    def popitem(self) -> tuple[Any, Any]:
        """Remove and return a (key, value) pair as a 2-tuple.

        Emits a 'remove' patch for the removed item.
        """
        self.__check_if_has_required_locks()
        key, value = super().popitem()
        full_path = _make_path(self._path, key)
        _publish_patch(
            self._config,
            Patch(op="remove", path=full_path, value=None, old_value=value),
        )
        return key, value

    def clear(self) -> None:
        """Remove all items from the dictionary.

        Emits a 'remove' patch for each key.
        """
        self.__check_if_has_required_locks()
        keys = list(self.keys())
        for key in keys:
            del self[key]

    def setdefault(self, key: Any, default: Any = None) -> Any:
        """Insert key with a value of default if key is not in the dictionary.

        Emits an 'add' patch only if the key was not present.
        """
        self.__check_if_has_required_locks()
        if key not in self:
            self[key] = default
        return self[key]

    def update(self, other: Any = None, **kwargs: Any) -> None:
        """Update the dictionary with key/value pairs.

        Emits 'add' or 'replace' patches for each key.
        """
        self.__check_if_has_required_locks()
        if other:
            if hasattr(other, "keys"):
                for k in other.keys():
                    self[k] = other[k]
            else:
                for k, v in other:
                    self[k] = v
        for k, v in kwargs.items():
            self[k] = v


# --- JSON Patch Compliant EventedList (RFC 6902) ---

T = TypeVar("T")


class EventedList(list):
    """A list wrapper that emits JSON Patch operations on modification.

    Supports all standard list mutation methods with proper JSON Patch semantics:
    - add: When an item is inserted (uses index or '/-' for append)
    - remove: When an item is deleted
    - replace: When an existing item is changed

    Per RFC 6902, the special path element '-' refers to the end of the array
    for 'add' operations.
    """

    def __init__(self, iterable: Iterable, config: EventedConfig, path: str):
        super().__init__(iterable)
        self._config = config
        self._path = path

    def __check_if_has_required_locks(self) -> None:
        acquired_locks = get_acquired_locks()
        missing_locks = [lock for lock in self._config.required_locks if lock not in acquired_locks]
        if missing_locks:
            raise RuntimeError(
                f"Cannot modify state '{self._config.state_name}' at path '{self._path}' without required locks: {missing_locks}"
            )

    def _reindex_items(self, start_index: int) -> None:
        """Update the internal path references for items after a shift.

        This is necessary after insert/remove operations that shift indices.
        """
        self.__check_if_has_required_locks()
        for i in range(start_index, len(self)):
            item = super().__getitem__(i)
            if hasattr(item, "_event_path"):
                new_path = _make_path(self._path, i)
                object.__setattr__(item, "_event_path", new_path)
            elif isinstance(item, (EventedDict, EventedList)):
                item._path = _make_path(self._path, i)

    @overload
    def __setitem__(self, index: SupportsIndex, value: Any) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[Any]) -> None: ...

    def __setitem__(self, index: SupportsIndex | slice, value: Any) -> None:
        self.__check_if_has_required_locks()
        if isinstance(index, slice):
            # Handle slice assignment
            indices = range(*index.indices(len(self)))

            # Convert value to list for iteration
            new_values = list(value)

            # For simplicity, emit replace for overlapping indices,
            # remove for extra old items, add for extra new items
            for i, idx in enumerate(indices):
                if i < len(new_values):
                    if idx < len(self):
                        self[idx] = new_values[i]

            # This is a complex case - for now, replace the slice and emit patches
            super().__setitem__(
                index,
                [
                    make_evented(v, self._config, _make_path(self._path, indices.start + i))
                    for i, v in enumerate(new_values)
                ],
            )
            self._reindex_items(0)
        else:
            idx = index.__index__()
            full_path = _make_path(self._path, idx)
            old_value = self[idx]

            # Wrap new value
            value = make_evented(value, self._config, full_path)
            super().__setitem__(idx, value)
            _publish_patch(
                self._config,
                Patch(op="replace", path=full_path, value=value, old_value=old_value),
            )

    def __delitem__(self, index: SupportsIndex | slice) -> None:
        self.__check_if_has_required_locks()
        if isinstance(index, slice):
            # Handle slice deletion
            indices = sorted(range(*index.indices(len(self))), reverse=True)
            for idx in indices:
                del self[idx]
        else:
            idx = index.__index__()
            full_path = _make_path(self._path, idx)
            old_value = self[idx]

            super().__delitem__(idx)
            _publish_patch(
                self._config,
                Patch(op="remove", path=full_path, value=None, old_value=old_value),
            )
            # Reindex items after the deleted position
            self._reindex_items(idx)

    def append(self, item: Any) -> None:
        """Append item to end of list.

        Per RFC 6902, uses '/-' to indicate appending to end of array.
        """
        # Use the special '-' path element for array append per RFC 6902
        self.__check_if_has_required_locks()
        append_path = f"{self._path}/-"

        # The actual index for the evented item's path reference
        actual_index = len(self)
        actual_path = _make_path(self._path, actual_index)

        item = make_evented(item, self._config, actual_path)
        super().append(item)
        _publish_patch(self._config, Patch(op="add", path=append_path, value=item, old_value=None))

    def insert(self, index: SupportsIndex, item: Any) -> None:
        """Insert item before index.

        Emits an 'add' patch at the specified index.
        """
        self.__check_if_has_required_locks()
        # Normalize negative index
        idx = index.__index__()
        if idx < 0:
            idx = max(0, len(self) + idx)
        idx = min(idx, len(self))

        full_path = _make_path(self._path, idx)

        item = make_evented(item, self._config, full_path)
        super().insert(idx, item)
        _publish_patch(self._config, Patch(op="add", path=full_path, value=item, old_value=None))
        # Reindex items after the inserted position
        self._reindex_items(idx + 1)

    def extend(self, items: Iterable[Any]) -> None:
        """Extend list by appending elements from the iterable.

        Emits an 'add' patch for each item.
        """
        self.__check_if_has_required_locks()
        for item in items:
            self.append(item)

    def pop(self, index: SupportsIndex = -1) -> Any:  # type: ignore[override]
        """Remove and return item at index (default last).

        Emits a 'remove' patch.
        """
        self.__check_if_has_required_locks()
        # Convert to int
        idx: int = index.__index__() if hasattr(index, "__index__") else int(index)  # type: ignore
        # Normalize negative index
        if idx < 0:
            idx = len(self) + idx

        full_path = _make_path(self._path, idx)
        old_value = self[idx]

        result = super().pop(idx)
        _publish_patch(
            self._config,
            Patch(op="remove", path=full_path, value=None, old_value=old_value),
        )
        # Reindex items after the removed position
        self._reindex_items(idx)
        return result

    def remove(self, item: Any) -> None:
        """Remove first occurrence of item.

        Emits a 'remove' patch at the item's index.
        """
        self.__check_if_has_required_locks()
        index = self.index(item)
        del self[index]

    def clear(self) -> None:
        """Remove all items from list.

        Emits a 'remove' patch for each item, from end to start.
        """
        self.__check_if_has_required_locks()
        while len(self) > 0:
            self.pop()

    def reverse(self) -> None:
        """Reverse list in place.

        Emits 'replace' patches for each changed position.
        """
        self.__check_if_has_required_locks()
        old_items = list(self)
        super().reverse()

        for i in range(len(self)):
            if old_items[i] != self[i]:
                full_path = _make_path(self._path, i)
                _publish_patch(
                    self._config,
                    Patch(
                        op="replace",
                        path=full_path,
                        value=self[i],
                        old_value=old_items[i],
                    ),
                )
        self._reindex_items(0)

    def sort(self, *, key: Any = None, reverse: bool = False) -> None:
        """Sort list in place.

        Emits 'replace' patches for each changed position.
        """
        self.__check_if_has_required_locks()
        old_items = list(self)
        super().sort(key=key, reverse=reverse)

        for i in range(len(self)):
            if old_items[i] != self[i]:
                full_path = _make_path(self._path, i)
                _publish_patch(
                    self._config,
                    Patch(
                        op="replace",
                        path=full_path,
                        value=self[i],
                        old_value=old_items[i],
                    ),
                )
        self._reindex_items(0)

    def __iadd__(self, other: Iterable[Any]) -> "EventedList":
        """Implement += operator."""
        self.__check_if_has_required_locks()
        self.extend(other)
        return self

    def __imul__(self, n: SupportsIndex) -> "EventedList":  # type: ignore[override]
        """Implement *= operator."""
        self.__check_if_has_required_locks()
        count = n.__index__() if hasattr(n, "__index__") else int(n)  # type: ignore
        if count <= 0:
            self.clear()
        else:
            original = list(self)
            for _ in range(count - 1):
                self.extend(original)
        return self


# --- The Recursive Factory ---


def make_evented(
    obj: Any,
    config: EventedConfig,
    path: str = "",
) -> Any:
    """
    Recursively converts Dataclasses, Dicts, and Lists into event-emitting objects.
    """

    # CASE A: Dictionary
    if isinstance(obj, dict):
        # Recursively wrap items inside the dict first
        wrapped_data = {}
        for k, v in obj.items():
            child_path = _make_path(path, k)
            wrapped_data[k] = make_evented(v, config, child_path)

        return EventedDict(wrapped_data, config, path)

    # CASE B: List
    if isinstance(obj, list):
        wrapped_items = [
            make_evented(item, config, path=_make_path(path, i)) for i, item in enumerate(obj)
        ]
        return EventedList(wrapped_items, config, path)

    # CASE C: Dataclass
    if dataclasses.is_dataclass(obj):
        # We modify the object IN-PLACE by changing its class to a dynamic subclass

        # 1. Recursively wrap children fields
        for field in dataclasses.fields(obj):
            val = getattr(obj, field.name)
            child_path = _make_path(path, field.name)

            wrapped_val = make_evented(val, config, path=child_path)
            # Use object.__setattr__ to bypass any existing hooks
            object.__setattr__(obj, field.name, wrapped_val)

        # 2. Check if already patched (optimization)
        if hasattr(obj, "_is_evented_wrapper"):
            return obj

        # 3. Create the interceptor hook
        def setattr_hook(self, name, value):
            self.__check_if_has_required_locks()
            if name.startswith("_"):
                super(self.__class__, self).__setattr__(name, value)
                return

            old_value = getattr(self, name, None)

            if old_value != value:
                # Calculate path using JSON Pointer format
                base = self._event_path
                current_path = _make_path(base, name)

                # Wrap the new value immediately!
                value = make_evented(value, self._event_config, path=current_path)

                super(self.__class__, self).__setattr__(name, value)

                # Publish the patch
                _publish_patch(
                    self._event_config,
                    Patch(
                        op="replace",
                        path=current_path,
                        value=value,
                        old_value=old_value,
                    ),
                )

        def __check_if_has_required_locks(self):
            acquired_locks = get_acquired_locks()
            missing_locks = [
                lock
                for lock in self.__rekuest__config__.required_locks
                if lock not in acquired_locks
            ]
            if missing_locks:
                raise RuntimeError(
                    f"Cannot modify state '{self.__rekuest__config__.state_name}' at path '{self._event_path}' without required locks: {missing_locks}"
                )

        # 4. Create dynamic subclass
        original_cls = obj.__class__
        EventedClass = type(
            f"Evented{original_cls.__name__}",
            (original_cls,),
            {
                "__check_if_has_required_locks": __check_if_has_required_locks,
                "__setattr__": setattr_hook,
                "_is_evented_wrapper": True,
                "__rekuest__config__": config,
            },
        )

        # 5. Swizzle
        obj.__class__ = EventedClass
        object.__setattr__(obj, "_event_config", config)
        object.__setattr__(obj, "_event_path", path)

        return obj

    # CASE D: Primitive
    return obj
