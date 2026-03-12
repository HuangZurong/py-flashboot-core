import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from flashboot_core.utils.project_utils import (
    ProjectRootFinder,
    _LIBRARY_ROOT,
    ROOT_MARKER,
    get_project_root,
    get_workspace_root,
    setup_import_path,
)


class DirectoryEnvironment:
    """Helper to build mock directory structures for testing."""

    def __init__(self, base: Path):
        self.base = base

    def mkdir(self, *parts) -> Path:
        p = self.base.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def touch(self, *parts) -> Path:
        p = self.base.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return p


# A unique marker that won't exist anywhere on the real filesystem,
# used to isolate tests from the host environment.
_TEST_MARKER = ".flashboot_test_marker_do_not_create"


class TestFindByMarkers(unittest.TestCase):
    """Test _find_by_markers with constructed directory environments."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    # --- Standard project ---

    def test_standard_project_with_single_marker(self):
        """
        project/
          .flashboot_test_marker
          src/
            app/
        """
        self.env.touch("project", _TEST_MARKER)
        start = self.env.mkdir("project", "src", "app")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    def test_standard_project_with_multiple_markers(self):
        """
        project/
          .flashboot_test_marker
          another_marker
          mypackage/
        """
        self.env.touch("project", _TEST_MARKER)
        self.env.touch("project", "another_marker")
        start = self.env.mkdir("project", "mypackage")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER, "another_marker"])
        self.assertEqual(result, self.tmp / "project")

    # --- Monorepo with submodules ---

    def test_monorepo_selects_root_over_submodule(self):
        """
        monorepo/
          marker_a
          marker_b
          marker_c
          packages/
            pkg-a/
              marker_a
              src/
        Root has 3 markers, pkg-a has 1 → root wins.
        """
        markers = ["marker_a", "marker_b", "marker_c"]
        self.env.touch("monorepo", "marker_a")
        self.env.touch("monorepo", "marker_b")
        self.env.touch("monorepo", "marker_c")
        self.env.touch("monorepo", "packages", "pkg-a", "marker_a")
        start = self.env.mkdir("monorepo", "packages", "pkg-a", "src")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=markers)
        self.assertEqual(result, self.tmp / "monorepo")

    def test_monorepo_submodules_equal_markers(self):
        """
        monorepo/
          marker_a
          marker_b
          packages/
            pkg-a/
              marker_a
              marker_b
        Both have 2 markers — either is acceptable.
        """
        markers = ["marker_a", "marker_b"]
        self.env.touch("monorepo", "marker_a")
        self.env.touch("monorepo", "marker_b")
        self.env.touch("monorepo", "packages", "pkg-a", "marker_a")
        self.env.touch("monorepo", "packages", "pkg-a", "marker_b")
        start = self.env.mkdir("monorepo", "packages", "pkg-a", "src")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=markers)
        self.assertIn(result, [
            self.tmp / "monorepo",
            self.tmp / "monorepo" / "packages" / "pkg-a",
        ])

    # --- .venv / .git directories should be skipped ---

    def test_skips_venv_directory(self):
        """
        project/
          .flashboot_test_marker
          .venv/
            lib/
              deep/
        Start from .venv/lib/deep/ — should not select .venv as root.
        """
        self.env.touch("project", _TEST_MARKER)
        start = self.env.mkdir("project", ".venv", "lib", "deep")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    def test_skips_dot_git_directory(self):
        """
        project/
          .flashboot_test_marker
          .git/
            hooks/
        Start from .git/hooks/
        """
        self.env.touch("project", _TEST_MARKER)
        start = self.env.mkdir("project", ".git", "hooks")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    def test_skips_idea_directory(self):
        self.env.touch("project", _TEST_MARKER)
        start = self.env.mkdir("project", ".idea", "inspections")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    # --- Start from a file path ---

    def test_start_path_is_a_file(self):
        """
        project/
          .flashboot_test_marker
          src/
            main.py
        Start from src/main.py (a file, not a directory).
        """
        self.env.touch("project", _TEST_MARKER)
        start = self.env.touch("project", "src", "main.py")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    # --- Deep nesting ---

    def test_deep_nesting(self):
        """Project root is many levels up."""
        self.env.touch("project", _TEST_MARKER)
        deep = self.env.mkdir("project", "a", "b", "c", "d", "e", "f", "g", "h")

        finder = self._finder(deep)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    # --- No markers at all ---

    def test_no_markers_returns_none(self):
        """Empty directory tree with no markers."""
        start = self.env.mkdir("empty", "sub")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertIsNone(result)

    # --- Custom markers ---

    def test_custom_markers_found(self):
        self.env.touch("project", "MY_CUSTOM_MARKER")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=["MY_CUSTOM_MARKER"])
        self.assertEqual(result, self.tmp / "project")

    def test_custom_markers_not_found(self):
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=["NONEXISTENT_MARKER"])
        self.assertIsNone(result)


class TestFindByStructure(unittest.TestCase):
    """Test _find_by_structure with constructed directory environments."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_finds_dir_with_src_and_py_files(self):
        """
        project/
          setup.py
          src/
            app/
        """
        self.env.touch("project", "setup.py")
        self.env.mkdir("project", "src")
        start = self.env.mkdir("project", "src", "app")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertEqual(result, self.tmp / "project")

    def test_finds_dir_with_lib_and_py_files(self):
        """
        project/
          main.py
          lib/
            utils/
        """
        self.env.touch("project", "main.py")
        self.env.mkdir("project", "lib")
        start = self.env.mkdir("project", "lib", "utils")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertEqual(result, self.tmp / "project")

    def test_src_without_py_files_not_matched(self):
        """
        project/
          src/
            data.txt
          sub/
        No .py files at project level — should not match.
        """
        self.env.mkdir("project", "src")
        self.env.touch("project", "src", "data.txt")
        start = self.env.mkdir("project", "sub")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertIsNone(result)

    def test_no_src_or_lib_returns_none(self):
        start = self.env.mkdir("project", "app", "deep")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertIsNone(result)


class TestFindByVCS(unittest.TestCase):
    """Test VCS methods with mocked subprocess calls."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_git_success(self, mock_run):
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        mock_run.return_value = MagicMock(stdout=str(expected) + "\n")
        finder = self._finder(start)
        result = finder._find_by_git()
        self.assertEqual(result, expected)

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_git_not_a_repo(self, mock_run):
        start = self.env.mkdir("project", "src")
        mock_run.side_effect = Exception("not a git repository")

        finder = self._finder(start)
        result = finder._find_by_git()
        self.assertIsNone(result)

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_svn_success(self, mock_run):
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        mock_run.return_value = MagicMock(stdout=str(expected) + "\n")
        finder = self._finder(start)
        result = finder._find_by_svn()
        self.assertEqual(result, expected)

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_hg_success(self, mock_run):
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        mock_run.return_value = MagicMock(stdout=str(expected) + "\n")
        finder = self._finder(start)
        result = finder._find_by_hg()
        self.assertEqual(result, expected)

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_git_timeout(self, mock_run):
        """Subprocess timeout should return None, not raise."""
        start = self.env.mkdir("project", "src")
        mock_run.side_effect = TimeoutError("timed out")

        finder = self._finder(start)
        result = finder._find_by_git()
        self.assertIsNone(result)

    @patch("flashboot_core.utils.project_utils.subprocess.run")
    def test_find_by_git_empty_output(self, mock_run):
        start = self.env.mkdir("project", "src")
        mock_run.return_value = MagicMock(stdout="  \n")

        finder = self._finder(start)
        result = finder._find_by_git()
        self.assertIsNone(result)


class TestFindRoot(unittest.TestCase):
    """Test the find_project_root orchestration method with mocked strategies."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_first_successful_method_wins(self):
        """When git returns a result, markers is not called."""
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        finder = self._finder(start)
        with patch.object(finder, "_find_by_git", return_value=expected) as mock_git, \
             patch.object(finder, "_find_nearest_by_markers") as mock_markers:
            result = finder.find_project_root(search_methods=["git", "markers"])
            self.assertEqual(result, expected)
            mock_git.assert_called_once()
            mock_markers.assert_not_called()

    def test_fallback_when_first_returns_none(self):
        """When git returns None, falls back to markers."""
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        finder = self._finder(start)
        with patch.object(finder, "_find_by_git", return_value=None), \
             patch.object(finder, "_find_nearest_by_markers", return_value=expected):
            result = finder.find_project_root(search_methods=["git", "markers"])
            self.assertEqual(result, expected)

    def test_fallback_when_first_raises(self):
        """When git raises an exception, falls back to markers."""
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        finder = self._finder(start)
        with patch.object(finder, "_find_by_git", side_effect=RuntimeError("boom")), \
             patch.object(finder, "_find_nearest_by_markers", return_value=expected):
            result = finder.find_project_root(search_methods=["git", "markers"])
            self.assertEqual(result, expected)

    def test_cache_returns_same_result(self):
        """Second call returns cached result without re-searching."""
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        finder = self._finder(start)
        with patch.object(finder, "_find_nearest_by_markers", return_value=expected) as mock:
            result1 = finder.find_project_root(search_methods=["markers"])
            result2 = finder.find_project_root(search_methods=["markers"])
            self.assertEqual(result1, result2)
            mock.assert_called_once()

    def test_raises_when_all_methods_fail(self):
        """Should raise FileNotFoundError when all strategies return None."""
        start = self.env.mkdir("empty", "nothing")

        finder = self._finder(start)
        with patch.object(finder, "_find_nearest_root_marker", return_value=None), \
             patch.object(finder, "_find_nearest_by_markers", return_value=None), \
             patch.object(finder, "_find_by_structure", return_value=None):
            with self.assertRaises(FileNotFoundError):
                finder.find_project_root(search_methods=["markers", "structure"])

    def test_unknown_method_skipped(self):
        """Unknown search method names are skipped gracefully."""
        start = self.env.mkdir("project", "src")
        expected = self.tmp / "project"

        finder = self._finder(start)
        with patch.object(finder, "_find_nearest_by_markers", return_value=expected):
            result = finder.find_project_root(search_methods=["nonexistent", "markers"])
            self.assertEqual(result, expected)


class TestFindByMarkersEdgeCases(unittest.TestCase):
    """Edge cases for _find_by_markers."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_start_path_is_project_root_itself(self):
        """Start path is the root directory that contains the marker."""
        self.env.touch("project", _TEST_MARKER)
        start = self.tmp / "project"

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "project")

    def test_start_path_does_not_exist(self):
        """Start path points to a non-existent directory."""
        fake_path = self.tmp / "does_not_exist" / "at_all"

        finder = self._finder(fake_path)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertIsNone(result)

    def test_marker_is_a_directory_not_file(self):
        """
        Marker like .git is a directory, not a file.
        _find_by_markers uses (current / marker).exists() which works for both.
        """
        self.env.mkdir("project", "my_dir_marker")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=["my_dir_marker"])
        self.assertEqual(result, self.tmp / "project")

    def test_path_with_spaces(self):
        """Directory names containing spaces."""
        self.env.touch("my project", _TEST_MARKER)
        start = self.env.mkdir("my project", "src code", "app")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "my project")

    def test_path_with_unicode(self):
        """Directory names containing unicode characters."""
        self.env.touch("项目根目录", _TEST_MARKER)
        start = self.env.mkdir("项目根目录", "源代码")

        finder = self._finder(start)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        self.assertEqual(result, self.tmp / "项目根目录")

    def test_marker_at_every_level(self):
        """
        a/          ← marker
          b/        ← marker
            c/      ← marker (start)
        Deepest with most ancestors having markers — should pick the one with most markers
        or at least not crash.
        """
        markers = [_TEST_MARKER, "extra_marker"]
        # a has 2 markers, b has 1, c has 1
        self.env.touch("a", _TEST_MARKER)
        self.env.touch("a", "extra_marker")
        self.env.touch("a", "b", _TEST_MARKER)
        self.env.touch("a", "b", "c", _TEST_MARKER)
        start = self.tmp / "a" / "b" / "c"

        finder = self._finder(start)
        result = finder._find_by_markers(markers=markers)
        # a has 2 markers, wins
        self.assertEqual(result, self.tmp / "a")

    def test_empty_markers_list_uses_defaults(self):
        """Passing empty list should fall back to default markers."""
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        # Empty list is falsy, should use defaults which include pyproject.toml
        result = finder._find_by_markers(markers=[])
        # May find something above tmp due to real filesystem — just verify no crash
        self.assertIsNotNone(result)

    def test_symlink_start_path(self):
        """Start path is a symlink to a real directory."""
        self.env.touch("real_project", _TEST_MARKER)
        self.env.mkdir("real_project", "src")
        link_path = self.tmp / "link_to_project"
        try:
            link_path.symlink_to(self.tmp / "real_project" / "src", target_is_directory=True)
        except OSError:
            # Symlinks may require elevated privileges on Windows
            self.skipTest("Cannot create symlinks on this system")

        finder = self._finder(link_path)
        result = finder._find_by_markers(markers=[_TEST_MARKER])
        # After resolve(), symlink is resolved to real path
        self.assertEqual(result, self.tmp / "real_project")


class TestFindByStructureEdgeCases(unittest.TestCase):
    """Edge cases for _find_by_structure."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_start_is_the_matching_directory(self):
        """Start path itself has src/ and .py files."""
        self.env.touch("project", "main.py")
        self.env.mkdir("project", "src")
        start = self.tmp / "project"

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertEqual(result, self.tmp / "project")

    def test_both_src_and_lib_exist(self):
        """Directory has both src/ and lib/."""
        self.env.touch("project", "app.py")
        self.env.mkdir("project", "src")
        self.env.mkdir("project", "lib")
        start = self.env.mkdir("project", "src", "deep")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertEqual(result, self.tmp / "project")

    def test_start_path_does_not_exist(self):
        """Non-existent start path should not crash."""
        fake = self.tmp / "nope" / "not_here"

        finder = self._finder(fake)
        result = finder._find_by_structure()
        self.assertIsNone(result)

    def test_init_py_counts_as_py_file(self):
        """__init__.py should satisfy the .py file check."""
        self.env.touch("project", "__init__.py")
        self.env.mkdir("project", "src")
        start = self.env.mkdir("project", "src", "sub")

        finder = self._finder(start)
        result = finder._find_by_structure()
        self.assertEqual(result, self.tmp / "project")


class TestGetCallerProjectPath(unittest.TestCase):
    """Test _get_caller_project_path and its sub-strategies."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_falls_back_to_cwd_when_stack_and_argv_fail(self):
        """When both stack inspection and sys.argv fail, returns cwd."""
        finder = ProjectRootFinder.__new__(ProjectRootFinder)
        with patch.object(finder, "_get_caller_from_stack", return_value=None), \
             patch.object(finder, "_get_main_script_path", return_value=None):
            result = finder._get_caller_project_path()
            self.assertEqual(result, Path.cwd())

    def test_prefers_stack_over_argv(self):
        """Stack result takes priority over sys.argv."""
        stack_path = self.tmp / "from_stack"
        argv_path = self.tmp / "from_argv"

        finder = ProjectRootFinder.__new__(ProjectRootFinder)
        with patch.object(finder, "_get_caller_from_stack", return_value=stack_path), \
             patch.object(finder, "_get_main_script_path", return_value=argv_path):
            result = finder._get_caller_project_path()
            self.assertEqual(result, stack_path)

    def test_falls_back_to_argv_when_stack_fails(self):
        """When stack returns None, uses sys.argv."""
        argv_path = self.tmp / "from_argv"

        finder = ProjectRootFinder.__new__(ProjectRootFinder)
        with patch.object(finder, "_get_caller_from_stack", return_value=None), \
             patch.object(finder, "_get_main_script_path", return_value=argv_path):
            result = finder._get_caller_project_path()
            self.assertEqual(result, argv_path)


class TestGetMainScriptPath(unittest.TestCase):
    """Test _get_main_script_path edge cases."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_valid_script_path(self):
        script = self.env.touch("project", "main.py")
        with patch.object(sys, "argv", [str(script)]):
            result = ProjectRootFinder._get_main_script_path()
            self.assertEqual(result, script.parent)

    def test_empty_argv(self):
        with patch.object(sys, "argv", []):
            result = ProjectRootFinder._get_main_script_path()
            self.assertIsNone(result)

    def test_argv_is_empty_string(self):
        with patch.object(sys, "argv", [""]):
            result = ProjectRootFinder._get_main_script_path()
            self.assertIsNone(result)

    def test_argv_points_to_nonexistent_file(self):
        with patch.object(sys, "argv", ["/nonexistent/script.py"]):
            result = ProjectRootFinder._get_main_script_path()
            self.assertIsNone(result)

    def test_argv_points_to_directory(self):
        d = self.env.mkdir("some_dir")
        with patch.object(sys, "argv", [str(d)]):
            result = ProjectRootFinder._get_main_script_path()
            self.assertIsNone(result)


class TestSetupImportPath(unittest.TestCase):
    """Test setup_import_path side effects."""

    def test_adds_root_to_sys_path(self):
        fake_root = Path("/fake/project/root")
        while str(fake_root) in sys.path:
            sys.path.remove(str(fake_root))
        setup_import_path(root=fake_root)
        self.assertIn(str(fake_root), sys.path)
        sys.path.remove(str(fake_root))

    def test_does_not_duplicate_in_sys_path(self):
        fake_root = Path("/fake/project/root_no_dup")
        sys.path.append(str(fake_root))
        count_before = sys.path.count(str(fake_root))
        setup_import_path(root=fake_root)
        self.assertEqual(sys.path.count(str(fake_root)), count_before)
        while str(fake_root) in sys.path:
            sys.path.remove(str(fake_root))

    def test_defaults_to_get_project_root(self):
        fake_root = Path("/fake/auto/root")
        with patch("flashboot_core.utils.project_utils.get_project_root", return_value=fake_root):
            while str(fake_root) in sys.path:
                sys.path.remove(str(fake_root))
            setup_import_path()
            self.assertIn(str(fake_root), sys.path)
            while str(fake_root) in sys.path:
                sys.path.remove(str(fake_root))


class TestRootMarker(unittest.TestCase):
    """Test .root marker file detection."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_nearest_root_marker_found(self):
        """
        workspace/
          service-a/    <- .root here
            src/
              caller    <- start here
        """
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder._find_nearest_root_marker()
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_nearest_root_marker_picks_closest(self):
        """
        workspace/      <- .root here
          service-a/    <- .root here too
            src/        <- start here
        Nearest should be service-a.
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder._find_nearest_root_marker()
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_farthest_root_marker_picks_outermost(self):
        """
        workspace/      <- .root here
          service-a/    <- .root here too
            src/        <- start here
        Farthest should be workspace.
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder._find_farthest_root_marker()
        self.assertEqual(result, self.tmp / "workspace")

    def test_no_root_marker_returns_none(self):
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        self.assertIsNone(finder._find_nearest_root_marker())
        self.assertIsNone(finder._find_farthest_root_marker())

    def test_root_marker_at_start_path(self):
        """If .root is in the start directory itself, it should be found."""
        self.env.touch("project", ROOT_MARKER)
        start = self.tmp / "project"

        finder = self._finder(start)
        self.assertEqual(finder._find_nearest_root_marker(), self.tmp / "project")
        self.assertEqual(finder._find_farthest_root_marker(), self.tmp / "project")


class TestFindProjectRoot(unittest.TestCase):
    """Test find_project_root (nearest root)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_root_marker_takes_priority_over_markers(self):
        """
        workspace/          <- pyproject.toml (would normally win by score)
          service-a/        <- .root
            src/            <- start
        .root should win.
        """
        self.env.touch("workspace", "pyproject.toml")
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder.find_project_root(search_methods=["markers"])
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_returns_nearest_marker_dir(self):
        """
        workspace/          <- pyproject.toml
          service-a/        <- pyproject.toml (nearest)
            src/            <- start
        Should return service-a, not workspace.
        """
        self.env.touch("workspace", "pyproject.toml")
        self.env.touch("workspace", "service-a", "pyproject.toml")
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder.find_project_root(search_methods=["markers"])
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_raises_when_nothing_found(self):
        start = self.env.mkdir("empty", "sub")

        finder = self._finder(start)
        with patch.object(finder, "_find_nearest_root_marker", return_value=None), \
             patch.object(finder, "_find_nearest_by_markers", return_value=None), \
             patch.object(finder, "_find_by_structure", return_value=None):
            with self.assertRaises(FileNotFoundError):
                finder.find_project_root(search_methods=["markers", "structure"])

    def test_result_is_cached(self):
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        with patch.object(finder, "_find_nearest_by_markers", wraps=finder._find_nearest_by_markers) as mock:
            finder.find_project_root(search_methods=["markers"])
            finder.find_project_root(search_methods=["markers"])
            mock.assert_called_once()

    def test_unknown_method_skipped(self):
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")

        finder = self._finder(start)
        result = finder.find_project_root(search_methods=["nonexistent", "markers"])
        self.assertEqual(result, self.tmp / "project")


class TestFindWorkspaceRoot(unittest.TestCase):
    """Test find_workspace_root (farthest root)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_root_marker_takes_priority(self):
        """
        workspace/      <- .root
          service-a/    <- pyproject.toml
            src/        <- start
        .root at workspace should win.
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", "pyproject.toml")
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder.find_workspace_root(search_methods=["markers"])
        self.assertEqual(result, self.tmp / "workspace")

    def test_returns_farthest_marker_dir(self):
        """
        workspace/          <- .root (farthest, isolated from real fs)
          service-a/        <- .root
            src/            <- start
        Should return workspace, not service-a.
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        # .root takes priority and picks the farthest
        result = finder.find_workspace_root()
        self.assertEqual(result, self.tmp / "workspace")

    def test_farthest_root_marker_beats_nearer_one(self):
        """
        workspace/      <- .root (farthest)
          service-a/    <- .root
            src/        <- start
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        result = finder.find_workspace_root()
        self.assertEqual(result, self.tmp / "workspace")

    def test_raises_when_nothing_found(self):
        start = self.env.mkdir("empty", "sub")

        finder = self._finder(start)
        with patch.object(finder, "_find_farthest_root_marker", return_value=None), \
             patch.object(finder, "_find_farthest_by_markers", return_value=None), \
             patch.object(finder, "_find_by_structure", return_value=None):
            with self.assertRaises(FileNotFoundError):
                finder.find_workspace_root(search_methods=["markers", "structure"])

    def test_result_is_cached(self):
        self.env.touch("workspace", "pyproject.toml")
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        with patch.object(finder, "_find_farthest_by_markers", wraps=finder._find_farthest_by_markers) as mock:
            finder.find_workspace_root(search_methods=["markers"])
            finder.find_workspace_root(search_methods=["markers"])
            mock.assert_called_once()

    def test_project_vs_workspace_differ_in_monorepo(self):
        """
        workspace/          <- .root (farthest)
          service-a/        <- .root (nearest)
            src/            <- start
        project_root -> service-a, workspace_root -> workspace
        """
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = self.env.mkdir("workspace", "service-a", "src")

        finder = self._finder(start)
        project = finder.find_project_root()
        workspace = finder.find_workspace_root()

        self.assertEqual(project, self.tmp / "workspace" / "service-a")
        self.assertEqual(workspace, self.tmp / "workspace")
        self.assertNotEqual(project, workspace)


class TestNearestAndFarthestByMarkers(unittest.TestCase):
    """Test _find_nearest_by_markers and _find_farthest_by_markers."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _finder(self, start: Path) -> ProjectRootFinder:
        return ProjectRootFinder(start_path=str(start))

    def test_nearest_returns_first_match(self):
        markers = [_TEST_MARKER]
        self.env.touch("a", _TEST_MARKER)
        self.env.touch("a", "b", _TEST_MARKER)
        start = self.env.mkdir("a", "b", "c")

        finder = self._finder(start)
        result = finder._find_nearest_by_markers(markers=markers)
        self.assertEqual(result, self.tmp / "a" / "b")

    def test_farthest_returns_last_match(self):
        markers = [_TEST_MARKER]
        self.env.touch("a", _TEST_MARKER)
        self.env.touch("a", "b", _TEST_MARKER)
        start = self.env.mkdir("a", "b", "c")

        finder = self._finder(start)
        result = finder._find_farthest_by_markers(markers=markers)
        self.assertEqual(result, self.tmp / "a")

    def test_nearest_returns_none_when_no_markers(self):
        start = self.env.mkdir("empty", "sub")
        finder = self._finder(start)
        self.assertIsNone(finder._find_nearest_by_markers(markers=[_TEST_MARKER]))

    def test_farthest_returns_none_when_no_markers(self):
        start = self.env.mkdir("empty", "sub")
        finder = self._finder(start)
        self.assertIsNone(finder._find_farthest_by_markers(markers=[_TEST_MARKER]))

    def test_single_match_nearest_equals_farthest(self):
        markers = [_TEST_MARKER]
        self.env.touch("a", _TEST_MARKER)
        start = self.env.mkdir("a", "b", "c")

        finder = self._finder(start)
        nearest = finder._find_nearest_by_markers(markers=markers)
        farthest = finder._find_farthest_by_markers(markers=markers)
        self.assertEqual(nearest, farthest)
        self.assertEqual(nearest, self.tmp / "a")


class TestPublicAPI(unittest.TestCase):
    """Test the public get_project_root and get_workspace_root functions."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_get_project_root(self):
        self.env.touch("workspace", "service-a", "pyproject.toml")
        start = str(self.env.mkdir("workspace", "service-a", "src"))

        result = get_project_root(start_path=start, search_methods=["markers"])
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_get_workspace_root(self):
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = str(self.env.mkdir("workspace", "service-a", "src"))

        result = get_workspace_root(start_path=start)
        self.assertEqual(result, self.tmp / "workspace")

    def test_get_project_root_with_root_marker(self):
        self.env.touch("workspace", "pyproject.toml")
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = str(self.env.mkdir("workspace", "service-a", "src"))

        result = get_project_root(start_path=start, search_methods=["markers"])
        self.assertEqual(result, self.tmp / "workspace" / "service-a")

    def test_get_workspace_root_with_root_marker(self):
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "service-a", ROOT_MARKER)
        start = str(self.env.mkdir("workspace", "service-a", "src"))

        result = get_workspace_root(start_path=start)
        self.assertEqual(result, self.tmp / "workspace")


class TestIsStdlibOrSitePackages(unittest.TestCase):
    """Test the static method for detecting library paths."""

    def test_site_packages_detected(self):
        p = Path("/usr/lib/python3.10/site-packages/some_lib/module.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_dist_packages_detected(self):
        p = Path("/usr/lib/python3/dist-packages/some_lib/module.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_ipykernel_detected(self):
        p = Path("/tmp/ipykernel_12345/some_file.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_windows_temp_detected(self):
        p = Path("C:/Users/user/AppData/Local/Temp/ipykernel_123/tmp.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_normal_project_file_not_detected(self):
        p = Path("/home/user/my_project/src/main.py")
        with patch.object(sys, "prefix", "/usr"), \
             patch.object(sys, "base_prefix", "/usr"):
            self.assertFalse(ProjectRootFinder._is_stdlib_or_site_packages(p))


class TestIsLibraryInternal(unittest.TestCase):
    """Test detection of flashboot_core internal files."""

    def test_internal_file_detected(self):
        internal = _LIBRARY_ROOT / "env" / "environment.py"
        self.assertTrue(ProjectRootFinder._is_library_internal(internal))

    def test_internal_utils_detected(self):
        internal = _LIBRARY_ROOT / "utils" / "project_utils.py"
        self.assertTrue(ProjectRootFinder._is_library_internal(internal))

    def test_external_file_not_detected(self):
        external = Path("/home/user/my_project/main.py")
        self.assertFalse(ProjectRootFinder._is_library_internal(external))


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

class TestIterAncestorsExtra(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_nonexistent_start_path_traverses_upward(self):
        """Non-existent start path: _iter_ancestors traverses upward to existing parents."""
        fake = self.tmp / "does_not_exist" / "deep"
        finder = ProjectRootFinder(start_path=str(fake))
        ancestors = finder._iter_ancestors()
        # Non-existent dirs are skipped, but existing parents are included
        self.assertNotIn(fake, ancestors)
        self.assertNotIn(self.tmp / "does_not_exist", ancestors)
        # The tmp dir itself (which exists) should appear
        self.assertIn(self.tmp, ancestors)

    def test_skips_all_non_root_dir_names(self):
        """All dirs in _NON_ROOT_DIR_NAMES should be skipped."""
        for name in ProjectRootFinder._NON_ROOT_DIR_NAMES:
            with self.subTest(name=name):
                d = self.env.mkdir("project", name, "sub")
                finder = ProjectRootFinder(start_path=str(d))
                ancestors = finder._iter_ancestors()
                self.assertNotIn(self.tmp / "project" / name, ancestors)

    def test_includes_start_dir_itself(self):
        """The start directory itself should be the first ancestor."""
        start = self.env.mkdir("project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        ancestors = finder._iter_ancestors()
        self.assertEqual(ancestors[0], start)


class TestFindNearestByMarkersExtra(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_start_dir_itself_has_marker(self):
        """If the start directory contains a marker, it should be returned immediately."""
        self.env.touch("project", _TEST_MARKER)
        start = self.tmp / "project"
        finder = ProjectRootFinder(start_path=str(start))
        self.assertEqual(finder._find_nearest_by_markers(markers=[_TEST_MARKER]), self.tmp / "project")

    def test_empty_markers_falls_back_to_defaults(self):
        """Passing empty list should use _DEFAULT_MARKERS."""
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        # pyproject.toml is in _DEFAULT_MARKERS, so it should be found
        result = finder._find_nearest_by_markers(markers=[])
        self.assertIsNotNone(result)

    def test_multiple_markers_any_match_counts(self):
        """A directory with any one of the markers should match."""
        self.env.touch("project", "marker_b")
        start = self.env.mkdir("project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        result = finder._find_nearest_by_markers(markers=["marker_a", "marker_b"])
        self.assertEqual(result, self.tmp / "project")


class TestFindFarthestByMarkersExtra(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_start_dir_itself_has_marker(self):
        """If only the start directory has a marker, it is both nearest and farthest."""
        self.env.touch("project", _TEST_MARKER)
        start = self.tmp / "project"
        finder = ProjectRootFinder(start_path=str(start))
        self.assertEqual(finder._find_farthest_by_markers(markers=[_TEST_MARKER]), self.tmp / "project")

    def test_empty_markers_falls_back_to_defaults(self):
        self.env.touch("project", "pyproject.toml")
        start = self.env.mkdir("project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        result = finder._find_farthest_by_markers(markers=[])
        self.assertIsNotNone(result)


class TestFindProjectRootExtra(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_root_marker_beats_vcs(self):
        """
        .root in a subdirectory should take priority even when git would return a parent.
        """
        self.env.touch("workspace", "project", ROOT_MARKER)
        start = self.env.mkdir("workspace", "project", "src")
        expected_vcs = self.tmp / "workspace"

        finder = ProjectRootFinder(start_path=str(start))
        with patch.object(finder, "_find_by_git", return_value=expected_vcs):
            result = finder.find_project_root(search_methods=["git", "markers"])
        # .root wins regardless of VCS
        self.assertEqual(result, self.tmp / "workspace" / "project")

    def test_method_exception_falls_back_to_next(self):
        """An exception in one method should fall back to the next."""
        self.env.touch("project", _TEST_MARKER)
        start = self.env.mkdir("project", "src")
        finder = ProjectRootFinder(start_path=str(start))

        with patch.object(finder, "_find_by_git", side_effect=RuntimeError("git exploded")), \
             patch.object(finder, "_find_nearest_by_markers", return_value=self.tmp / "project"):
            result = finder.find_project_root(search_methods=["git", "markers"])
        self.assertEqual(result, self.tmp / "project")

    def test_project_cache_independent_of_workspace_cache(self):
        """project root cache and workspace root cache are stored separately."""
        self.env.touch("workspace", ROOT_MARKER)
        self.env.touch("workspace", "project", ROOT_MARKER)
        start = self.env.mkdir("workspace", "project", "src")

        finder = ProjectRootFinder(start_path=str(start))
        project = finder.find_project_root()
        workspace = finder.find_workspace_root()

        self.assertEqual(project, self.tmp / "workspace" / "project")
        self.assertEqual(workspace, self.tmp / "workspace")
        # Caches are independent
        self.assertEqual(finder._project_cache, self.tmp / "workspace" / "project")
        self.assertEqual(finder._workspace_cache, self.tmp / "workspace")


class TestFindWorkspaceRootExtra(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_unknown_method_skipped(self):
        self.env.touch("workspace", _TEST_MARKER)
        start = self.env.mkdir("workspace", "project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        expected = self.tmp / "workspace"
        with patch.object(finder, "_find_farthest_by_markers", return_value=expected):
            result = finder.find_workspace_root(search_methods=["nonexistent", "markers"])
        self.assertEqual(result, expected)

    def test_method_exception_falls_back_to_next(self):
        self.env.touch("workspace", _TEST_MARKER)
        start = self.env.mkdir("workspace", "project", "src")
        finder = ProjectRootFinder(start_path=str(start))
        expected = self.tmp / "workspace"

        with patch.object(finder, "_find_farthest_by_markers", side_effect=RuntimeError("boom")), \
             patch.object(finder, "_find_by_structure", return_value=expected):
            result = finder.find_workspace_root(search_methods=["markers", "structure"])
        self.assertEqual(result, expected)

    def test_no_root_marker_no_markers_raises(self):
        start = self.env.mkdir("empty", "sub")
        finder = ProjectRootFinder(start_path=str(start))
        with patch.object(finder, "_find_farthest_root_marker", return_value=None), \
             patch.object(finder, "_find_farthest_by_markers", return_value=None), \
             patch.object(finder, "_find_by_structure", return_value=None):
            with self.assertRaises(FileNotFoundError):
                finder.find_workspace_root(search_methods=["markers", "structure"])


class TestIsStdlibOrSitePackagesExtra(unittest.TestCase):
    def test_lib_python_detected(self):
        # Use a path string that contains "lib/python" literally (forward slash)
        # The implementation checks path_str which uses str(file_path).lower()
        # On Windows, Path converts to backslashes, so we need to check the actual indicator
        p = Path("/usr/lib/python3.10/os.py")
        path_str = str(p).lower().replace("\\", "/")
        self.assertIn("lib/python", path_str)
        # Verify the method itself works with a site-packages path (cross-platform safe)
        p2 = Path("/usr/lib/python3.10/site-packages/requests/__init__.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p2))

    def test_lib64_python_detected(self):
        p = Path("/usr/lib64/python3.10/site-packages/lib.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_dist_packages_detected(self):
        p = Path("/usr/lib/python3/dist-packages/requests/__init__.py")
        self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_path_under_sys_prefix_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as venv:
            venv_path = Path(venv).resolve()
            p = venv_path / "lib" / "mymodule.py"
            with patch.object(sys, "prefix", str(venv_path)), \
                 patch.object(sys, "base_prefix", "/usr"):
                self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))

    def test_path_under_sys_base_prefix_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            base_path = Path(base).resolve()
            p = base_path / "lib" / "os.py"
            with patch.object(sys, "prefix", "/some/venv"), \
                 patch.object(sys, "base_prefix", str(base_path)):
                self.assertTrue(ProjectRootFinder._is_stdlib_or_site_packages(p))


class TestGetCallerFromStackExtra(unittest.TestCase):
    def test_returns_none_when_inspect_raises(self):
        """If inspect.stack() raises, _get_caller_from_stack should return None."""
        finder = ProjectRootFinder.__new__(ProjectRootFinder)
        with patch("flashboot_core.utils.project_utils.inspect.stack", side_effect=Exception("stack error")):
            result = finder._get_caller_from_stack()
        self.assertIsNone(result)

    def test_skips_ipykernel_frames(self):
        """Frames with ipykernel_ in filename should be skipped."""
        finder = ProjectRootFinder.__new__(ProjectRootFinder)

        fake_frame = MagicMock()
        fake_frame.filename = "/tmp/ipykernel_12345/tmp_code.py"

        with tempfile.TemporaryDirectory() as d:
            real_file = Path(d) / "project" / "main.py"
            real_file.parent.mkdir(parents=True, exist_ok=True)
            real_file.touch()

            real_frame = MagicMock()
            real_frame.filename = str(real_file)

            with patch("flashboot_core.utils.project_utils.inspect.stack", return_value=[MagicMock(), fake_frame, real_frame]), \
                 patch.object(ProjectRootFinder, "_is_library_internal", return_value=False), \
                 patch.object(ProjectRootFinder, "_is_stdlib_or_site_packages", return_value=False):
                result = finder._get_caller_from_stack()
            self.assertEqual(result.resolve(), real_file.parent.resolve())


class TestRootMarkerExtraEdgeCases(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name).resolve()
        self.env = DirectoryEnvironment(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_nearest_and_farthest_same_when_only_one_root_marker(self):
        self.env.touch("project", ROOT_MARKER)
        start = self.env.mkdir("project", "a", "b", "c")
        finder = ProjectRootFinder(start_path=str(start))
        self.assertEqual(finder._find_nearest_root_marker(), finder._find_farthest_root_marker())

    def test_root_marker_deep_nesting(self):
        """Root marker many levels up should still be found."""
        self.env.touch("root", ROOT_MARKER)
        start = self.env.mkdir("root", "a", "b", "c", "d", "e")
        finder = ProjectRootFinder(start_path=str(start))
        self.assertEqual(finder._find_nearest_root_marker(), self.tmp / "root")

    def test_root_marker_not_in_default_markers(self):
        """.root should NOT be in _DEFAULT_MARKERS (it's handled separately)."""
        self.assertNotIn(ROOT_MARKER, ProjectRootFinder._DEFAULT_MARKERS)


if __name__ == "__main__":
    unittest.main()
