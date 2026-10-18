import gzip
import io

from botocore.response import StreamingBody
from botocore.stub import Stubber

from apps.usage_tracking.services.r2_logs_client import R2LogsClient


def _client() -> R2LogsClient:
    return R2LogsClient("https://example.r2.cloudflarestorage.com", "id", "secret", "itqan-usage-logs")


class TestR2LogsClient:
    def test_list_day_prefixes_where_pages_returned_should_collect_sorted_prefixes(self):
        # Arrange
        client = _client()
        stubber = Stubber(client._s3)
        stubber.add_response(
            "list_objects_v2",
            {
                "CommonPrefixes": [{"Prefix": "http/production/20261018/"}],
                "IsTruncated": True,
                "NextContinuationToken": "t",
            },
            {"Bucket": "itqan-usage-logs", "Prefix": "http/production/", "Delimiter": "/"},
        )
        stubber.add_response(
            "list_objects_v2",
            {"CommonPrefixes": [{"Prefix": "http/production/20261017/"}], "IsTruncated": False},
            {"Bucket": "itqan-usage-logs", "Prefix": "http/production/", "Delimiter": "/", "ContinuationToken": "t"},
        )

        # Act
        with stubber:
            prefixes = client.list_day_prefixes("http/production/")

        # Assert
        assert prefixes == ["http/production/20261017/", "http/production/20261018/"]

    def test_iter_lines_where_gzip_object_should_yield_non_empty_lines(self):
        # Arrange
        client = _client()
        payload = gzip.compress(b'{"a":1}\n\n{"b":2}\n')
        stubber = Stubber(client._s3)
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(payload), len(payload))},
            {"Bucket": "itqan-usage-logs", "Key": "k.log.gz"},
        )

        # Act
        with stubber:
            lines = list(client.iter_lines("k.log.gz"))

        # Assert
        assert lines == [b'{"a":1}\n', b'{"b":2}\n']
