from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str | None:
    """The visitor's IP. Caddy sets X-Forwarded-For from Cloudflare's CF-Connecting-IP."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
