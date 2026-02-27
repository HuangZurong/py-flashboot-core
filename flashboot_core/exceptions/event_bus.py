from typing import Any

from flashboot_core.exceptions.base import FlashBootException


class InvalidEventException(FlashBootException):

    def __init__(self, event: Any) -> None:
        super().__init__(f"Expected type \"str\" but got type \"{type(event).__name__}\" instead")
