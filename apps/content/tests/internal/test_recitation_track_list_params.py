from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class InternalRecitationTrackListParamsTest(BaseTestCase):
    def test_list_recitation_tracks_where_old_folder_param_given_should_return_400(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            is_open_access=True,
            reciter=baker.make("content.Reciter", name="Internal Reciter"),
            riwayah=baker.make("content.Riwayah", name="Internal Riwayah"),
        )
        self.authenticate_user(User.objects.create_user(email="internal-tracks@example.com", name="Dev"))

        # Act
        response = self.client.get(f"/cms-api/recitation-tracks/{asset.id}/?folder=with-echo")

        # Assert — `folder` was renamed to `quality`; old callers get an error, not the default
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("folder_param_renamed", response.json()["error_name"])
