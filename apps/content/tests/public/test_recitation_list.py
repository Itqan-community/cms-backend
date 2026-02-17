from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")
        self.reciter1 = baker.make(Reciter, name="Reciter One")
        self.reciter2 = baker.make(Reciter, name="Reciter Two")
        self.riwayah1 = baker.make(Riwayah)
        self.riwayah2 = baker.make(Riwayah)

        self.ready_recitation_resource_pub1 = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.ready_recitation_resource2 = baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.draft_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        self.other_category_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )

        # Valid assets that should be returned
        self.asset1 = baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="First Recitation",
            description="Beautiful recitation",
        )
        self.asset2 = baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource2,
            reciter=self.reciter2,
            riwayah=self.riwayah2,
            name="Second Recitation",
            description="Calm recitation",
        )

        mp3_file = SimpleUploadedFile("a.mp3", b"fake-bytes")
        RecitationSurahTrack.objects.create(asset=self.asset1, surah_number=1, audio_file=mp3_file)
        mp3_file2 = SimpleUploadedFile("b.mp3", b"fake-bytes-2")
        RecitationSurahTrack.objects.create(asset=self.asset1, surah_number=2, audio_file=mp3_file2)
        mp3_file3 = SimpleUploadedFile("c.mp3", b"fake-bytes-3")
        RecitationSurahTrack.objects.create(asset=self.asset2, surah_number=1, audio_file=mp3_file3)

        # Assets that should NOT be returned
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=self.draft_recitation_resource,
            reciter=self.reciter1,
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=self.other_category_resource,
            reciter=self.reciter1,
            riwayah=baker.make("content.Riwayah", name="Test Riwayah2"),
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.ready_recitation_resource_pub1,
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_list_recitations_should_return_only_ready_recitation_assets(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get("/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        # Only two valid assets should be returned
        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.asset1.id, returned_ids)
        self.assertIn(self.asset2.id, returned_ids)

        # Check required fields and shapes
        for item in items:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("description", item)
            self.assertIn("publisher", item)
            self.assertIn("reciter", item)
            self.assertIn("riwayah", item)
            self.assertIn("surahs_count", item)
            self.assertIsInstance(item["publisher"], dict)
            self.assertIsInstance(item["reciter"], dict)
            self.assertIsInstance(item["riwayah"], dict)
            self.assertSetEqual(set(item["publisher"].keys()), {"id", "name"})
            self.assertSetEqual(set(item["reciter"].keys()), {"id", "name"})
            self.assertSetEqual(set(item["riwayah"].keys()), {"id", "name"})

        # Validate surahs_count by asset
        asset1_item = next(i for i in items if i["id"] == self.asset1.id)
        asset2_item = next(i for i in items if i["id"] == self.asset2.id)
        self.assertEqual(2, asset1_item["surahs_count"])
        self.assertEqual(1, asset2_item["surahs_count"])

    def test_list_recitations_filter_by_publisher(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get(f"/recitations/?publisher_id={self.publisher1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])
        self.assertEqual(self.publisher1.name, items[0]["publisher"]["name"])

    def test_list_recitations_filter_by_reciter(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get(f"/recitations/?reciter_id={self.reciter2.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.reciter2.id, items[0]["reciter"]["id"])
        self.assertEqual(self.reciter2.name, items[0]["reciter"]["name"])

    def test_list_recitations_filter_by_riwayah(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get(f"/recitations/?riwayah_id={self.riwayah1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.riwayah1.id, items[0]["riwayah"]["id"])
        self.assertEqual(self.riwayah1.name, items[0]["riwayah"]["name"])

    def test_list_recitations_search_should_match_name_description_publisher_or_reciter(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        # Search by part of description
        response = self.client.get("/recitations/?search=Beautiful")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

        # Assert
        # Search by reciter name
        response = self.client.get("/recitations/?search=Reciter Two")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_ordering_by_name(self):
        # Arrange
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get("/recitations/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_recitations_where_surahs_count_should_reflect_related_tracks(self):
        # Arrange done in setUp: asset1 has 2 tracks, asset2 has 1 track
        self.authenticate_client(application=self.app)

        # Act
        response = self.client.get("/recitations/")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Assert
        asset1_item = next(i for i in items if i["id"] == self.asset1.id)
        asset2_item = next(i for i in items if i["id"] == self.asset2.id)
        self.assertEqual(2, asset1_item["surahs_count"])
        self.assertEqual(1, asset2_item["surahs_count"])
