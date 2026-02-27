from abc import ABC, abstractmethod

from flashboot_core.io import File


class Resource(ABC):

    @abstractmethod
    def get_file(self) -> File:
        pass

    @abstractmethod
    def get_file_name(self) -> str:
        pass
