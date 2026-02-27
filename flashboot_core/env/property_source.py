import typing

T = typing.TypeVar("T")


class PropertySource(object):
    def __init__(self, name: str, source: typing.Optional[T] = object):
        self.name = name
        self.source = source
        assert self.name is not None
        assert self.source is not None

    def get_name(self) -> str:
        return self.name

    def get_source(self) -> T:
        return self.source

    def get_contains_property(self, name: str):
        pass
