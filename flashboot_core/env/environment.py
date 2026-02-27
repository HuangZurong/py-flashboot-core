import argparse
import os
from typing import Literal, Optional, get_args

from commons_lang.text import string_utils

ACTIVE_PROFILES_PROPERTY_NAME = "profiles.active"

Profile = Literal["dev", "test", "prod"]


class Environment(object):

    @staticmethod
    def get_active_profiles(default_profile: Optional[Profile] = "prod") -> list[str]:
        """
        Get the active profiles from the environment.
        The value may be comma-delimited.
        :return: The active profiles.
        """
        profiles = []
        active_profiles = os.getenv(ACTIVE_PROFILES_PROPERTY_NAME)
        if string_utils.is_blank(active_profiles):
            parser = argparse.ArgumentParser()
            parser.add_argument(
                f"--{ACTIVE_PROFILES_PROPERTY_NAME}",
                dest="active_profiles",
                help="The active profiles",
                default=default_profile,
                choices=list(map(lambda x: str(x), get_args(Profile))),
            )
            args, _ = parser.parse_known_args()
            active_profiles = args.active_profiles

        if string_utils.is_not_blank(active_profiles):
            profiles.extend(active_profiles.split(","))
        if len(profiles) == 0:
            raise RuntimeError("No active profiles found")
        return profiles
