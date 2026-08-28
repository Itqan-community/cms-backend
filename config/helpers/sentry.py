import re
from typing import Any

from decouple import config

# Reciter endpoints are high-volume public reads that add nothing to performance
# monitoring, so their transactions are dropped before they consume the tracing
# quota. Matches every API surface: /reciters/, /cms-api/reciters/,
# /tenant/reciters/, /portal/reciters/<id>/ ... Errors are unaffected.
TRACING_IGNORED_PATHS = re.compile(r"(?:^|/)reciters/")


def _sampled_request_path(sampling_context: dict[str, Any]) -> str:
    """Best-effort URL path of the transaction being sampled.

    Returns an empty string for non-HTTP transactions (Celery tasks, cron monitors).
    """
    wsgi_environ = sampling_context.get("wsgi_environ")
    if wsgi_environ:
        return wsgi_environ.get("PATH_INFO", "")

    asgi_scope = sampling_context.get("asgi_scope")
    if asgi_scope:
        return asgi_scope.get("path", "")

    # Fallback: at sampling time the Django integration has not resolved the route
    # yet, but other integrations may already name the transaction after the path.
    name = (sampling_context.get("transaction_context") or {}).get("name") or ""
    return name if name.startswith("/") else ""


def traces_sampler(sampling_context: dict[str, Any]) -> float:
    """Sample rate per transaction. Ignored paths are never traced or profiled."""
    if TRACING_IGNORED_PATHS.search(_sampled_request_path(sampling_context)):
        return 0.0
    return config("SENTRY_TRACES_SAMPLE_RATE", cast=float, default=1)


def enable_sentry() -> None:
    from sentry_sdk import init
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    init(
        server_name=config("DEFAULT_SERVER_NAME", default=""),
        dsn=config("SENTRY_DSN"),
        integrations=[
            DjangoIntegration(transaction_style="url", middleware_spans=True),
            CeleryIntegration(propagate_traces=True, monitor_beat_tasks=True),
            RedisIntegration(),
        ],
        enable_logs=True,
        # Sampling configuration
        sample_rate=config("SENTRY_ERRORS_SAMPLE_RATE", cast=float, default=1),
        # traces_sampler takes precedence over traces_sample_rate; it reads the same
        # setting and returns 0 for the paths we do not want traced.
        traces_sampler=traces_sampler,
        # Additional settings
        debug=config("SENTRY_DEBUG_BOOL", cast=bool, default=False),
        send_default_pii=config("SENTRY_PII_BOOL", cast=bool, default=True),
        environment=config("ENV_NAME", default="production"),
        # Performance monitoring
        enable_tracing=True,
        profiles_sample_rate=config("SENTRY_PROFILES_SAMPLE_RATE", cast=float, default=1),
        # Additional configuration
        max_breadcrumbs=config("SENTRY_MAX_BREADCRUMBS", cast=int, default=50),
        attach_stacktrace=True,
        before_send=lambda event, hint: event,  # Hook for custom event filtering
    )
