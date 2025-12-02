import contextlib
import pathlib

from django.apps import apps
from django.conf import settings
from ninja import NinjaAPI


def auto_discover_ninja_routers(ninja_api: NinjaAPI, pattern: str) -> None:
    """
    Auto-discover and register Ninja routers from local Django apps.

    pattern may be a filesystem-like subpath (e.g. "api/internal" or "views").
    This function scans that path within each LOCAL_APPS package and registers
    dotted import paths like "apps.content.api.internal.<module>.router".
    """
    for app in apps.get_app_configs():
        if app.name not in settings.LOCAL_APPS:
            continue

        # Resolve filesystem path to scan for this app
        pattern_path = pathlib.Path(pattern)
        base_dir = pathlib.Path(app.path) / pattern_path
        if not base_dir.exists():
            continue

        # Build dotted module prefix for imports
        module_prefix = ".".join((app.name, *pattern_path.parts))

        if base_dir.is_file():
            ninja_api.add_router("/", f"{module_prefix}.{base_dir.stem}.router")
            continue

        # Walk all python files in the directory
        for py_file in base_dir.glob("**/*.py"):
            # Skip hidden/utility files
            if py_file.name.startswith("_") and py_file.stem != "__init__":
                continue

            relative_module = py_file.relative_to(base_dir).with_suffix("")
            if relative_module.name == "__init__":
                # Try to register package-level router if exists
                with contextlib.suppress(ImportError):
                    ninja_api.add_router("/", f"{module_prefix}.router")
                continue

            rel_module_str = ".".join(relative_module.parts)
            ninja_api.add_router("/", f"{module_prefix}.{rel_module_str}.router")
