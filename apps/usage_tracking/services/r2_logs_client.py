"""Reads Cloudflare Logpush files from the R2 logs bucket (S3 API, read-only key)."""

from collections.abc import Iterator
import gzip

import boto3


class R2LogsClient:
    def __init__(self, endpoint_url: str, access_key_id: str, secret_access_key: str, bucket: str) -> None:
        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def _pages(self, **kwargs) -> Iterator[dict]:
        token = None
        while True:
            params = {"Bucket": self._bucket, **kwargs}
            if token:
                params["ContinuationToken"] = token
            page = self._s3.list_objects_v2(**params)
            yield page
            if not page.get("IsTruncated"):
                return
            token = page["NextContinuationToken"]

    def list_day_prefixes(self, prefix: str) -> list[str]:
        """The `<prefix><YYYYMMDD>/` folders Logpush created, oldest first."""
        prefixes = [
            entry["Prefix"]
            for page in self._pages(Prefix=prefix, Delimiter="/")
            for entry in page.get("CommonPrefixes", [])
        ]
        return sorted(prefixes)

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(entry["Key"] for page in self._pages(Prefix=prefix) for entry in page.get("Contents", []))

    def iter_lines(self, key: str) -> Iterator[bytes]:
        body = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"]
        stream = gzip.GzipFile(fileobj=body) if key.endswith(".gz") else body
        try:
            for line in stream:
                if line.strip():
                    yield line
        finally:
            body.close()
