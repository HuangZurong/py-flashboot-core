import os
import re
import typing
from pathlib import Path
from typing import Dict, List, Any, Union, Optional

import yaml
from loguru import logger

from flashboot_core.env.environment import Environment
from flashboot_core.env.property_source import PropertySource
from flashboot_core.env.property_source_loader import PropertySourceLoader
from flashboot_core.io.resource import Resource
from flashboot_core.utils import project_utils


class SimpleYamlLoader:
    loaded_configs = {}
    _cache = {}

    def __init__(self, config_dir: Union[str, Path] = None):
        self.config_dir = Path(config_dir) if config_dir else self.find_config_dir()
        assert self.config_dir is not None and self.config_dir.exists(), "Config dir not exists, please check!"
        self.env = Environment()

    @staticmethod
    def find_config_dir() -> Optional[Path]:
        try:
            project_root_path = project_utils.get_root_path()
            possible_config_dirs = [
                project_root_path / "resources" / "configs",
                project_root_path / "resources" / "config",
                project_root_path / "resource" / "configs",
                project_root_path / "resource" / "config",
                project_root_path / "resources",
                project_root_path / "resource",
                project_root_path / "configs",
                project_root_path / "config",
                project_root_path / "src" / "resources" / "configs",
                project_root_path / "src" / "resources" / "config",
                project_root_path / "src" / "resource" / "configs",
                project_root_path / "src" / "resource" / "config",
                project_root_path / "src" / "resources",
                project_root_path / "src" / "resource",
                project_root_path / "src" / "configs",
                project_root_path / "src" / "config",
            ]
            possible_profile_filenames = [
                f"application-prod.yml",
                f"application-prod.yaml",
                f"application-test.yml",
                f"application-test.yaml",
                f"application-dev.yml",
                f"application-dev.yaml",
                f"prod.yml",
                f"prod.yaml",
                f"test.yml",
                f"test.yaml",
                f"dev.yml",
                f"dev.yaml",
                f"application.yml",
                f"application.yaml",
            ]
            for config_dir in possible_config_dirs:
                for profile_filename in possible_profile_filenames:
                    file_path = Path(config_dir) / profile_filename
                    if file_path.exists():
                        return config_dir
            return project_root_path
        except FileNotFoundError:
            ...
        return None

    def load_config(self, filename: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        if filename in self.loaded_configs:
            return self.loaded_configs[filename]

        file_path = self.config_dir / filename

        if not file_path.exists():
            self.loaded_configs[filename] = None
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.loaded_configs[filename] = config
                return config
        except Exception as e:
            logger.error(f"Failed to load config file {filename}: {e}")
            self.loaded_configs[filename] = None
            return None

    def load_profile_config(self, profile: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        possible_files = [
            f"application-{profile}.yml",
            f"application-{profile}.yaml",
            f"{profile}.yml",
            f"{profile}.yaml"
        ]

        for filename in possible_files:
            config = self.load_config(filename)
            if config:
                return config

        return None

    def deep_merge(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()

        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(base[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def resolve_placeholders(config: Dict[str, Any]) -> Union[Dict[str, Any], List[Any]]:

        def get_config_value(_config: Dict, key_path: str) -> Optional[str]:
            keys = key_path.split(".")
            value = _config

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return str(value) if value is not None else None

        def resolve_value(value) -> Union[Dict[str, Any], List[Any]]:
            if isinstance(value, str):
                # match ${VAR_NAME:default} or ${VAR_NAME} pattern
                pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

                def replacer(match):
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""

                    # get from environment variables
                    env_value = os.getenv(var_name)
                    # get from system properties
                    if env_value is None:
                        env_value = get_config_value(config, var_name)

                    return env_value if env_value is not None else default_value

                return re.sub(pattern, replacer, value)
            elif isinstance(value, Dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, List):
                return [resolve_value(item) for item in value]
            else:
                return value

        return resolve_value(config)

    def load_and_merge_config(self, profiles: List[str]) -> Union[Dict[str, Any], List[Any]]:
        merged_config = self.load_config("application.yml") or self.load_config("application.yaml") or {}

        for profile in profiles:
            profile_config = self.load_profile_config(profile)
            if profile_config:
                merged_config = self.deep_merge(merged_config, profile_config)

        merged_config = self.resolve_placeholders(merged_config)
        return merged_config

    def load(self, profiles: List[str] = None) -> Union[Dict[str, Any], List[Any]]:
        if not profiles:
            profiles = self.env.get_active_profiles()

        cache_key = ",".join(profiles)
        if cache_key in self._cache:
            return self._cache[cache_key]

        merged_config = self.load_and_merge_config(profiles)
        self._cache[cache_key] = merged_config

        return merged_config


# TODO 使用YamlPropertySourceLoader而不是SimpleYamlLoader
class YamlPropertySourceLoader(PropertySourceLoader):

    def get_file_extensions(self) -> typing.List[str]:
        return ["yml", "yaml"]

    def load(self, name: str, source: Resource) -> PropertySource:
        pass
