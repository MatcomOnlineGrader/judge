# flake8: noqa: F401

from __future__ import unicode_literals

from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "api"

    def ready(self):
        from .signals.cache import (
            clean_five_top_rated_profiles,
            clean_ten_most_recent_posts,
        )
        from .signals.main import create_profile_for_user
