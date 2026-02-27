import typing
from abc import ABC, abstractmethod
from typing import Optional, Dict

from flashboot_core.env.environment import Environment
from flashboot_core.env.property_source import PropertySource
from flashboot_core.io.resource import Resource


class PropertySourceLoader(ABC):

    @abstractmethod
    def get_file_extensions(self) -> typing.List[str]:
        pass

    @abstractmethod
    def load(self, name: str, source: Resource) -> PropertySource:
        pass
