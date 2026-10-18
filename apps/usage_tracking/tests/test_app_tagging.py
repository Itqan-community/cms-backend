from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, override_settings

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.middlewares.app_tagging import AppTaggingMiddleware, tag_storage_urls
from apps.users.models import APIKey, User

BASE = "https://storage.example.com"


class TestTagStorageUrls:
    def test_tag_storage_urls_where_storage_media_url_should_append_slug(self):
        # Arrange
        body = b'{"audio_url":"https://storage.example.com/media/uploads/assets/1/recitations/001.mp3"}'

        # Act
        result = tag_storage_urls(body, BASE, "my-app")

        # Assert
        assert (
            result == b'{"audio_url":"https://storage.example.com/media/uploads/assets/1/recitations/001.mp3?c=my-app"}'
        )

    def test_tag_storage_urls_where_query_present_or_other_host_should_leave_alone(self):
        # Arrange
        body = (
            b'{"a":"https://storage.example.com/media/x.mp3?v=2",'
            b'"b":"https://other.example.com/media/x.mp3","c":"https://storage.example.com/static/x.css"}'
        )

        # Act / Assert
        assert tag_storage_urls(body, BASE, "my-app") == body


@override_settings(CLOUDFLARE_R2_PUBLIC_BASE_URL=BASE)
class TestAppTaggingMiddleware(BaseTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.create_user(email="dev2@example.com", name="Dev")
        self.api_key, _ = APIKey.objects.create_key(name="My App", user=user)

    def _run(self, response: HttpResponse, auth=None) -> HttpResponse:
        request = RequestFactory().get("/recitations/1/")

        def view(req):
            req.auth = auth
            return response

        return AppTaggingMiddleware(view)(request)

    def test_middleware_where_api_key_auth_should_tag_body_set_header_and_private(self):
        # Arrange
        response = JsonResponse({"audio_url": f"{BASE}/media/a.mp3"})
        response["Cache-Control"] = "public, max-age=300, s-maxage=300"

        # Act
        result = self._run(response, auth=self.api_key)

        # Assert
        assert b"a.mp3?c=my-app" in result.content
        assert result["X-Itqan-App"] == "my-app"
        assert result["Cache-Control"] == "private, max-age=300"

    def test_middleware_where_anonymous_should_change_nothing(self):
        # Arrange
        response = JsonResponse({"audio_url": f"{BASE}/media/a.mp3"})
        response["Cache-Control"] = "public, max-age=300, s-maxage=300"

        # Act
        result = self._run(response, auth=None)

        # Assert
        assert b"?c=" not in result.content
        assert "X-Itqan-App" not in result
        assert result["Cache-Control"] == "public, max-age=300, s-maxage=300"
