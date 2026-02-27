from pathlib import Path


class File:

    def __init__(self, pathname: str | Path):
        self.pathname = Path(pathname)

    def get_name(self) -> str:
        return str(self.pathname)

    def get_absolute_path(self) -> str:
        return str(self.pathname.absolute())
