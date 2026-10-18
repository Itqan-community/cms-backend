from django.conf import settings
from django.core.checks import Warning as CheckWarning


def check_usage_identity_key(app_configs=None, **kwargs) -> list[CheckWarning]:
    if settings.USAGE_IDENTITY_KEY or not settings.ENABLE_USAGE_LOGPUSH_IMPORT:
        return []
    return [
        CheckWarning(
            "USAGE_IDENTITY_KEY is not set; unique-listener ids derive from SECRET_KEY, "
            "so rotating SECRET_KEY resets all unique counts.",
            id="usage_tracking.W001",
        )
    ]
