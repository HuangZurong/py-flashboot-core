import inspect
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from loguru import logger

# Root directory of this library, used to filter out internal frames from the call stack
_LIBRARY_ROOT = Path(__file__).resolve().parent.parent


class ProjectRootFinder:
    """
    Discovers the project root directory using multiple strategies:
    VCS commands (git/svn/hg), marker files, and directory structure heuristics.
    """

    _MAX_TRAVERSAL_DEPTH = 50
    _SUBPROCESS_TIMEOUT = 5  # seconds

    _DEFAULT_MARKERS = [
        "setup.py",
        "pyproject.toml",
        "setup.cfg",
        "poetry.lock",
        "uv.lock",
        "requirements.txt",
        ".git",
        ".gitignore",
        ".hg",
        "Pipfile",
        "Makefile",
        ".idea",
        ".vscode",
        ".venv",
    ]

    _NON_ROOT_DIR_NAMES = {".venv", ".idea", ".git", ".vscode", ".hg"}

    def __init__(self, start_path: str = None):
        if start_path is None:
            self.start_path = self._get_caller_project_path()
        else:
            self.start_path = Path(start_path).resolve()
        self._cache: Optional[Path] = None

    def _get_caller_project_path(self) -> Path:
        """Determine the caller's project path using multiple fallback strategies."""
        # Strategy 1: inspect the call stack for the first external frame
        caller_path = self._get_caller_from_stack()
        if caller_path:
            return caller_path

        # Strategy 2: derive from the main script path (sys.argv[0])
        main_script = self._get_main_script_path()
        if main_script:
            return main_script

        # Strategy 3: fall back to the current working directory
        return Path.cwd()

    def _get_caller_from_stack(self) -> Optional[Path]:
        """Walk the call stack to find the first frame outside this library."""
        try:
            stack = inspect.stack()

            for frame_info in stack[1:]:
                # Skip Jupyter kernel temporary files
                if "ipykernel_" in frame_info.filename:
                    continue

                frame_file = Path(frame_info.filename).resolve()

                # Skip frames from within this library and from stdlib/site-packages
                if self._is_library_internal(frame_file):
                    continue
                if self._is_stdlib_or_site_packages(frame_file):
                    continue

                return frame_file.parent

        except Exception:
            pass

        return None

    @staticmethod
    def _is_library_internal(file_path: Path) -> bool:
        """Check whether the given path belongs to the flashboot_core library itself."""
        try:
            file_path.relative_to(_LIBRARY_ROOT)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_stdlib_or_site_packages(file_path: Path) -> bool:
        """Check whether the given path belongs to the standard library or third-party packages."""
        path_str = str(file_path).lower()

        # Check against Python installation and virtual environment prefixes
        prefixes = [
            sys.prefix.lower(),
            sys.base_prefix.lower(),
        ]
        if any(path_str.startswith(p) for p in prefixes):
            return True

        # Fallback: match common library path indicators
        library_indicators = [
            "site-packages",
            "dist-packages",
            "lib/python",
            "lib64/python",
            "ipykernel",
            "appdata\\local\\temp",
        ]
        return any(indicator in path_str for indicator in library_indicators)

    @staticmethod
    def _get_main_script_path() -> Optional[Path]:
        """Resolve the directory of the main script from sys.argv[0]."""
        try:
            if sys.argv and sys.argv[0]:
                main_script = Path(sys.argv[0]).resolve()
                if main_script.exists() and main_script.is_file():
                    return main_script.parent
        except Exception:
            pass

        return None

    def _find_by_git(self) -> Optional[Path]:
        """Locate the project root via `git rev-parse --show-toplevel`."""
        return self._run_vcs_command(["git", "rev-parse", "--show-toplevel"])

    def _find_by_svn(self) -> Optional[Path]:
        """Locate the project root via `svn info --show-item wcroot-abspath`."""
        return self._run_vcs_command(
            ["svn", "info", "--show-item", "wcroot-abspath", str(self.start_path)]
        )

    def _find_by_hg(self) -> Optional[Path]:
        """Locate the project root via `hg root`."""
        return self._run_vcs_command(["hg", "root"])

    def _run_vcs_command(self, cmd: List[str]) -> Optional[Path]:
        """Run a VCS command and return the resulting path, or None on failure."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.start_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=self._SUBPROCESS_TIMEOUT,
            )
            output = result.stdout.strip()
            if output:
                return Path(output)
        except Exception:
            pass
        return None

    def _find_by_markers(self, markers: List[str] = None) -> Optional[Path]:
        """
        Traverse upward from start_path, scoring each directory by how many
        marker files/dirs it contains. The directory with the highest score wins.
        """
        if self.start_path is None:
            return None

        if not markers:
            markers = self._DEFAULT_MARKERS

        candidates = {}
        depth = 0
        current = self.start_path

        # Ensure we start from a directory, not a file
        if current.is_file():
            current = current.parent

        try:
            while current != current.parent and depth < self._MAX_TRAVERSAL_DEPTH:
                depth += 1

                if not current.exists() or not current.is_dir():
                    current = current.parent
                    continue

                # Skip directories that are clearly not project roots
                if current.name in self._NON_ROOT_DIR_NAMES:
                    current = current.parent
                    continue

                marker_count = sum(
                    1 for marker in markers if (current / marker).exists()
                )
                if marker_count > 0:
                    candidates[current] = marker_count

                current = current.parent
        except Exception:
            pass

        if not candidates:
            return None

        return max(candidates.items(), key=lambda x: x[1])[0]

    def _find_by_structure(self) -> Optional[Path]:
        """
        Traverse upward looking for a directory that contains src/ or lib/
        alongside Python files — a common project layout convention.
        """
        depth = 0
        current = self.start_path

        while current != current.parent and depth < self._MAX_TRAVERSAL_DEPTH:
            depth += 1
            src_dir = current / "src"
            lib_dir = current / "lib"
            if (src_dir.exists() and src_dir.is_dir()) or (
                lib_dir.exists() and lib_dir.is_dir()
            ):
                if list(current.glob("*.py")):
                    return current
            current = current.parent
        return None

    def find_root(self, search_methods: List[str] = None) -> Path:
        """
        Find the project root by trying each search method in order.
        Returns the first successful result, or raises FileNotFoundError.
        """
        if self._cache:
            return self._cache

        if search_methods is None:
            search_methods = ["git", "svn", "hg", "markers", "structure"]

        method_map = {
            "git": self._find_by_git,
            "svn": self._find_by_svn,
            "hg": self._find_by_hg,
            "markers": self._find_by_markers,
            "structure": self._find_by_structure,
        }

        for method_name in search_methods:
            finder = method_map.get(method_name)
            if finder is None:
                logger.warning(f"Unknown search method: {method_name}, skipping")
                continue

            try:
                result = finder()
            except Exception as e:
                logger.warning(
                    f"Failed to find project root via '{method_name}': {e}"
                )
                continue

            if result:
                self._cache = result
                return result

        raise FileNotFoundError("Unable to locate project root directory.")


def get_root_path(start_path: str = None, search_methods: List[str] = None) -> Path:
    """
    Get the project root path.

    :param start_path: directory to start searching from (default: auto-detect)
    :param search_methods: ordered list of strategies to try
                           (default: ["git", "svn", "hg", "markers", "structure"])
    :return: resolved Path to the project root
    """
    finder = ProjectRootFinder(start_path)
    return finder.find_root(search_methods)


def ensure_search_path() -> None:
    """Ensure the project root is on sys.path so that local imports work."""
    root_path = str(get_root_path())
    logger.debug(
        f"Root path: {root_path}, please make sure it satisfies the project structure. "
        f"If not, add it to PYTHONPATH manually."
    )
    if root_path not in sys.path:
        sys.path.append(root_path)
