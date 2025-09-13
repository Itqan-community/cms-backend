import pathlib

from django.apps import apps
from django.conf import settings
from ninja import NinjaAPI


def auto_discover_ninja_routers(ninja_api: NinjaAPI, pattern: str):
    for app in apps.get_app_configs():
        if app.name not in settings.LOCAL_APPS:
            continue
        views_module = pathlib.Path(app.path) / pattern
        if not views_module.exists():
            continue
        if views_module.is_file():
            try:
                ninja_api.add_router("/", f"{app.name}.{pattern}.{views_module.stem}.router")
            except Exception:
                pass
        if views_module.is_dir():
            for view_file in views_module.glob("**/*.py"):
                try:
                    ninja_api.add_router("/", f"{app.name}.{pattern}.{view_file.stem}.router")
                except Exception:
                    pass
