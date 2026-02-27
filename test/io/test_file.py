import unittest
from flashboot_core.io import File


class TestFile(unittest.TestCase):

    def test_get_name(self):
        file = File("test.txt")
        self.assertEqual(file.get_name(), "test.txt")

    def test_get_absolute_path(self):
        file = File("test.txt")
        self.assertNotEqual(file.get_absolute_path(), "test.txt")
