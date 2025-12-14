from decouple import config


def enable_sentry():
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
        # Sampling configuration
        sample_rate=config("SENTRY_ERRORS_SAMPLE_RATE", cast=float, default=1),
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", cast=float, default=1),
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
