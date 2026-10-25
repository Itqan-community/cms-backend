from datetime import UTC, datetime
import json
import re

from apps.usage_tracking.models import TrafficKind, TrafficStatusClass
from apps.usage_tracking.services.logpush_parser import parse_line, parse_lines


def _line(**overrides) -> str:
    record = {
        "RayID": "8f0a1b2c3d4e5f60",
        "EdgeStartTimestamp": "2026-10-18T10:00:18Z",
        "ClientRequestHost": "storage.cms.itqan.dev",
        "ClientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
        "ClientRequestURI": "/media/uploads/assets/13/recitations/091.mp3",
        "EdgeResponseStatus": 206,
        "EdgeResponseBytes": 4096,
        "CacheCacheStatus": "dynamic",
        "ClientIP": "203.0.113.7",
        "ClientCountry": "sa",
        "ClientRequestUserAgent": "Dalvik/2.1.0 (Linux; U; Android 14)",
        "ClientRequestReferer": "",
        "RequestHeaders": {},
    }
    record.update(overrides)
    return json.dumps(record)


class TestParseLine:
    def test_parse_line_where_surah_audio_should_return_audio_request(self):
        # Act
        parsed = parse_line(_line())

        # Assert
        assert parsed is not None
        assert (parsed.kind, parsed.asset_id, parsed.surah) == (TrafficKind.AUDIO_SURAH, 13, 91)
        assert parsed.occurred_at == datetime(2026, 10, 18, 10, 0, 18, tzinfo=UTC)
        assert (parsed.country, parsed.status_class, parsed.bytes) == ("SA", TrafficStatusClass.PARTIAL, 4096)

    def test_parse_line_where_download_param_should_be_gallery_download(self):
        # Arrange
        uri = "/media/uploads/assets/13/versions/7/mushaf.zip?download=mushaf-v1.zip"

        # Act
        parsed = parse_line(_line(ClientRequestURI=uri))

        # Assert
        assert (parsed.kind, parsed.asset_version_id, parsed.path) == (
            TrafficKind.GALLERY_DOWNLOAD,
            7,
            "/media/uploads/assets/13/versions/7/mushaf.zip",
        )

    def test_parse_line_where_app_tag_and_headers_present_should_keep_them(self):
        # Arrange
        headers = {"x-client-name": "quran-companion", "x-client-version": "2.4.1", "x-external-user-id": "u-1"}

        # Act
        parsed = parse_line(
            _line(
                ClientRequestURI="/media/uploads/assets/13/recitations/091.mp3?c=quran-companion",
                RequestHeaders=headers,
            )
        )

        # Assert
        assert (parsed.app_slug_raw, parsed.client_name, parsed.client_version, parsed.external_user_id) == (
            "quran-companion",
            "quran-companion",
            "2.4.1",
            "u-1",
        )

    def test_parse_line_where_api_route_with_asset_should_return_api_call(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/recitations/13/2/range/?from=1", EdgeResponseStatus=200))

        # Assert
        assert (parsed.kind, parsed.asset_id, parsed.surah, parsed.endpoint) == (
            TrafficKind.API_CALL,
            13,
            2,
            "/recitations/{asset_id}/{surah_number}/range/",
        )

    def test_parse_line_where_resolve_manifest_should_match_literal_route(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/resolve/manifest/"))

        # Assert
        assert (parsed.endpoint, parsed.asset_slug) == ("/packages/resolve/manifest/", "")

    def test_parse_line_where_resolve_slug_should_keep_slug(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/resolve/hafs-mushaf/"))

        # Assert
        assert (parsed.endpoint, parsed.asset_slug) == ("/packages/resolve/{slug}/", "hafs-mushaf")

    def test_parse_line_where_package_download_should_keep_version(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/download/42/hafs-ar-1.0.0.csv/"))

        # Assert
        assert (parsed.kind, parsed.asset_version_id) == (TrafficKind.API_CALL, 42)

    def test_parse_line_where_oauth_or_portal_or_scanner_path_should_skip(self):
        # Act / Assert
        for uri in ("/token/", "/portal/usage/downloads/summary/", "/.env", "/cms-api/assets/1/"):
            assert parse_line(_line(ClientRequestURI=uri)) is None

    def test_parse_line_where_timestamp_is_unixnano_should_convert(self):
        # Act
        parsed = parse_line(_line(EdgeStartTimestamp=1760781618000000000))

        # Assert
        assert parsed.occurred_at == datetime(2025, 10, 18, 10, 0, 18, tzinfo=UTC)

    def test_parse_line_where_not_json_or_missing_ray_should_skip(self):
        # Act / Assert
        assert parse_line(b"{not json") is None
        assert parse_line(_line(RayID="")) is None

    def test_parse_line_where_install_header_present_should_keep_raw_install_id(self):
        # Act
        parsed = parse_line(_line(RequestHeaders={"x-itqan-install-id": "0b1c"}))

        # Assert
        assert parsed.install_id_raw == "0b1c"


class TestParseLines:
    def test_parse_lines_where_mixed_lines_should_count_skipped(self):
        # Act
        parsed, skipped = parse_lines([_line(), "garbage", _line(ClientRequestURI="/.env")])

        # Assert
        assert (len(parsed), skipped) == (1, 2)


class TestRouteCoverage:
    def test_parse_line_where_any_public_route_should_map_to_its_template(self):
        # Arrange
        from config.developers_api import developers_api

        templates = [p for p in developers_api.get_openapi_schema()["paths"] if p not in ("/token/", "/revoke/")]

        # Act / Assert
        for template in templates:
            path = re.sub(r"\{[^}]+\}", "7", template)
            parsed = parse_line(_line(ClientRequestURI=path))
            assert parsed is not None, template
            assert parsed.endpoint == template


class TestParseLineFilters:
    def test_parse_line_where_method_is_not_get_should_skip(self):
        # Act / Assert
        for method in ("OPTIONS", "HEAD", "POST"):
            assert parse_line(_line(ClientRequestMethod=method)) is None, method

    def test_parse_line_where_method_is_get_should_keep(self):
        # Act / Assert
        assert parse_line(_line(ClientRequestMethod="GET")) is not None

    def test_parse_line_where_fields_contain_nul_should_strip_it(self):
        # Act
        parsed = parse_line(
            _line(ClientRequestUserAgent="Dalvik\u0000/2", RequestHeaders={"x-client-name": "app\u0000"})
        )

        # Assert
        assert "\x00" not in parsed.user_agent + parsed.client_name


class TestAttributionParsing:
    def test_parse_line_where_api_response_names_app_should_use_it(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/recitations/13/", ResponseHeaders={"x-itqan-app": "my-app"}))

        # Assert
        assert parsed.app_slug_raw == "my-app"

    def test_parse_line_where_api_post_should_keep_but_file_post_should_skip(self):
        # Act / Assert
        assert parse_line(_line(ClientRequestURI="/packages/resolve/manifest/", ClientRequestMethod="POST")) is not None
        assert parse_line(_line(ClientRequestMethod="POST")) is None

    def test_parse_line_where_api_call_has_c_param_should_ignore_it(self):
        # Act
        spoofed = parse_line(_line(ClientRequestURI="/recitations/13/?c=other-app"))
        tagged = parse_line(
            _line(ClientRequestURI="/recitations/13/?c=other-app", ResponseHeaders={"x-itqan-app": "my-app"})
        )

        # Assert
        assert (spoofed.app_slug_raw, tagged.app_slug_raw) == ("", "my-app")
