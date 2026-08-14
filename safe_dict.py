import threading
from collections.abc import MutableMapping
from functools import wraps
from typing import Iterator, Tuple, Optional, TypeVar

KT = TypeVar("KT")
VT = TypeVar("VT")


def lock(func):
    """Decorator to wrap methods with thread lock."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)

    return wrapper


class SafeDict(MutableMapping):
    """Thread-safe dictionary"""

    def __init__(self, *args, **kwargs) -> None:
        self.data = dict(*args, **kwargs)
        self._lock = threading.RLock()

    @lock
    def __setitem__(self, key: KT, value: VT) -> None:
        self.data[key] = value

    @lock
    def __getitem__(self, key: KT) -> VT:
        return self.data[key]

    @lock
    def __delitem__(self, key: KT) -> None:
        del self.data[key]

    @lock
    def __iter__(self) -> Iterator[KT]:
        # Copy keys to avoid holding lock during iteration
        return iter(list(self.data.keys()))

    @lock
    def __len__(self) -> int:
        return len(self.data)

    @lock
    def clear(self) -> None:
        self.data.clear()

    @lock
    def update(self, *args, **kwargs) -> None:
        self.data.update(*args, **kwargs)

    @lock
    def pop(self, key: KT, default: Optional[VT] = None) -> VT:
        return self.data.pop(key, default)

    @lock
    def popitem(self) -> Tuple[KT, VT]:
        return self.data.popitem()

    @lock
    def get(self, key: KT, default: Optional[VT] = None) -> VT:
        return self.data.get(key, default)

    @lock
    def setdefault(self, key: KT, default: Optional[VT] = None) -> VT:
        return self.data.setdefault(key, default)

    @lock
    def keys(self):
        return self.data.keys()

    @lock
    def values(self):
        return self.data.values()

    @lock
    def items(self):
        return self.data.items()

    @lock
    def copy(self) -> "SafeDict":
        return SafeDict(self.data.copy())

    @lock
    def __contains__(self, key: KT) -> bool:
        return key in self.data

    @lock
    def __eq__(self, other) -> bool:
        if isinstance(other, SafeDict):
            return self.data == other.data
        return self.data == other

    @lock
    def __or__(self, other):
        if isinstance(other, (dict, SafeDict)):
            return SafeDict(self.data | dict(other))
        return NotImplemented

    @lock
    def __ior__(self, other):
        if isinstance(other, (dict, SafeDict)):
            self.data |= dict(other)
            return self
        return NotImplemented

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.data!r})"
