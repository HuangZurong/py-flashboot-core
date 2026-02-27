"""Application context responsible for managing the bean lifecycle."""

from typing import Dict, Any

class ApplicationContext:
    def __init__(self):
        self._bean_registry: Dict[str, Any] = {}

    def register_bean(self, name: str, instance: Any):
        """Register a bean instance."""
        if name in self._bean_registry:
            raise ValueError(f"Bean with name '{name}' already registered.")
        self._bean_registry[name] = instance

    def get_bean(self, name: str) -> Any:
        """Retrieve a bean by name."""
        if name not in self._bean_registry:
            raise ValueError(f"Bean with name '{name}' not found.")
        return self._bean_registry[name]

    def get_all_beans(self) -> Dict[str, Any]:
        """Return all registered beans."""
        return self._bean_registry.copy()
