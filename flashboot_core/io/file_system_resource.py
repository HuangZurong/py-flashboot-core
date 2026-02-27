from pathlib import Path

from flashboot_core.io import File
from flashboot_core.io.resource import Resource


class FileSystemResource(Resource):

    def __init__(self, pathname: str | Path):
        self.pathname = Path(pathname)

    def get_file(self) -> File:
        return File(self.pathname)

    def get_file_name(self) -> str:
        return self.pathname.name
