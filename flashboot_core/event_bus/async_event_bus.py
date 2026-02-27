from typing import Callable

from flashboot_core.event_bus.base import BaseEventBus


class AsyncEventBus(BaseEventBus):

    def on(self, event: str, /, *, priority: int = 1) -> Callable | int:
        pass

    def subscribe(self, event: str, callback: Callable, /, *, priority: int = 1) -> int:
        pass

    def unsubscribe(self, event: str, callback: Callable, /) -> int | None:
        pass

    def emit(self, event: str, /, **kwargs) -> int:
        pass


async_event_bus = AsyncEventBus()
