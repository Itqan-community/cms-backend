"""Read-only Wikipedia lookup used as the free "web" source for portal AI translation.

Searches Arabic Wikipedia, then follows the article's English language link.
Every failure is logged and treated as "nothing found": callers fall back to a
plain translation, so this never raises.
"""

from dataclasses import dataclass
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://{lang}.wikipedia.org/w/api.php"
# Wikimedia asks API clients to identify themselves.
USER_AGENT = "ItqanCMS/1.0 (https://cms.itqan.dev; admin metadata helper)"
TIMEOUT_SECONDS = 8.0
MAX_EXTRACT_LENGTH = 3000
PAGE_PROPS = {
    "action": "query",
    "format": "json",
    "formatversion": "2",
    "prop": "extracts|info",
    "exintro": "1",
    "explaintext": "1",
    "inprop": "url",
    "redirects": "1",
}


@dataclass(frozen=True)
class WikiArticle:
    url: str
    extract: str


class WikipediaClient:
    """Args:
    http_client: Optional ``httpx.Client``. Tests inject
        ``httpx.Client(transport=httpx.MockTransport(...))``.
    """

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client

    def lookup(self, query: str) -> list[WikiArticle]:
        """Best Arabic article for ``query`` plus its English counterpart, when they exist."""
        query = query.strip()
        if not query:
            return []
        page = self._first_page(
            "ar",
            {
                **PAGE_PROPS,
                "prop": "extracts|info|langlinks",
                "lllang": "en",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": "1",
            },
        )
        if page is None:
            return []
        articles = [article] if (article := self._article(page)) else []
        english_title = next(
            (
                link.get("title")
                for link in page.get("langlinks") or []
                if isinstance(link, dict) and link.get("lang") == "en"
            ),
            None,
        )
        if english_title:
            english_page = self._first_page("en", {**PAGE_PROPS, "titles": str(english_title)})
            if english_page is not None and (english := self._article(english_page)):
                articles.append(english)
        return articles

    def _first_page(self, lang: str, params: dict[str, str]) -> dict[str, Any] | None:
        url = API_URL.format(lang=lang)
        headers = {"User-Agent": USER_AGENT}
        try:
            if self._http_client is not None:
                response = self._http_client.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
            else:
                with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                    response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages")
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            logger.warning("wikipedia: lookup failed [lang=%s, error=%s]", lang, type(exc).__name__)
            return None
        if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict) or pages[0].get("missing"):
            return None
        return pages[0]

    @staticmethod
    def _article(page: dict[str, Any]) -> WikiArticle | None:
        extract = str(page.get("extract") or "").strip()
        url = str(page.get("fullurl") or "")
        if not extract or not url:
            return None
        return WikiArticle(url=url, extract=extract[:MAX_EXTRACT_LENGTH])
