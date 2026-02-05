from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")
        self.domain1 = baker.make(
            "publishers.Domain",
            domain="publisher1.com",
            publisher=self.publisher1,
            is_primary=True,
        )
        self.domain2 = baker.make(
            "publishers.Domain",
            domain="publisher2.com",
            publisher=self.publisher2,
            is_primary=True,
        )
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
            publisher=self.publisher1,
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
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="First Recitation",
            description="Beautiful recitation",
        )
        self.asset2 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
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
            category=Asset.CategoryChoice.RECITATION,
            resource=self.draft_recitation_resource,
            reciter=self.reciter1,
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.other_category_resource,
            reciter=self.reciter1,
            riwayah=baker.make("content.Riwayah", name="Test Riwayah2"),
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
            resource=self.ready_recitation_resource_pub1,
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")

    def test_list_recitations_should_return_only_ready_recitation_assets(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)
        # Act
        response = self.client.get("/tenant/recitations/")

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
            self.assertIn("reciter", item)
            self.assertIn("riwayah", item)
            self.assertIsInstance(item["reciter"], dict)
            self.assertIsInstance(item["riwayah"], dict)
            self.assertSetEqual(set(item["reciter"].keys()), {"id", "name"})
            self.assertSetEqual(set(item["riwayah"].keys()), {"id", "name"})

    def test_list_recitations_filter_by_reciter(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Act
        response = self.client.get(f"/tenant/recitations/?reciter_id={self.reciter2.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.reciter2.id, items[0]["reciter"]["id"])
        self.assertEqual(self.reciter2.name, items[0]["reciter"]["name"])

    def test_list_recitations_filter_by_riwayah(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Act
        response = self.client.get(f"/tenant/recitations/?riwayah_id={self.riwayah1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.riwayah1.id, items[0]["riwayah"]["id"])
        self.assertEqual(self.riwayah1.name, items[0]["riwayah"]["name"])

    def test_list_recitations_search_should_match_name_description_publisher_or_reciter(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Act
        # Search by part of description
        response = self.client.get("/tenant/recitations/?search=Beautiful")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

        # Assert
        # Search by reciter name
        response = self.client.get("/tenant/recitations/?search=Reciter Two")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_ordering_by_name(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Act
        response = self.client.get("/tenant/recitations/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_recitations_filter_by_madd_level(self):
        """Test filtering recitations by madd_level"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Create one asset with TWASSUT and one with QASR
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="Twassut Recitation",
            description="Twassut",
            madd_level=Asset.MaddLevelChoice.TWASSUT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="Qasr Recitation",
            description="Qasr",
            madd_level=Asset.MaddLevelChoice.QASR,
        )

        # Act - filter by madd_level=twassut
        response = self.client.get(f"/tenant/recitations/?madd_level={Asset.MaddLevelChoice.TWASSUT}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = {item["name"] for item in items}
        self.assertIn("Twassut Recitation", names)
        self.assertNotIn("Qasr Recitation", names)

    def test_list_recitations_filter_by_meem_behaviour(self):
        """Test filtering recitations by meem_behaviour"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain1)

        # Create one asset with SILAH and one with SKOUN
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="Silah Recitation",
            description="Silah",
            meem_behaviour=Asset.MeemBehaviorChoice.SILAH,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="Skoun Recitation",
            description="Skoun",
            meem_behaviour=Asset.MeemBehaviorChoice.SKOUN,
        )

        # Act - filter by meem_behaviour=silah
        response = self.client.get(f"/tenant/recitations/?meem_behaviour={Asset.MeemBehaviorChoice.SILAH}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = {item["name"] for item in items}
        self.assertIn("Silah Recitation", names)
        self.assertNotIn("Skoun Recitation", names)
