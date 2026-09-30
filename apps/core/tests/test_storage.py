from unittest.mock import MagicMock, patch

from django.test import RequestFactory, override_settings

from apps.core.mixins import storage
from apps.core.mixins.storage import _get_s3_client, absolute_file_url, generate_presigned_download_url
from apps.core.tests.base import BaseTestCase


@override_settings(CLOUDFLARE_R2_BUCKET="bucket")
class GeneratePresignedDownloadUrlTests(BaseTestCase):
    def _content_disposition(self, filename: str) -> str:
        client = MagicMock()
        client.generate_presigned_url.return_value = "https://signed"
        with patch.object(storage, _get_s3_client.__name__, return_value=client):
            generate_presigned_download_url(key="media/x.csv", filename=filename)
        return client.generate_presigned_url.call_args.kwargs["Params"]["ResponseContentDisposition"]

    def test_generate_presigned_download_url_where_ascii_name_should_set_plain_filename(self):
        # Arrange / Act
        header = self._content_disposition("Hassaan_Tafsir-ar-v1.csv")

        # Assert
        self.assertEqual(header, 'attachment; filename="Hassaan_Tafsir-ar-v1.csv"')

    def test_generate_presigned_download_url_where_arabic_name_should_encode_it_per_rfc_5987(self):
        # Arrange / Act
        header = self._content_disposition("Tafsir-ar-مسودة_2.csv")

        # Assert
        self.assertEqual(header, "attachment; filename*=utf-8''Tafsir-ar-%D9%85%D8%B3%D9%88%D8%AF%D8%A9_2.csv")


class AbsoluteFileUrlTests(BaseTestCase):
    def _request(self):
        return RequestFactory().get("/portal/anything/")

    def test_absolute_file_url_where_storage_returns_relative_path_should_prefix_the_request_origin(self):
        # Arrange
        file = MagicMock(url="/media/uploads/v1.csv")
        file.__bool__.return_value = True

        # Act
        url = absolute_file_url(self._request(), file)

        # Assert
        self.assertEqual(url, "http://testserver/media/uploads/v1.csv")

    def test_absolute_file_url_where_storage_returns_absolute_url_should_keep_it(self):
        # Arrange
        file = MagicMock(url="https://cdn.example.com/uploads/v1.csv?sig=1")
        file.__bool__.return_value = True

        # Act
        url = absolute_file_url(self._request(), file)

        # Assert
        self.assertEqual(url, "https://cdn.example.com/uploads/v1.csv?sig=1")

    def test_absolute_file_url_where_no_file_should_return_none(self):
        # Arrange
        file = MagicMock()
        file.__bool__.return_value = False

        # Act
        url = absolute_file_url(self._request(), file)

        # Assert
        self.assertIsNone(url)
