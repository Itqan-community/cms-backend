# apps/usage/middleware.py
import time

from django.utils.deprecation import MiddlewareMixin

from apps.content.tasks import create_usage_event_task


def _get_client_ip(request):
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _bounded_dict(d: dict, max_chars: int = 2000):
    s = str(d)
    return s[:max_chars]


class PublicApiUsageLoggingMiddleware(MiddlewareMixin):

    PUBLIC_PREFIXES = ("/api/cms-api/", "/content-api/")
    EXCLUDE_PREFIXES = ("/api/public/health", "/api/public/metrics")

    def process_request(self, request):
        path = request.path
        is_public = path.startswith(self.PUBLIC_PREFIXES) and not path.startswith(self.EXCLUDE_PREFIXES)
        request._usage_log_is_public = is_public
        if is_public:
            request._usage_log_start = time.monotonic()

    def process_response(self, request, response):
        if not getattr(request, "_usage_log_is_public", False):
            return response

        start = getattr(request, "_usage_log_start", None)
        duration_ms = int((time.monotonic() - start) * 1000) if start else None

        event_data = {
            "developer_user_id": None,
            "usage_kind": "api_access",
            "subject_kind": "public_api",
            "asset_id": None,
            "resource_id": None,
            "ip_address": _get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "effective_license": "free",
            "metadata": {
                "path": request.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "query_params": _bounded_dict(dict(request.GET)),
            },
        }

        create_usage_event_task.delay(event_data)
        return response
