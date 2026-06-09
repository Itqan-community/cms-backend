"""Custom Gunicorn worker classes."""

from uvicorn.workers import UvicornWorker


class DjangoUvicornWorker(UvicornWorker):
    """Uvicorn worker tuned for Django's ASGI app.

    Django's ASGI application only handles the ``http`` protocol, not
    ``lifespan``. With Uvicorn's default ``lifespan="auto"`` this logs a
    harmless but noisy "Django can only handle ASGI/HTTP connections, not
    lifespan." message on every worker boot. Django manages its own
    startup/shutdown, so we disable lifespan entirely.
    """

    CONFIG_KWARGS = {"lifespan": "off"}
