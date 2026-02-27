"""Component scanning logic."""
import inspect
import pkgutil
from pathlib import Path

def find_components(base_package_path: str):
    """
    Scan a package for classes marked with the @component decorator.
    """
    components = []
    module_path = Path(base_package_path)

    for _, name, is_pkg in pkgutil.walk_packages([str(module_path)]):
        full_module_name = f"{module_path.name}.{name}"
        if is_pkg:
            components.extend(find_components(str(module_path / name)))
        else:
            module = __import__(full_module_name, fromlist=["*"])
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if getattr(obj, "_is_component", False):
                    components.append(obj)
    return components
