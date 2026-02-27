import unittest
from flashboot_core.odbc.database.mysql import MySQLDatabaseManager
from flashboot_core.types.odbc import MySQLConfig


class TestMySQLDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.database_manager = MySQLDatabaseManager(
            MySQLConfig()
        )

    def test_get_database(self):
        database = self.database_manager.get_database()
        self.assertIsNotNone(database)

    def test_get_connection(self):
        connection = self.database_manager.open_connection()
        self.assertIsNotNone(connection)

    def test_close_connection(self):
        connection = self.database_manager.open_connection()
        self.assertTrue(self.database_manager.close_connection(connection))

    def test_connection_context(self):
        with self.database_manager.connection_context() as connection:
            self.assertIsNotNone(connection)
