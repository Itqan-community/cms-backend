from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from storages.backends.s3 import S3Storage


class StaticFileStorage(ManifestStaticFilesStorage):
    location = "static"
    default_acl = "public-read"


class MediaFileStorage(S3Storage):
    location = "media"
    default_acl = "public-read"
