from abc import abstractmethod
from typing import Dict, List, Callable, Any

from flashboot_core.exceptions.event_bus import InvalidEventException


class BaseEventBus:
    subscribers: Dict[str, List[Dict]] = {}

    @abstractmethod
    def on(self, event: str, /, *, priority: int = 1) -> Callable | int:
        ...

    @abstractmethod
    def subscribe(self, event: str, callback: Callable, /, *, priority: int = 1) -> int:
        ...

    @abstractmethod
    def unsubscribe(self, event: str, callback: Callable, /) -> int | None:
        ...

    @abstractmethod
    def emit(self, event: str, /, **kwargs) -> int:
        ...

    @staticmethod
    def validate_event(event: Any):
        if not isinstance(event, str):
            raise InvalidEventException(event)
