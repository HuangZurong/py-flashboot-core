import unittest
from typing import List, Any
from flashboot_core.env import property_bind


class Profile():
    username: str
    password: str


@property_bind("server")
class MySimpleModel:
    port: int
    name: str
    hosts: List[str]
    ratio: float
    profile: Profile


@property_bind("services")
class MyServiceModel:
    name: str
    url: str
    timeout: int

    def __init__(self, name: str, /, **data: Any):
        super().__init__(**data)
        self.name = name


class TestPropertySourceLoader(unittest.TestCase):

    def test_simple_model(self):
        model = MySimpleModel()
        self.assertEqual(model.port, 8080)
        self.assertEqual(model.name, "web-server")
        self.assertEqual(model.hosts, [1, 2])
        self.assertEqual(model.ratio, 0.5)
        self.assertEqual(model.profile.username, "admin")
        self.assertEqual(model.profile.password, "password")

    def test_service_model(self):
        model = MyServiceModel("service1")
        self.assertEqual(model.name, "my-service")
        self.assertEqual(model.url, "http://localhost:8080")
        self.assertEqual(model.timeout, 1000)
