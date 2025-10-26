import pathlib

from django.apps import apps
from django.conf import settings
from ninja import NinjaAPI


def auto_discover_ninja_routers(ninja_api: NinjaAPI, pattern: str) -> None:
    """
    Auto-discover and register Ninja routers from local Django apps.
    """
    for app in apps.get_app_configs():
        if app.name not in settings.LOCAL_APPS:
            continue
        views_module = pathlib.Path(app.path) / pattern
        if not views_module.exists():
            continue
        if views_module.is_file():
            ninja_api.add_router("/", f"{app.name}.{pattern}.{views_module.stem}.router")
        if views_module.is_dir():
            for view_file in views_module.glob("**/*.py"):
                if view_file.stem == "__init__":
                    try:
                        ninja_api.add_router("/", f"{app.name}.{pattern}.router")
                    except ImportError:
                        pass
                else:
                    # Skip files starting with underscore (utility files)
                    if not view_file.stem.startswith("_"):
                        ninja_api.add_router("/", f"{app.name}.{pattern}.{view_file.stem}.router")
