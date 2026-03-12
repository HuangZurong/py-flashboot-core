import inspect
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from loguru import logger

# Root directory of this library, used to filter out internal frames from the call stack
_LIBRARY_ROOT = Path(__file__).resolve().parent.parent

# Explicit root marker file — place this file in a directory to mark it as a project root
ROOT_MARKER = ".root"


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
        self._project_cache: Optional[Path] = None
        self._workspace_cache: Optional[Path] = None

    def _get_caller_project_path(self) -> Path:
        """Determine the caller's project path using multiple fallback strategies."""
        caller_path = self._get_caller_from_stack()
        if caller_path:
            return caller_path

        main_script = self._get_main_script_path()
        if main_script:
            return main_script

        return Path.cwd()

    def _get_caller_from_stack(self) -> Optional[Path]:
        """Walk the call stack to find the first frame outside this library."""
        try:
            stack = inspect.stack()

            for frame_info in stack[1:]:
                if "ipykernel_" in frame_info.filename:
                    continue

                frame_file = Path(frame_info.filename).resolve()

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

        prefixes = [
            sys.prefix.lower(),
            sys.base_prefix.lower(),
        ]
        if any(path_str.startswith(p) for p in prefixes):
            return True

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

    def _iter_ancestors(self) -> List[Path]:
        """
        Walk upward from start_path and return candidate directories (nearest first),
        skipping known non-root dir names.
        """
        candidates = []
        depth = 0
        current = self.start_path

        if current.is_file():
            current = current.parent

        while current != current.parent and depth < self._MAX_TRAVERSAL_DEPTH:
            depth += 1

            if not current.exists() or not current.is_dir():
                current = current.parent
                continue

            if current.name in self._NON_ROOT_DIR_NAMES:
                current = current.parent
                continue

            candidates.append(current)
            current = current.parent

        return candidates

    def _find_nearest_root_marker(self) -> Optional[Path]:
        """Return the nearest ancestor directory containing a .root file."""
        for directory in self._iter_ancestors():
            if (directory / ROOT_MARKER).exists():
                return directory
        return None

    def _find_farthest_root_marker(self) -> Optional[Path]:
        """Return the farthest ancestor directory containing a .root file."""
        result = None
        for directory in self._iter_ancestors():
            if (directory / ROOT_MARKER).exists():
                result = directory
        return result

    def _find_nearest_by_markers(self, markers: List[str] = None) -> Optional[Path]:
        """Return the nearest ancestor directory containing at least one marker."""
        if not markers:
            markers = self._DEFAULT_MARKERS

        for directory in self._iter_ancestors():
            if any((directory / m).exists() for m in markers):
                return directory

        return None

    def _find_farthest_by_markers(self, markers: List[str] = None) -> Optional[Path]:
        """Return the farthest ancestor directory containing at least one marker."""
        if not markers:
            markers = self._DEFAULT_MARKERS

        result = None
        for directory in self._iter_ancestors():
            if any((directory / m).exists() for m in markers):
                result = directory

        return result

    def _find_by_markers(self, markers: List[str] = None) -> Optional[Path]:
        """
        Scoring-based marker search: returns the directory with the highest
        marker count. Used as a legacy fallback.
        """
        if not markers:
            markers = self._DEFAULT_MARKERS

        candidates = {}
        for directory in self._iter_ancestors():
            score = sum(1 for m in markers if (directory / m).exists())
            if score > 0:
                candidates[directory] = score

        if not candidates:
            return None

        return max(candidates.items(), key=lambda x: x[1])[0]

    def _find_by_structure(self) -> Optional[Path]:
        """
        Traverse upward looking for a directory that contains src/ or lib/
        alongside Python files — a common project layout convention.
        """
        for directory in self._iter_ancestors():
            src_dir = directory / "src"
            lib_dir = directory / "lib"
            if (src_dir.exists() and src_dir.is_dir()) or (
                lib_dir.exists() and lib_dir.is_dir()
            ):
                if list(directory.glob("*.py")):
                    return directory

        return None

    def find_project_root(self, search_methods: List[str] = None) -> Path:
        """
        Find the nearest project root — the closest ancestor that looks like
        a project root. Suitable for sub-projects and sub-modules.

        Search order:
        1. Nearest .root marker file (optional, explicit override)
        2. VCS commands (git/svn/hg)
        3. Nearest directory with marker files
        4. Nearest directory matching src/lib structure

        Returns the first successful result, or raises FileNotFoundError.
        """
        if self._project_cache:
            return self._project_cache

        nearest_root_marker = self._find_nearest_root_marker()
        if nearest_root_marker:
            self._project_cache = nearest_root_marker
            return self._project_cache

        if search_methods is None:
            search_methods = ["git", "svn", "hg", "markers", "structure"]

        method_map = {
            "git": self._find_by_git,
            "svn": self._find_by_svn,
            "hg": self._find_by_hg,
            "markers": self._find_nearest_by_markers,
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
                logger.warning(f"Failed to find project root via '{method_name}': {e}")
                continue

            if result:
                self._project_cache = result
                return self._project_cache

        raise FileNotFoundError("Unable to locate project root directory.")

    def find_workspace_root(self, search_methods: List[str] = None) -> Path:
        """
        Find the top-level workspace root — the outermost ancestor that looks
        like a project root. Suitable for monorepos and workspaces.

        Search order:
        1. Farthest .root marker file (optional, explicit override)
        2. Farthest directory with marker files
        3. Farthest directory matching src/lib structure

        Returns the first successful result, or raises FileNotFoundError.
        """
        if self._workspace_cache:
            return self._workspace_cache

        farthest_root_marker = self._find_farthest_root_marker()
        if farthest_root_marker:
            self._workspace_cache = farthest_root_marker
            return self._workspace_cache

        if search_methods is None:
            search_methods = ["markers", "structure"]

        method_map = {
            "markers": self._find_farthest_by_markers,
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
                logger.warning(f"Failed to find workspace root via '{method_name}': {e}")
                continue

            if result:
                self._workspace_cache = result
                return self._workspace_cache

        raise FileNotFoundError("Unable to locate workspace root directory.")

    def find_root(self, search_methods: List[str] = None) -> Path:
        """Alias for find_project_root, kept for internal test compatibility."""
        return self.find_project_root(search_methods)


def get_project_root(start_path: str = None, search_methods: List[str] = None) -> Path:
    """
    Get the nearest project root — the closest ancestor that looks like a project root.
    Suitable for sub-projects and sub-modules.

    :param start_path: directory to start searching from (default: auto-detect)
    :param search_methods: ordered list of strategies to try
                           (default: ["git", "svn", "hg", "markers", "structure"])
    :return: resolved Path to the nearest project root
    """
    return ProjectRootFinder(start_path).find_project_root(search_methods)


def get_workspace_root(start_path: str = None, search_methods: List[str] = None) -> Path:
    """
    Get the top-level workspace root — the outermost ancestor that looks like a project root.
    Suitable for monorepos and workspaces.

    :param start_path: directory to start searching from (default: auto-detect)
    :param search_methods: ordered list of strategies to try
                           (default: ["markers", "structure"])
    :return: resolved Path to the workspace root
    """
    return ProjectRootFinder(start_path).find_workspace_root(search_methods)


def setup_import_path(root: Path = None) -> None:
    """
    Ensure the project root is on sys.path so that local imports work.

    :param root: explicit root path to add; defaults to get_project_root()
    """
    if root is None:
        root = get_project_root()
    root_str = str(root)
    logger.debug(
        f"Root path: {root_str}, please make sure it satisfies the project structure. "
        f"If not, add it to PYTHONPATH manually."
    )
    if root_str not in sys.path:
        sys.path.append(root_str)
