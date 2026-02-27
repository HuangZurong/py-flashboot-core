from functools import wraps
from typing import Union, Callable, get_type_hints
from pathlib import Path
from commons_lang import object_utils

from .environment import Environment
from .yaml_property_source_loader import SimpleYamlLoader


def property_bind(property_path: str, config_dir: Union[str, Path] = None) -> Callable:
    yaml_loader = SimpleYamlLoader(config_dir)

    def decorator(cls):
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            config = yaml_loader.load()
            prop = object_utils.get(config, property_path)
            if not prop:
                return
            if isinstance(prop, dict):
                fields = get_type_hints(cls).keys()
                for key, value in prop.items():
                    if key in fields:
                        # TODO 暂时未考虑属性为类对象的情况，统一当做dict处理
                        setattr(self, key, value)
            # TODO 考虑列表的情况

        cls.__init__ = new_init
        return cls

    return decorator


__all__ = [
    "Environment",
    "property_bind",
]
