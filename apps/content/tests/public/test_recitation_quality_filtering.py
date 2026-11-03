import json

from django.core.cache import cache as django_cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.cache import DEFAULT_QUALITY_CACHE_TOKEN, quality_cache_token, recitation_response_cache_key
from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationQuality,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.core.ninja_utils.paginations import DEFAULT_PAGE_SIZE
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class QualityCacheTokenTest(BaseTestCase):
    """
    ?quality= is user input that may be a quality name, so it must be sanitized before
    it lands in a cache key -- memcached rejects spaces outright and Django warns
    under every backend.
    """

    def test_quality_cache_token_where_quality_omitted_should_return_default_sentinel(self):
        # Arrange / Act / Assert
        self.assertEqual(DEFAULT_QUALITY_CACHE_TOKEN, quality_cache_token(None))

    def test_quality_cache_token_where_value_is_slug_shaped_should_pass_through(self):
        # Arrange / Act / Assert - keeps Redis keys readable in the common case
        self.assertEqual("with-echo", quality_cache_token("with-echo"))

    def test_quality_cache_token_where_value_has_spaces_should_be_key_safe(self):
        # Arrange / Act
        token = quality_cache_token("With echo")

        # Assert
        self.assertNotIn(" ", token)
        self.assertTrue(token.isalnum())

    def test_quality_cache_token_where_value_is_arabic_should_be_key_safe(self):
        # Arrange / Act
        token = quality_cache_token("مع صدى")

        # Assert - ASCII-only, so the key is valid under any cache backend
        self.assertTrue(token.isascii())
        self.assertNotIn(" ", token)

    def test_quality_cache_token_where_case_differs_should_produce_same_token(self):
        # Arrange / Act / Assert - name matching is case-insensitive, so these resolve
        # to the same quality and must not occupy two cache entries
        self.assertEqual(quality_cache_token("With echo"), quality_cache_token("WITH ECHO"))

    def test_quality_cache_token_where_values_differ_should_produce_different_tokens(self):
        # Arrange / Act / Assert
        self.assertNotEqual(quality_cache_token("With echo"), quality_cache_token("Without echo"))

    def test_quality_cache_token_where_value_is_very_long_should_stay_short(self):
        # Arrange / Act - memcached caps keys at 250 chars
        token = quality_cache_token("x" * 500)

        # Assert
        self.assertLessEqual(len(token), 32)


class PublicRecitationQualityFilteringTest(BaseTestCase):
    """
    Covers the public contract for qualities: omitting ?quality must behave exactly as it
    did before qualities existed, and naming one must serve that variant only.
    """

    def setUp(self):
        super().setUp()
        django_cache.clear()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.default_quality = self.asset.recitation_qualities.get(is_default=True)
        self.echo_quality = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Default quality: surahs 1 and 2. Echo quality: surah 1 only, different duration.
        for surah_number in (1, 2):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                quality=self.default_quality,
                surah_number=surah_number,
                duration_ms=1000,
                size_bytes=512,
                audio_file=SimpleUploadedFile(f"{surah_number:03}.mp3", b"dummy"),
            )
        self.echo_track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.echo_quality,
            surah_number=1,
            duration_ms=9999,
            size_bytes=4096,
            audio_file=SimpleUploadedFile("001-echo.mp3", b"dummy"),
        )

        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_list_tracks_where_quality_omitted_should_return_default_quality_tracks_only(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/")

        # Assert - pre-quality consumers must still see exactly one track per surah
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(2, len(items))
        self.assertEqual([1, 2], [i["surah_number"] for i in items])
        self.assertEqual(1000, items[0]["duration_ms"])

    def test_public_recitation_endpoints_where_old_folder_param_given_should_return_400(self):
        urls = {
            "tracks": f"/recitations/{self.asset.id}/?folder=with-echo",
            "ayah": f"/recitations/{self.asset.id}/ayah/1:1/?folder=with-echo",
            "range": f"/recitations/{self.asset.id}/1/range/?from=1&to=2&folder=with-echo",
        }
        for surface, url in urls.items():
            with self.subTest(surface=surface):
                # Arrange
                self.authenticate_client(self.app)

                # Act
                response = self.client.get(url)

                # Assert — refused rather than silently serving the default quality
                self.assertEqual(400, response.status_code, response.content)
                self.assertEqual("folder_param_renamed", response.json()["error_name"])

    def test_list_tracks_where_quality_given_should_return_only_that_quality_tracks(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(1, items[0]["surah_number"])
        self.assertEqual(9999, items[0]["duration_ms"])

    def test_list_tracks_where_quality_is_english_name_should_return_that_quality(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act - the name, not the slug
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=With echo")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(9999, items[0]["duration_ms"])

    def test_list_tracks_where_quality_name_differs_in_case_should_still_match(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=WITH ECHO")

        # Assert - name matching is case-insensitive
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(response.json()["results"]))

    def test_list_tracks_where_quality_is_arabic_name_should_return_that_quality(self):
        # Arrange
        arabic = RecitationQuality.objects.create(asset=self.asset, name="مع صدى", name_ar="مع صدى")
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=arabic,
            surah_number=3,
            duration_ms=4242,
            size_bytes=64,
            audio_file=SimpleUploadedFile("003-ar.mp3", b"dummy"),
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=مع صدى")

        # Assert - the localized name column is matched too
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(4242, items[0]["duration_ms"])

    def test_list_tracks_where_slug_and_name_collide_should_prefer_the_slug_match(self):
        # Arrange - a quality literally *named* "with-echo", colliding with the other
        # quality's slug. The slug is the canonical identifier and must win.
        named_like_a_slug = RecitationQuality.objects.create(asset=self.asset, name="with-echo", name_en="with-echo")
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=named_like_a_slug,
            surah_number=4,
            duration_ms=1234,
            size_bytes=64,
            audio_file=SimpleUploadedFile("004.mp3", b"dummy"),
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo")

        # Assert - resolves to the quality whose *slug* is with-echo, not the one named it
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(9999, items[0]["duration_ms"])

    def test_list_tracks_where_quality_unknown_should_return_404_quality_not_found(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=nope")

        # Assert - a typo must not silently look like an empty variant
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("quality_not_found", response.json()["error_name"])

    def test_list_tracks_where_quality_exists_but_empty_should_return_empty_200(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="Video", name_en="Video")
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/?quality=video")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json()["results"])

    def test_list_tracks_where_two_qualities_requested_should_not_share_cache_entries(self):
        # Arrange - this is the regression that would serve one variant's audio for another
        self.authenticate_client(self.app)

        # Act - warm both caches, then read them back
        default_body = self.client.get(f"/recitations/{self.asset.id}/").json()
        echo_body = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo").json()

        # Assert - distinct payloads
        self.assertNotEqual(default_body["results"], echo_body["results"])

        # ...backed by distinct cache entries
        default_key = recitation_response_cache_key(
            self.asset.id, page=1, page_size=DEFAULT_PAGE_SIZE, quality_slug=DEFAULT_QUALITY_CACHE_TOKEN
        )
        echo_key = recitation_response_cache_key(
            self.asset.id, page=1, page_size=DEFAULT_PAGE_SIZE, quality_slug="with-echo"
        )
        self.assertNotEqual(default_key, echo_key)

        cached_default = json.loads(django_cache.get(default_key))
        cached_echo = json.loads(django_cache.get(echo_key))
        self.assertEqual(2, cached_default["count"])
        self.assertEqual(1, cached_echo["count"])

    def test_list_tracks_where_served_from_cache_should_still_be_quality_specific(self):
        # Arrange - warm both, then re-request so both are cache hits
        self.authenticate_client(self.app)
        first_default = self.client.get(f"/recitations/{self.asset.id}/").json()
        first_echo = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo").json()

        # Act
        second_default = self.client.get(f"/recitations/{self.asset.id}/").json()
        second_echo = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo").json()

        # Assert - the cached responses must not have crossed over
        self.assertEqual(first_default, second_default)
        self.assertEqual(first_echo, second_echo)
        self.assertEqual(2, len(second_default["results"]))
        self.assertEqual(1, len(second_echo["results"]))

    def test_list_recitations_should_expose_qualities_default_first(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/recitations/")

        # Assert - this is how a consumer discovers valid ?quality= values
        self.assertEqual(200, response.status_code, response.content)
        recitation = next(r for r in response.json()["results"] if r["id"] == self.asset.id)
        self.assertEqual(
            [
                {"name": "Default", "slug": "default", "is_default": True},
                {"name": "With echo", "slug": "with-echo", "is_default": False},
            ],
            recitation["qualities"],
        )

    def test_list_recitations_where_many_recitations_should_not_query_qualities_per_row(self):
        # Arrange - extra recitations, each of which would trigger its own quality query
        for index in range(4):
            extra = baker.make(
                Asset,
                category=CategoryChoice.RECITATION,
                publisher=self.publisher,
                status=StatusChoice.READY,
                is_open_access=True,
                reciter=baker.make("content.Reciter", name=f"Reciter {index}"),
                riwayah=baker.make("content.Riwayah", name=f"Riwayah {index}"),
            )
            RecitationQuality.objects.create(asset=extra, name="With echo", name_en="With echo")
        self.authenticate_client(self.app)

        # Act
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/recitations/")

        # Assert - qualities come from ONE prefetch, not one query per recitation.
        # Asserting on the quality query specifically rather than a total, so the test
        # does not break when unrelated queries (auth, tracking) change.
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(5, len(response.json()["results"]))
        self.assertTrue(all(len(r["qualities"]) == 2 for r in response.json()["results"]))

        quality_queries = [q["sql"] for q in captured.captured_queries if "content_recitationquality" in q["sql"]]
        prefetch_queries = [sql for sql in quality_queries if 'FROM "content_recitationquality"' in sql]
        self.assertEqual(1, len(prefetch_queries), prefetch_queries)

    def test_list_tracks_where_timings_differ_per_quality_should_return_the_requested_variant(self):
        # Arrange - echo/delay variants genuinely have different offsets
        default_track = RecitationSurahTrack.objects.get(quality=self.default_quality, surah_number=1)
        RecitationAyahTiming.objects.create(track=default_track, ayah_key="1:1", start_ms=0, end_ms=500)
        RecitationAyahTiming.objects.create(track=self.echo_track, ayah_key="1:1", start_ms=250, end_ms=900)
        self.authenticate_client(self.app)

        # Act
        default_items = self.client.get(f"/recitations/{self.asset.id}/").json()["results"]
        echo_items = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo").json()["results"]

        # Assert
        self.assertEqual(0, default_items[0]["ayahs_timings"][0]["start_ms"])
        self.assertEqual(250, echo_items[0]["ayahs_timings"][0]["start_ms"])

    def test_list_recitations_should_omit_hidden_qualities(self):
        self.echo_quality.is_visible = False
        self.echo_quality.save(update_fields=["is_visible"])
        self.authenticate_client(self.app)

        response = self.client.get("/recitations/")

        self.assertEqual(200, response.status_code, response.content)
        recitation = next(r for r in response.json()["results"] if r["id"] == self.asset.id)
        self.assertEqual(
            [{"name": "Default", "slug": "default", "is_default": True}],
            recitation["qualities"],
        )

    def test_list_tracks_where_quality_hidden_should_return_404(self):
        self.echo_quality.is_visible = False
        self.echo_quality.save(update_fields=["is_visible"])
        self.authenticate_client(self.app)

        response = self.client.get(f"/recitations/{self.asset.id}/?quality=with-echo")

        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("quality_not_found", response.json()["error_name"])
