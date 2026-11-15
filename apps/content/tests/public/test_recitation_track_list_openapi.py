from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, RecitationSurahTrack, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class RecitationTrackListOpenApiTest(BaseTestCase):
    def _track_list_200_schema(self) -> dict:
        spec = self.client.get("/openapi.json").json()
        content = spec["paths"]["/recitations/{asset_id}/"]["get"]["responses"]["200"]["content"]
        ref = content["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
        return spec["components"]["schemas"][ref]

    def test_openapi_where_recitation_tracks_documented_should_describe_a_results_and_count_page(self):
        # Arrange / Act
        schema = self._track_list_200_schema()

        # Assert
        self.assertEqual("object", schema["type"])
        self.assertEqual({"results", "count"}, set(schema["properties"]))
        self.assertEqual("array", schema["properties"]["results"]["type"])

    def test_list_recitation_tracks_where_called_should_return_the_documented_keys(self):
        # Arrange
        cache.clear()
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=baker.make(Publisher),
            status=StatusChoice.READY,
            is_open_access=True,
            in_public_api=True,
            reciter=baker.make("content.Reciter"),
            riwayah=baker.make("content.Riwayah"),
        )
        RecitationSurahTrack.objects.create(
            asset=asset,
            quality=asset.recitation_qualities.get(is_default=True),
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=SimpleUploadedFile("001.mp3", b"dummy"),
        )
        schema = self._track_list_200_schema()

        # Act
        response = self.client.get(f"/recitations/{asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(set(schema["properties"]), set(response.json()))
