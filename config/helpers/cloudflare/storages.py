from storages.backends.s3 import S3ManifestStaticStorage, S3Storage


class StaticFileStorage(S3ManifestStaticStorage):
    location = "static"
    default_acl = "public-read"
    querystring_auth = False


class MediaFileStorage(S3Storage):
    location = "media"
    default_acl = "public-read"
    querystring_auth = False
