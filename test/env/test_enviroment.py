import os
import unittest

from flashboot_core.env import Environment
from flashboot_core.env.environment import ACTIVE_PROFILES_PROPERTY_NAME


class TestEnvironment(unittest.TestCase):

    def setUp(self):
        os.environ[ACTIVE_PROFILES_PROPERTY_NAME] = "prod"
        self.environment = Environment()

    def tearDown(self):
        ...

    def test_get_active_profiles(self):
        self.assertEqual(Environment.get_active_profiles(), ["prod"])

    def test_get_active_profiles_with_unknown_args(self):
        import sys
        # Clear env var to force argument parsing
        if ACTIVE_PROFILES_PROPERTY_NAME in os.environ:
            del os.environ[ACTIVE_PROFILES_PROPERTY_NAME]
        
        original_argv = sys.argv
        # Simulate uvicorn arguments
        sys.argv = ["main.py", "--host", "0.0.0.0", "--profiles.active", "test"]
        try:
            self.assertEqual(Environment.get_active_profiles(), ["test"])
        finally:
            sys.argv = original_argv

