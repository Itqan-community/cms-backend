"""Publishers mark any asset type as a draft from the portal: it stays listed and
editable there, while every consumer surface keeps hiding it (``Asset.status``)."""

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Qiraah, Reciter, Riwayah, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# Asset types created with a multipart form, with the extra fields their create needs.
FORM_TYPES = {
    "mushafs": (CategoryChoice.MUSHAF, "MUSHAF", {}),
    "fonts": (CategoryChoice.FONT, "FONT", {}),
    "tafsirs": (CategoryChoice.TAFSIR, "TAFSIR", {"template": "ayah"}),
    "translations": (CategoryChoice.TRANSLATION, "TRANSLATION", {"template": "ayah"}),
}

# The translation PATCH endpoint reads JSON; the others read a form.
JSON_PATCH_TYPES = frozenset({"translations"})


class AssetDraftStatusTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Draft Publisher")
        self.user = User.objects.create_user(email="drafts@example.com", name="Drafts", is_staff=True)

    def _grant(self, prefix: str, *actions: str) -> None:
        for action in actions:
            self.give_permission(self.user, PermissionChoice[f"PORTAL_{action}_{prefix}"])

    def _create_form_asset(self, kind: str, **fields: object):
        _category, _prefix, extra = FORM_TYPES[kind]
        return self.client.post(
            f"/portal/{kind}/",
            data={
                "name_ar": "مسودة",
                "name_en": "Draft",
                "description_ar": "وصف",
                "description_en": "Description",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                **extra,
                **fields,
            },
        )

    def test_create_asset_where_status_draft_should_store_draft_for_every_form_type(self):
        for kind, (category, prefix, _extra) in FORM_TYPES.items():
            with self.subTest(kind=kind):
                # Arrange
                self.authenticate_user(self.user)
                self._grant(prefix, "CREATE")

                # Act
                response = self._create_form_asset(kind, status="draft")

                # Assert
                self.assertEqual(201, response.status_code, response.content)
                self.assertEqual("draft", response.json()["status"])
                asset = Asset.objects.get(pk=response.json()["id"])
                self.assertEqual(category, asset.category)
                self.assertEqual(StatusChoice.DRAFT, asset.status)

    def test_create_asset_where_status_omitted_should_default_to_ready(self):
        # Arrange
        self.authenticate_user(self.user)
        self._grant("MUSHAF", "CREATE")

        # Act
        response = self._create_form_asset("mushafs")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(StatusChoice.READY, Asset.objects.get(pk=response.json()["id"]).status)

    def test_retrieve_and_patch_asset_where_draft_should_stay_reachable_in_portal(self):
        for kind, (category, prefix, _extra) in FORM_TYPES.items():
            with self.subTest(kind=kind):
                # Arrange
                self.authenticate_user(self.user)
                self._grant(prefix, "READ", "UPDATE")
                asset = baker.make(
                    Asset,
                    category=category,
                    publisher=self.publisher,
                    status=StatusChoice.DRAFT,
                    template="ayah" if kind in ("tafsirs", "translations") else None,
                    name=f"Draft {kind}",
                    license="CC-BY",
                )

                # Act
                listed = self.client.get(f"/portal/{kind}/")
                detail = self.client.get(f"/portal/{kind}/{asset.slug}/")
                patch_body = (
                    {"content_type": "application/json"} if kind in JSON_PATCH_TYPES else {"format": "multipart"}
                )
                patched = self.client.patch(f"/portal/{kind}/{asset.slug}/", data={"status": "ready"}, **patch_body)

                # Assert
                self.assertEqual(200, listed.status_code, listed.content)
                self.assertIn(asset.id, {row["id"] for row in listed.json()["results"]})
                self.assertEqual(200, detail.status_code, detail.content)
                self.assertEqual("draft", detail.json()["status"])
                self.assertEqual(200, patched.status_code, patched.content)
                asset.refresh_from_db()
                self.assertEqual(StatusChoice.READY, asset.status)

    def test_create_and_patch_recitation_where_status_draft_should_toggle_status(self):
        # Arrange
        self.authenticate_user(self.user)
        self._grant("RECITATION", "CREATE", "READ", "UPDATE")
        qiraah = baker.make(Qiraah, name="Q")
        payload = {
            "name_ar": "تلاوة",
            "name_en": "Recitation",
            "description_ar": "وصف",
            "description_en": "Description",
            "publisher_id": self.publisher.id,
            "reciter_id": baker.make(Reciter, name="R").id,
            "qiraah_id": qiraah.id,
            "riwayah_id": baker.make(Riwayah, name="W", qiraah=qiraah).id,
            "madd_level": "twassut",
            "meem_behaviour": "silah",
            "year": 2024,
            "license": "CC0",
            "status": "draft",
        }

        # Act
        created = self.client.post("/portal/recitations/", data=payload, content_type="application/json")
        slug = created.json()["slug"]
        listed = self.client.get("/portal/recitations/")
        patched = self.client.patch(
            f"/portal/recitations/{slug}/", data={"status": "ready"}, content_type="application/json"
        )

        # Assert
        self.assertEqual(201, created.status_code, created.content)
        self.assertEqual("draft", created.json()["status"])
        self.assertIn(created.json()["id"], {row["id"] for row in listed.json()["results"]})
        self.assertEqual(200, patched.status_code, patched.content)
        self.assertEqual(StatusChoice.READY, Asset.objects.get(slug=slug).status)

    def test_patch_asset_where_status_invalid_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self._grant("MUSHAF", "UPDATE")
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF, publisher=self.publisher, status=StatusChoice.READY)

        # Act
        response = self.client.patch(f"/portal/mushafs/{asset.slug}/", data={"status": "hidden"}, format="multipart")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])
        asset.refresh_from_db()
        self.assertEqual(StatusChoice.READY, asset.status)
