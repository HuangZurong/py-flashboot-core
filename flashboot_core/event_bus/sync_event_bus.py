from typing import Callable

from flashboot_core.event_bus.base import BaseEventBus


class SyncEventBus(BaseEventBus):

    def on(self, event: str, /, *, priority: int = 1) -> Callable:
        """
        Decorator for event subscribe, do not use for instance method.
        :param event:
        :param priority:
        :return:
        """
        self.validate_event(event)

        def wrapper(callback: Callable):
            self.subscribe(event, callback, priority=priority)
            return callback

        return wrapper

    def subscribe(self, event: str, callback: Callable, /, *, priority: int = 1) -> None:
        if event not in self.subscribers:
            self.subscribers[event] = []
        self.subscribers[event].append({"callback": callback, "priority": priority})
        self.subscribers[event].sort(key=lambda x: x["priority"], reverse=True)

    def unsubscribe(self, event: str, callback: Callable, /) -> None:
        if event not in self.subscribers:
            return
        self.subscribers[event] = [x for x in self.subscribers[event] if x["callback"] != callback]

    def emit(self, event: str, *args, **kwargs) -> int:
        self.validate_event(event)

        emit_count: int = 0
        for subscriber in self.subscribers.get(event, []):
            callback = subscriber["callback"]
            callback(*args, **kwargs)
            emit_count += 1

        return emit_count


sync_event_bus = SyncEventBus()
