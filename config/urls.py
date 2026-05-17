from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from django.views.generic import TemplateView
from oauth2_provider import urls as oauth2_urls

from config.cms_api import cms_api, cms_auth_api
from config.developers_api import developers_api
from config.portal_api import portal_api
from config.tenant_api import tenant_api


def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "Itqan CMS API",
            "timestamp": str(timezone.now()),
        }
    )


urlpatterns = [
    path("health/", health_check, name="health_check"),
    # Django Admin
    path("django-admin/", admin.site.urls),
    # Django Allauth URLs
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("o/", include(oauth2_urls)),
    # Internal API mount
    path("cms-api/", cms_api.urls),
    # Tenant API mount
    path("tenant/", tenant_api.urls),
    # Portal API mount
    path("portal/", portal_api.urls),
    # Public developers API mount
    path("", developers_api.urls),
]
if settings.ENABLE_ALLAUTH:
    urlpatterns += [
        path("cms-api/auth/", include("allauth.headless.urls")),
        path("cms-api/auth/", cms_auth_api.urls),  # just to show documentation
    ]

if settings.SAML_IDP_ENABLED:
    import base64
    import zlib

    from django.contrib.admin.views.decorators import staff_member_required
    from django.http import HttpResponse

    @staff_member_required
    def saml_debug(request):
        """Temporary: decode SAMLRequest param to reveal the Issuer entity ID."""
        raw = request.GET.get("SAMLRequest", "") or request.session.get("SAMLRequest", "")
        if not raw:
            return HttpResponse("Pass ?SAMLRequest=... or trigger the SSO flow first", content_type="text/plain")
        try:
            decoded = base64.b64decode(raw)
            try:
                xml = zlib.decompress(decoded, -15).decode("utf-8")
            except Exception:
                xml = decoded.decode("utf-8")
        except Exception as e:
            xml = f"Error decoding: {e}"
        return HttpResponse(xml, content_type="text/xml")

    urlpatterns += [
        path("idp/debug/saml-request/", saml_debug),
        path("idp/", include("djangosaml2idp.urls")),
    ]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Django Debug Toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
