from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db.models.fields.files import FieldFile, FileField
from django.test import RequestFactory, override_settings

from apps.core.utils.media_urls import public_media_url

R2 = {
    "CLOUDFLARE_R2_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
    "CLOUDFLARE_R2_PUBLIC_BASE_URL": "https://storage.example.com/",
}


def _file(name: str) -> FieldFile:
    field = FileField(storage=FileSystemStorage(base_url="/media/"))
    file = FieldFile(None, field, name)
    file.file = ContentFile(b"")
    return file


class TestPublicMediaUrl:
    @override_settings(**R2)
    def test_public_media_url_where_r2_should_use_the_storage_custom_domain(self):
        # Act
        url = public_media_url(_file("uploads/assets/2/recitations/001.mp3"), RequestFactory().get("/"))

        # Assert
        assert url == "https://storage.example.com/media/uploads/assets/2/recitations/001.mp3"

    @override_settings(**R2)
    def test_public_media_url_where_name_is_not_ascii_should_percent_encode_it(self):
        # Act
        url = public_media_url(_file("uploads/assets/9/مصحف.pdf"), RequestFactory().get("/"))

        # Assert
        assert url == "https://storage.example.com/media/uploads/assets/9/%D9%85%D8%B5%D8%AD%D9%81.pdf"

    @override_settings(CLOUDFLARE_R2_ENDPOINT="", CLOUDFLARE_R2_PUBLIC_BASE_URL="")
    def test_public_media_url_where_no_r2_should_use_the_absolute_local_media_url(self):
        # Act
        url = public_media_url(_file("uploads/a.pdf"), RequestFactory().get("/"))

        # Assert
        assert url == "http://testserver/media/uploads/a.pdf"
