"""Reviewed categories (translations / tafsirs) in the package registry.

Consumers are served what the publisher published (``AssetLanguage.published_version``),
so the registry installs only the published version and older committed versions
that are fully approved: never a newer commit, never unreviewed content.
"""

from datetime import timedelta

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewStateChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.publishing import publish
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class ReviewedPackageTests(BaseTestCase):
    """A French translation rendition with a commit timeline 1.0 -> 1.1 -> 1.2."""

    def setUp(self):
        super().setUp()
        cache.clear()  # the public package API is throttled per client
        self.publisher = baker.make(Publisher, name="P")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            language="ar",
            slug="t1",
            name="T1",
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr", status=StatusChoice.READY)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah1 = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")
        self.reviewer = User.objects.create_user(email="rev@example.com", name="Rev")
        self._clock = timezone.now() - timedelta(days=10)

    def _commit(self, name: str, *, review: str | None = ReviewStateChoice.APPROVED) -> AssetVersion:
        """A committed version changing ayah 1, created after the previous one,
        whose change is reviewed with ``review`` (None leaves it unreviewed)."""
        self._clock += timedelta(hours=1)
        version = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.fr,
            name=name,
            state=VersionStateChoice.PUBLISHED,
            file_url=ContentFile(b"surah,ayah,text\n", name=f"{name}.csv"),
        )
        AssetVersion.objects.filter(pk=version.pk).update(created_at=self._clock)
        change = baker.make(
            AssetVersionChange, version=version, ayah=self.ayah1, change_type="modified", new_text=name, order=1
        )
        if review is not None:
            self._review(change, review)
        return version

    def _review(self, change: AssetVersionChange, state: str) -> None:
        AssetVersionChangeReview.objects.create(
            change=change,
            state=state,
            comment="fix" if state == ReviewStateChoice.COMMENTED else "",
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

    def _resolve(self, version: str):
        return self.client.get(f"/packages/resolve/t1/?version={version}&language=fr")

    def _catalog_languages(self) -> dict[str, str]:
        response = self.client.get("/packages/")
        self.assertEqual(200, response.status_code, response.content)
        assets = {item["slug"]: item for item in response.json()["results"]}
        if "t1" not in assets:
            return {}
        return {lang["language"]: lang["latest_version"] for lang in assets["t1"]["languages"]}

    def test_list_packages_where_newer_commit_is_unpublished_should_list_published_version(self):
        # Arrange
        self._commit("1.0")
        publish(self._commit("1.1"))
        self._commit("1.2")

        # Act
        languages = self._catalog_languages()

        # Assert
        self.assertEqual({"fr": "1.1.0"}, languages)

    def test_list_packages_where_no_language_is_published_should_not_list_asset(self):
        # Arrange
        self._commit("1.0")

        # Act
        languages = self._catalog_languages()

        # Assert
        self.assertEqual({}, languages)

    def test_resolve_package_single_where_newer_commit_is_unpublished_should_resolve_published_version(self):
        # Arrange
        self._commit("1.0")
        publish(self._commit("1.1"))
        self._commit("1.2")

        # Act
        response = self._resolve("^1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.1.0", response.json()["result"]["resolved_version"])

    def test_resolve_package_single_where_pinned_to_unpublished_newer_commit_should_return_404(self):
        # Arrange
        publish(self._commit("1.1"))
        self._commit("1.2")

        # Act
        response = self._resolve("1.2.0")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_resolve_package_single_where_pinned_to_older_approved_version_should_resolve_it(self):
        # Arrange
        self._commit("1.0")
        publish(self._commit("1.1"))

        # Act
        response = self._resolve("1.0.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.0.0", response.json()["result"]["resolved_version"])

    def test_resolve_package_single_where_older_version_is_not_approved_should_return_404(self):
        # Arrange
        self._commit("1.0", review=ReviewStateChoice.COMMENTED)
        publish(self._commit("1.1"))

        # Act
        response = self._resolve("1.0.0")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_resolve_package_single_where_publisher_rolled_back_should_resolve_rolled_back_version(self):
        # Arrange
        v1 = self._commit("1.0")
        publish(self._commit("1.1"))
        publish(v1)

        # Act
        response = self._resolve("^1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.0.0", response.json()["result"]["resolved_version"])

    def test_resolve_package_single_where_published_version_was_commented_later_should_still_resolve_it(self):
        # Arrange
        published = publish(self._commit("1.1"))
        AssetVersionChangeReview.objects.filter(change__version=published).update(
            state=ReviewStateChoice.COMMENTED, comment="fix"
        )

        # Act
        response = self._resolve("^1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.1.0", response.json()["result"]["resolved_version"])

    def test_resolve_package_single_where_language_has_no_published_version_should_return_422(self):
        # Arrange
        self._commit("1.0")

        # Act
        response = self._resolve("^1.0")

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("no_eligible_package_versions", response.json()["error_name"])

    def test_resolve_package_manifest_where_newer_commit_is_unpublished_should_resolve_published_version(self):
        # Arrange
        publish(self._commit("1.1"))
        self._commit("1.2")

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"t1-fr": {"asset": "t1", "language": "fr", "version": "^1.0"}}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["1.1.0"], [r["resolved_version"] for r in response.json()["results"]])

    def test_download_package_file_where_version_is_unpublished_newer_commit_should_return_404(self):
        # Arrange
        publish(self._commit("1.1"))
        unpublished = self._commit("1.2")

        # Act
        response = self.client.get(f"/packages/download/{unpublished.pk}/t1-fr-1.2.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_download_package_file_where_version_is_published_should_redirect_to_file(self):
        # Arrange
        published = publish(self._commit("1.1"))

        # Act
        response = self.client.get(f"/packages/download/{published.pk}/t1-fr-1.1.csv/")

        # Assert
        self.assertEqual(302, response.status_code, response.content)
