import httpx

from apps.core.tests.base import BaseTestCase
from apps.core.wikipedia import WikiArticle, WikipediaClient


def _client(handler) -> WikipediaClient:
    return WikipediaClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))


AR_PAGE = {
    "title": "مشاري راشد العفاسي",
    "extract": "مشاري بن راشد العفاسي قارئ كويتي.",
    "fullurl": "https://ar.wikipedia.org/wiki/x",
    "langlinks": [{"lang": "en", "title": "Mishary Rashid Alafasy"}],
}
EN_PAGE = {
    "title": "Mishary Rashid Alafasy",
    "extract": "Mishary Rashid Alafasy is a Kuwaiti qari.",
    "fullurl": "https://en.wikipedia.org/wiki/Mishary_Rashid_Alafasy",
}


class WikipediaClientTests(BaseTestCase):
    def test_lookup_where_arabic_article_has_english_link_should_return_both(self):
        # Arrange
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if request.url.host == "ar.wikipedia.org":
                return httpx.Response(200, json={"query": {"pages": [AR_PAGE]}})
            return httpx.Response(200, json={"query": {"pages": [EN_PAGE]}})

        # Act
        articles = _client(handler).lookup("مشاري العفاسي")

        # Assert
        self.assertEqual(
            [
                WikiArticle(url="https://ar.wikipedia.org/wiki/x", extract="مشاري بن راشد العفاسي قارئ كويتي."),
                WikiArticle(
                    url="https://en.wikipedia.org/wiki/Mishary_Rashid_Alafasy",
                    extract="Mishary Rashid Alafasy is a Kuwaiti qari.",
                ),
            ],
            articles,
        )
        self.assertEqual("مشاري العفاسي", seen[0].url.params["gsrsearch"])
        self.assertEqual("Mishary Rashid Alafasy", seen[1].url.params["titles"])
        self.assertIn("ItqanCMS", seen[0].headers["user-agent"])

    def test_lookup_where_no_english_link_should_return_arabic_only(self):
        # Arrange
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={"query": {"pages": [{**AR_PAGE, "langlinks": []}]}})

        # Act
        articles = _client(handler).lookup("مشاري العفاسي")

        # Assert
        self.assertEqual(["https://ar.wikipedia.org/wiki/x"], [a.url for a in articles])
        self.assertEqual(1, len(calls))

    def test_lookup_where_nothing_found_should_return_empty(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"batchcomplete": True})

        # Act / Assert
        self.assertEqual([], _client(handler).lookup("لا شيء"))

    def test_lookup_where_http_fails_should_return_empty_without_raising(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("down", request=request)

        # Act / Assert
        self.assertEqual([], _client(handler).lookup("مشاري العفاسي"))

    def test_lookup_where_english_fetch_fails_should_keep_arabic(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "ar.wikipedia.org":
                return httpx.Response(200, json={"query": {"pages": [AR_PAGE]}})
            return httpx.Response(500, text="oops")

        # Act
        articles = _client(handler).lookup("مشاري العفاسي")

        # Assert
        self.assertEqual(["https://ar.wikipedia.org/wiki/x"], [a.url for a in articles])

    def test_lookup_where_extract_is_long_should_truncate(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            page = {**AR_PAGE, "extract": "x" * 10000, "langlinks": []}
            return httpx.Response(200, json={"query": {"pages": [page]}})

        # Act
        articles = _client(handler).lookup("q")

        # Assert
        self.assertLessEqual(len(articles[0].extract), 3000)

    def test_lookup_where_query_blank_should_not_call_http(self):
        # Arrange
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={})

        # Act / Assert
        self.assertEqual([], _client(handler).lookup("   "))
        self.assertEqual([], calls)
