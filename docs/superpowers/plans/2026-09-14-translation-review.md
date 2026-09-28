# Translation Review Phase — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let permission-gated reviewers approve, comment ("needs changes"), or leave unreviewed each per-commit translation change, for languages assigned to them, without being able to edit content — storing who reviewed for auditing.

**Architecture:** Reviews attach one-to-one to `AssetVersionChange` rows (the per-commit delta). Each change has a single shared state (`unreviewed` = no row; `approved`/`commented` stored). Reviewer↔language assignment is per-language-global (`ReviewerLanguage`, Django-admin managed). One permission `PORTAL_REVIEW_CONTENT` gates the surface. A consolidated per-`(asset, language)` review grid lives on the asset detail page. Audit-only — no publish/availability gating.

**Tech Stack:** Django + django-ninja portal API (Service→Repository), `@paginate` with `NinjaPagination` (`results`/`count`), `ItqanError`/`NinjaErrorResponse`, model_bakery + `BaseTestCase` tests, pytest. Angular 20 standalone + signals, ng-zorro, ngx-translate (en/ar).

**Spec:** `docs/superpowers/specs/2026-09-14-translation-review-design.md`

## Global Constraints

- Audit-only: MUST NOT gate publishing or the availability toggle.
- Tenant-scoped: every asset lookup uses `request.publisher_q()`.
- Reviewers MUST have no content-edit path through this surface; review API writes only review state/comment. `PORTAL_REVIEW_CONTENT` is independent of `PORTAL_UPDATE_*`.
- A reviewer may act on a change only if its language ∈ their `ReviewerLanguage` set.
- `commented` requires a non-empty comment.
- Tests: AAA comments; named `test_<fn>_where_<criteria>_should_<result>`; assert `error_name` on 4xx; use `BaseTestCase` (never raw `django.test.TestCase`); run with `pytest` (use `.venv`).
- Localize every user-facing string with `gettext`/`gettext_lazy`; add Arabic to `locale/ar/LC_MESSAGES/django.po`; before "ready", pass the localization check (`msgfmt --check --statistics …` → 0 untranslated) and `compilemessages`.
- Frontend: i18n en+ar parity (`node scripts/check-arabic-translations.js`), `tsc --noEmit`, `eslint`, `prettier`, and `ng build --configuration staging` all clean.
- Category path segments: `translations` → `CategoryChoice.TRANSLATION`, `tafsirs` → `CategoryChoice.TAFSIR`. Review applies to these two only.

---

## Task 1: Review permission

**Files:**
- Modify: `apps/core/permissions.py`
- Test: `apps/content/tests/portal/test_asset_review.py` (created in Task 4; permission wiring is exercised there)

**Interfaces:**
- Produces: `PermissionChoice.PORTAL_REVIEW_CONTENT` (value `"portal_review_content"`).

- [ ] **Step 1: Add the permission choice**

In `apps/core/permissions.py`, inside `class PermissionChoice`, after the access-requests block, add:
```python
    # Content review
    PORTAL_REVIEW_CONTENT = "portal_review_content", _("Portal - Review Content")
```
Do NOT add any entry to the implied-permissions map (review is independent of read/update).

- [ ] **Step 2: Verify it imports**

Run: `.venv/bin/python manage.py check`
Expected: no errors.

- [ ] **Step 3: Commit**
```bash
git add apps/core/permissions.py
git commit -m "feat(content): add PORTAL_REVIEW_CONTENT permission"
```

---

## Task 2: Models, migration, Django admin

**Files:**
- Modify: `apps/content/models.py`
- Modify: `apps/content/admin.py`
- Create: `apps/content/migrations/00XX_review_models.py` (via makemigrations)
- Test: `apps/content/tests/models/test_review_models.py`

**Interfaces:**
- Produces:
  - `ReviewStateChoice` (TextChoices: `APPROVED="approved"`, `COMMENTED="commented"`).
  - `ReviewerLanguage(user, language)` — unique `(user, language)`, `related_name="reviewer_languages"`.
  - `AssetVersionChangeReview(change OneToOne→AssetVersionChange related_name="review", state, comment, reviewed_by, reviewed_at)`.

- [ ] **Step 1: Write failing model tests**

Create `apps/content/tests/models/test_review_models.py`:
```python
from django.db import IntegrityError
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewerLanguage,
    ReviewStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class ReviewerLanguageModelTest(BaseTestCase):
    def test_unique_reviewer_language(self):
        # Arrange
        user = User.objects.create_user(email="r@example.com", name="R")
        ReviewerLanguage.objects.create(user=user, language="fr")
        # Act / Assert
        with self.assertRaises(IntegrityError):
            ReviewerLanguage.objects.create(user=user, language="fr")


class AssetVersionChangeReviewModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")
        self.version = baker.make(AssetVersion, asset=self.asset)
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="x", order=1
        )
        self.user = User.objects.create_user(email="r@example.com", name="R")

    def test_one_review_per_change(self):
        # Arrange
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )
        # Act / Assert — OneToOne rejects a second row for the same change
        with self.assertRaises(IntegrityError):
            AssetVersionChangeReview.objects.create(
                change=self.change, state=ReviewStateChoice.COMMENTED, reviewed_by=self.user, reviewed_at=timezone.now()
            )

    def test_review_related_name(self):
        # Arrange
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )
        # Act / Assert
        self.assertEqual(ReviewStateChoice.APPROVED, self.change.review.state)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest apps/content/tests/models/test_review_models.py -q`
Expected: FAIL (ImportError: cannot import `ReviewerLanguage` / `AssetVersionChangeReview` / `ReviewStateChoice`).

- [ ] **Step 3: Add the models**

In `apps/content/models.py`, after `class AssetVersionChange` (ends ~line 525), add:
```python
class ReviewStateChoice(models.TextChoices):
    APPROVED = "approved", _("Approved")
    COMMENTED = "commented", _("Commented")


class ReviewerLanguage(BaseModel):
    """A language a reviewer is assigned to review (globally, across all assets).

    A user with PORTAL_REVIEW_CONTENT but no ReviewerLanguage rows can review
    nothing. Managed via Django admin.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviewer_languages")
    language = models.CharField(max_length=10, help_text="Language code the user may review, e.g. 'fr'")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "language"], name="unique_reviewer_language"),
        ]

    def __str__(self):
        return f"ReviewerLanguage(user_id={self.user_id}, language={self.language})"


class AssetVersionChangeReview(BaseModel):
    """A reviewer's outcome for a single AssetVersionChange (audit-only).

    Absence of a row means the change is unreviewed. ``reviewed_by`` /
    ``reviewed_at`` record who set the current state, for auditing.
    """

    change = models.OneToOneField(AssetVersionChange, on_delete=models.CASCADE, related_name="review")
    state = models.CharField(max_length=20, choices=ReviewStateChoice)
    comment = models.TextField(blank=True, help_text="Reviewer comment; required when state is commented")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    reviewed_at = models.DateTimeField()

    def __str__(self):
        return f"AssetVersionChangeReview(change_id={self.change_id}, state={self.state})"
```

- [ ] **Step 4: Register ReviewerLanguage in Django admin**

In `apps/content/admin.py`, add an import for `ReviewerLanguage` alongside the other content model imports, then register:
```python
@admin.register(ReviewerLanguage)
class ReviewerLanguageAdmin(admin.ModelAdmin):
    list_display = ("user", "language")
    list_filter = ("language",)
    search_fields = ("user__email", "user__name", "language")
    autocomplete_fields = ("user",)
```
If `User` is not registered with search fields, drop `autocomplete_fields` and use `raw_id_fields = ("user",)` instead.

- [ ] **Step 5: Make the migration**

Run: `.venv/bin/python manage.py makemigrations content --name review_models`
Expected: a new migration adds `ReviewerLanguage` and `AssetVersionChangeReview`. Confirm it depends on the latest content migration.

- [ ] **Step 6: Run tests (create DB)**

Run: `.venv/bin/pytest apps/content/tests/models/test_review_models.py --create-db -q`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add apps/content/models.py apps/content/admin.py apps/content/migrations/ apps/content/tests/models/test_review_models.py
git commit -m "feat(content): add ReviewerLanguage and AssetVersionChangeReview models"
```

---

## Task 3: Review repository + service

**Files:**
- Create: `apps/content/repositories/asset_review.py`
- Create: `apps/content/services/asset_review.py`
- Test: `apps/content/tests/services/test_asset_review.py`

**Interfaces:**
- Consumes: `ReviewerLanguage`, `AssetVersionChange`, `AssetVersionChangeReview`, `ReviewStateChoice`, `Asset`, `CategoryChoice`.
- Produces (service `AssetReviewService`):
  - `assigned_languages(user) -> set[str]`
  - `list_review_languages(slug, category, *, user, publisher_q) -> list[str]`
  - `list_changes(slug, category, *, language, user, state, publisher_q) -> QuerySet[AssetVersionChange]` (each annotated/prefetched with `review`)
  - `set_review_state(slug, category, *, change_id, user, state, comment, publisher_q) -> AssetVersionChange`
  - module helper `change_language(change) -> str`

- [ ] **Step 1: Write failing service tests**

Create `apps/content/tests/services/test_asset_review.py`:
```python
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetVersion,
    AssetVersionChange,
    CategoryChoice,
    ReviewerLanguage,
    ReviewStateChoice,
    StatusChoice,
)
from apps.content.services.asset_review import AssetReviewService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetReviewServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY, language="ar", slug="t1"
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr")
        self.version = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v1")
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="au nom", order=1
        )
        self.reviewer = User.objects.create_user(email="rev@example.com", name="Rev")
        ReviewerLanguage.objects.create(user=self.reviewer, language="fr")

    def test_set_review_state_where_assigned_should_approve_and_record_auditing(self):
        # Act
        change = AssetReviewService().set_review_state(
            "t1", CategoryChoice.TRANSLATION, change_id=self.change.id, user=self.reviewer,
            state="approved", comment="",
        )
        # Assert
        self.assertEqual(ReviewStateChoice.APPROVED, change.review.state)
        self.assertEqual(self.reviewer, change.review.reviewed_by)
        self.assertIsNotNone(change.review.reviewed_at)

    def test_set_review_state_where_commented_without_text_should_raise(self):
        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().set_review_state(
                "t1", CategoryChoice.TRANSLATION, change_id=self.change.id, user=self.reviewer,
                state="commented", comment="   ",
            )
        self.assertEqual("review_comment_required", ctx.exception.error_name)

    def test_set_review_state_where_language_not_assigned_should_raise_403(self):
        # Arrange — reviewer only assigned 'fr'; make an 'ar' (source) change
        source = self.asset.get_or_create_source_language()
        src_version = baker.make(AssetVersion, asset=self.asset, asset_language=source, name="src")
        src_change = baker.make(
            AssetVersionChange, version=src_version, ayah=self.ayah, change_type="added", new_text="بسم", order=1
        )
        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().set_review_state(
                "t1", CategoryChoice.TRANSLATION, change_id=src_change.id, user=self.reviewer,
                state="approved", comment="",
            )
        self.assertEqual("language_not_assigned", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_set_review_state_unreviewed_deletes_row(self):
        # Arrange
        svc = AssetReviewService()
        svc.set_review_state("t1", CategoryChoice.TRANSLATION, change_id=self.change.id, user=self.reviewer,
                             state="approved", comment="")
        # Act
        change = svc.set_review_state("t1", CategoryChoice.TRANSLATION, change_id=self.change.id, user=self.reviewer,
                                      state="unreviewed", comment="")
        # Assert
        self.assertFalse(hasattr(change, "review") and change.__dict__.get("review"))
        self.change.refresh_from_db()
        self.assertFalse(AssetVersionChange.objects.get(pk=self.change.id).__dict__.get("review", None) or
                         hasattr(self.change, "review") and self.change.review is not None and False)
        from apps.content.models import AssetVersionChangeReview
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change).exists())

    def test_list_review_languages_returns_intersection(self):
        # Act
        langs = AssetReviewService().list_review_languages("t1", CategoryChoice.TRANSLATION, user=self.reviewer)
        # Assert — only 'fr' (assigned) even though the asset also has 'ar'
        self.assertEqual(["fr"], langs)

    def test_list_changes_filters_by_language_and_state(self):
        # Act — unreviewed filter returns the pending change
        qs = AssetReviewService().list_changes(
            "t1", CategoryChoice.TRANSLATION, language="fr", user=self.reviewer, state="unreviewed"
        )
        # Assert
        self.assertEqual([self.change.id], [c.id for c in qs])

    def test_list_changes_where_language_not_assigned_should_raise_403(self):
        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().list_changes(
                "t1", CategoryChoice.TRANSLATION, language="ar", user=self.reviewer, state=None
            )
        self.assertEqual("language_not_assigned", ctx.exception.error_name)
```

Note: `_get_asset_or_404` needs `publisher_q=None` to default to all assets in tests; the service signatures below make `publisher_q` optional.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_review.py -q`
Expected: FAIL (module `apps.content.services.asset_review` does not exist).

- [ ] **Step 3: Write the repository**

Create `apps/content/repositories/asset_review.py`:
```python
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.content.models import Asset, AssetVersionChange, ReviewStateChoice


def change_language(change: AssetVersionChange) -> str:
    """The language a change belongs to: its version's asset_language, else the
    asset's source language (legacy rows with no asset_language)."""
    version = change.version
    if version.asset_language_id:
        return version.asset_language.language
    return version.asset.language


class AssetReviewRepository:
    def changes_for(self, asset: Asset, language: str, *, state: str | None = None) -> QuerySet[AssetVersionChange]:
        """All change rows for one (asset, language), newest-commit first, with
        their review prefetched. Optional state filter (unreviewed/approved/commented)."""
        language_q = Q(version__asset_language__language=language)
        if language == asset.language:
            language_q |= Q(version__asset_language__isnull=True)
        qs = (
            AssetVersionChange.objects.filter(version__asset=asset)
            .filter(language_q)
            .select_related("ayah", "ayah__sura", "version", "review", "review__reviewed_by")
        )
        if state == "unreviewed":
            qs = qs.filter(review__isnull=True)
        elif state in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            qs = qs.filter(review__state=state)
        return qs.order_by("-version__created_at", "-version_id", "order", "ayah_id")

    def get_change(self, asset: Asset, change_id: int) -> AssetVersionChange | None:
        return (
            AssetVersionChange.objects.filter(version__asset=asset, pk=change_id)
            .select_related("version", "version__asset_language", "version__asset", "review")
            .first()
        )
```

- [ ] **Step 4: Write the service**

Create `apps/content/services/asset_review.py`:
```python
from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.content.models import (
    Asset,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewerLanguage,
    ReviewStateChoice,
    StatusChoice,
)
from apps.content.repositories.asset_review import AssetReviewRepository, change_language
from apps.core.ninja_utils.errors import ItqanError

_NOT_FOUND_ERROR = {
    CategoryChoice.TRANSLATION: "translation_not_found",
    CategoryChoice.TAFSIR: "tafsir_not_found",
}


class AssetReviewService:
    def __init__(self, repo: AssetReviewRepository | None = None) -> None:
        self.repo = repo or AssetReviewRepository()

    def _get_asset_or_404(self, slug: str, category: CategoryChoice, publisher_q: Q | None = None) -> Asset:
        qs = Asset.objects.all()
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        try:
            return qs.get(slug=slug, category=category, status=StatusChoice.READY)
        except Asset.DoesNotExist as exc:
            raise ItqanError(
                error_name=_NOT_FOUND_ERROR[category],
                message=_("{category} with slug {slug} not found.").format(category=category.label, slug=slug),
                status_code=404,
            ) from exc

    def assigned_languages(self, user) -> set[str]:
        return set(ReviewerLanguage.objects.filter(user=user).values_list("language", flat=True))

    def _require_assigned(self, user, language: str) -> None:
        if language not in self.assigned_languages(user):
            raise ItqanError(
                error_name="language_not_assigned",
                message=_("You are not assigned to review this language."),
                status_code=403,
            )

    def list_review_languages(
        self, slug: str, category: CategoryChoice, *, user, publisher_q: Q | None = None
    ) -> list[str]:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        asset_languages = set(asset.languages.values_list("language", flat=True))
        asset_languages.add(asset.language)  # source, even if the row is lazy
        return sorted(asset_languages & self.assigned_languages(user))

    def list_changes(
        self, slug: str, category: CategoryChoice, *, language: str, user, state: str | None,
        publisher_q: Q | None = None,
    ) -> QuerySet[AssetVersionChange]:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        self._require_assigned(user, language)
        return self.repo.changes_for(asset, language, state=state)

    def set_review_state(
        self, slug: str, category: CategoryChoice, *, change_id: int, user, state: str, comment: str,
        publisher_q: Q | None = None,
    ) -> AssetVersionChange:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        change = self.repo.get_change(asset, change_id)
        if change is None:
            raise ItqanError(
                error_name="change_not_found",
                message=_("Change with id {id} not found.").format(id=change_id),
                status_code=404,
            )
        self._require_assigned(user, change_language(change))

        if state == "unreviewed":
            AssetVersionChangeReview.objects.filter(change=change).delete()
            return change

        if state not in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            raise ItqanError(
                error_name="invalid_review_state",
                message=_("Invalid review state."),
                status_code=400,
            )
        comment = (comment or "").strip()
        if state == ReviewStateChoice.COMMENTED and not comment:
            raise ItqanError(
                error_name="review_comment_required",
                message=_("A comment is required when requesting changes."),
                status_code=400,
            )
        AssetVersionChangeReview.objects.update_or_create(
            change=change,
            defaults={
                "state": state,
                "comment": comment if state == ReviewStateChoice.COMMENTED else "",
                "reviewed_by": user,
                "reviewed_at": timezone.now(),
            },
        )
        change.refresh_from_db()
        return change
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_review.py --create-db -q`
Expected: PASS. (If the `test_set_review_state_unreviewed_deletes_row` assertions read awkwardly, simplify to assert `AssetVersionChangeReview.objects.filter(change=self.change).exists()` is `False`.)

- [ ] **Step 6: Commit**
```bash
git add apps/content/repositories/asset_review.py apps/content/services/asset_review.py apps/content/tests/services/test_asset_review.py
git commit -m "feat(content): add review service + repository"
```

---

## Task 4: Portal review API

**Files:**
- Create: `apps/content/api/portal/asset_review.py`
- Test: `apps/content/tests/portal/test_asset_review.py`

**Interfaces:**
- Consumes: `AssetReviewService`, `change_language`, `PermissionChoice.PORTAL_REVIEW_CONTENT`, `check_permission`, `NinjaPagination`.
- Produces endpoints under `/portal/`:
  - `GET content/{category}/{slug}/review/languages/`
  - `GET content/{category}/{slug}/review/changes/?language=&state=`
  - `PATCH content/{category}/{slug}/review/changes/{change_id}/`

- [ ] **Step 1: Write failing endpoint tests**

Create `apps/content/tests/portal/test_asset_review.py` covering:
```python
from model_bakery import baker

from apps.content.models import (
    Asset, AssetLanguage, AssetVersion, AssetVersionChange, AssetVersionChangeReview,
    CategoryChoice, ReviewerLanguage, ReviewStateChoice, StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetReviewApiBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="P")
        self.asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, publisher=self.publisher,
            status=StatusChoice.READY, language="ar", slug="t1",
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr")
        self.version = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v1")
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="au nom", order=1
        )
        self.user = User.objects.create_user(email="rev@example.com", name="Rev", is_staff=True)


class ReviewPermissionTest(AssetReviewApiBaseTest):
    def test_list_changes_where_no_review_permission_should_return_403(self):
        self.authenticate_user(self.user)  # no PORTAL_REVIEW_CONTENT granted
        ReviewerLanguage.objects.create(user=self.user, language="fr")
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/changes/?language=fr")
        self.assertEqual(403, response.status_code, response.content)


class ReviewAssignmentTest(AssetReviewApiBaseTest):
    def test_list_changes_where_language_not_assigned_should_return_403(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        # assigned to 'es', not 'fr'
        ReviewerLanguage.objects.create(user=self.user, language="es")
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/changes/?language=fr")
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_list_languages_returns_only_assigned(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        ReviewerLanguage.objects.create(user=self.user, language="fr")
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/languages/")
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["fr"], response.json())


class ReviewActionTest(AssetReviewApiBaseTest):
    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        ReviewerLanguage.objects.create(user=self.user, language="fr")

    def test_approve_change_sets_state_and_auditing(self):
        self._auth_reviewer()
        response = self.client.patch(
            f"/portal/content/translations/{self.asset.slug}/review/changes/{self.change.id}/",
            data={"state": "approved"}, content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("approved", body["review_state"])
        self.assertEqual("Rev", body["reviewed_by"])
        self.assertTrue(AssetVersionChangeReview.objects.filter(change=self.change, state="approved").exists())

    def test_comment_without_text_returns_400(self):
        self._auth_reviewer()
        response = self.client.patch(
            f"/portal/content/translations/{self.asset.slug}/review/changes/{self.change.id}/",
            data={"state": "commented", "comment": "  "}, content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("review_comment_required", response.json()["error_name"])

    def test_unreviewed_clears_row(self):
        self._auth_reviewer()
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user,
            reviewed_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
        )
        response = self.client.patch(
            f"/portal/content/translations/{self.asset.slug}/review/changes/{self.change.id}/",
            data={"state": "unreviewed"}, content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change).exists())

    def test_list_changes_returns_change_fields(self):
        self._auth_reviewer()
        response = self.client.get(
            f"/portal/content/translations/{self.asset.slug}/review/changes/?language=fr"
        )
        self.assertEqual(200, response.status_code, response.content)
        row = response.json()["results"][0]
        self.assertEqual(self.change.id, row["id"])
        self.assertEqual(1, row["sura"])
        self.assertEqual(1, row["aya"])
        self.assertEqual("added", row["change_type"])
        self.assertEqual("unreviewed", row["review_state"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_review.py -q`
Expected: FAIL (404s / router not registered).

- [ ] **Step 3: Write the API module**

Create `apps/content/api/portal/asset_review.py`:
```python
from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.api.portal.asset_content import _CATEGORY_CONFIG
from apps.content.models import AssetVersionChange, CategoryChoice
from apps.content.repositories.asset_review import change_language
from apps.content.services.asset_review import AssetReviewService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.paginations import NinjaPagination
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


def _resolve_review(category: str, request: Request) -> CategoryChoice:
    """Resolve the category segment (translations/tafsirs only) and enforce the
    single review permission — review uses one permission, not the per-category ones."""
    config = _CATEGORY_CONFIG.get(category)
    if config is None:
        raise ItqanError(
            error_name="unsupported_content_category",
            message=_("Unsupported content category: {category}").format(category=category),
            status_code=404,
        )
    check_permission(request.user, PermissionChoice.PORTAL_REVIEW_CONTENT, raise_exception=True)
    return config[0]


class ReviewChangeOut(Schema):
    id: int
    sura: int
    aya: int
    surah_name: str
    change_type: str
    old_text: str
    new_text: str
    commit_ref: str
    commit_id: int
    review_state: str
    comment: str
    reviewed_by: str | None
    reviewed_at: AwareDatetime | None

    @staticmethod
    def resolve_sura(obj: AssetVersionChange) -> int:
        return obj.ayah.sura_id

    @staticmethod
    def resolve_aya(obj: AssetVersionChange) -> int:
        return obj.ayah.number_in_sura

    @staticmethod
    def resolve_surah_name(obj: AssetVersionChange) -> str:
        return obj.ayah.sura.name

    @staticmethod
    def resolve_commit_ref(obj: AssetVersionChange) -> str:
        return obj.version.name

    @staticmethod
    def resolve_commit_id(obj: AssetVersionChange) -> int:
        return obj.version_id

    @staticmethod
    def resolve_review_state(obj: AssetVersionChange) -> str:
        review = getattr(obj, "review", None)
        return review.state if review is not None else "unreviewed"

    @staticmethod
    def resolve_comment(obj: AssetVersionChange) -> str:
        review = getattr(obj, "review", None)
        return review.comment if review is not None else ""

    @staticmethod
    def resolve_reviewed_by(obj: AssetVersionChange) -> str | None:
        review = getattr(obj, "review", None)
        return review.reviewed_by.name if review is not None and review.reviewed_by_id else None

    @staticmethod
    def resolve_reviewed_at(obj: AssetVersionChange):
        review = getattr(obj, "review", None)
        return review.reviewed_at if review is not None else None


class ReviewStateIn(Schema):
    state: Literal["approved", "commented", "unreviewed"]
    comment: str = ""


_REVIEW_ERRORS = (
    NinjaErrorResponse[Literal["translation_not_found"]]
    | NinjaErrorResponse[Literal["tafsir_not_found"]]
    | NinjaErrorResponse[Literal["unsupported_content_category"]]
    | NinjaErrorResponse[Literal["language_not_assigned"]]
)


@router.get(
    "content/{category}/{slug}/review/languages/",
    response={200: list[str], 403: NinjaErrorResponse[Literal["permission_denied"]], 404: _REVIEW_ERRORS},
)
def list_review_languages(request: Request, category: str, slug: str) -> list[str]:
    resolved = _resolve_review(category, request)
    return AssetReviewService().list_review_languages(
        slug, resolved, user=request.user, publisher_q=request.publisher_q()
    )


@router.get(
    "content/{category}/{slug}/review/changes/",
    response={200: list[ReviewChangeOut], 403: _REVIEW_ERRORS, 404: _REVIEW_ERRORS},
)
@paginate(NinjaPagination)
def list_review_changes(
    request: Request, category: str, slug: str, language: str, state: str | None = None
):
    resolved = _resolve_review(category, request)
    return AssetReviewService().list_changes(
        slug, resolved, language=language, user=request.user, state=state, publisher_q=request.publisher_q()
    )


@router.patch(
    "content/{category}/{slug}/review/changes/{change_id}/",
    response={
        200: ReviewChangeOut,
        400: NinjaErrorResponse[Literal["review_comment_required"]] | NinjaErrorResponse[Literal["invalid_review_state"]],
        403: _REVIEW_ERRORS,
        404: _REVIEW_ERRORS | NinjaErrorResponse[Literal["change_not_found"]],
    },
)
def set_review_state(
    request: Request, category: str, slug: str, change_id: int, data: ReviewStateIn
) -> AssetVersionChange:
    resolved = _resolve_review(category, request)
    return AssetReviewService().set_review_state(
        slug, resolved, change_id=change_id, user=request.user, state=data.state, comment=data.comment,
        publisher_q=request.publisher_q(),
    )
```

Verify the router auto-registration: portal routers are auto-discovered (like `asset_languages.py`). If registration is explicit somewhere, add this module the same way the other portal routers are added.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_review.py --create-db -q`
Expected: PASS. Fix any pagination-shape assertions to match `NinjaPagination` (`results`/`count`).

- [ ] **Step 5: Run the whole content suite**

Run: `.venv/bin/pytest apps/content --create-db -q`
Expected: all pass.

- [ ] **Step 6: Commit**
```bash
git add apps/content/api/portal/asset_review.py apps/content/tests/portal/test_asset_review.py
git commit -m "feat(content): add portal review API"
```

---

## Task 5: Backend localization

**Files:**
- Modify: `locale/ar/LC_MESSAGES/django.po`

**Interfaces:**
- Consumes: the new `_()` strings from Tasks 3–4 and the `Commented` choice label from Task 2.

- [ ] **Step 1: Capture new strings**

Run: `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header`
(Or the `.venv` equivalent of the Actions `makemessages` command.)

- [ ] **Step 2: Add Arabic translations**

Fill in the `msgstr` for every newly added `msgid`, including:
- `"Commented"` → `"يحتاج إلى تعديل"`
- `"You are not assigned to review this language."` → `"لست مُكلَّفًا بمراجعة هذه اللغة."`
- `"A comment is required when requesting changes."` → `"التعليق مطلوب عند طلب إجراء تعديلات."`
- `"Invalid review state."` → `"حالة مراجعة غير صالحة."`
- `"Change with id {id} not found."` → `"لم يتم العثور على التغيير بالمعرّف {id}."`

(Confirm exact set from the makemessages diff; translate any others it surfaces.)

- [ ] **Step 3: Run the localization check (REQUIRED gate)**

Run: `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null`
Expected: `N translated messages` with **0 untranslated** and no errors.

Then: `.venv/bin/python manage.py compilemessages -l ar`
Expected: compiles without error.

- [ ] **Step 4: Commit**
```bash
git add locale/ar/LC_MESSAGES/django.po
git commit -m "i18n(ar): translate review-phase strings"
```

---

## Task 6: Frontend permission, models, service

**Files:**
- Modify: `cms-frontend/src/app/features/admin/constants/portal-permission.constants.ts`
- Create: `cms-frontend/src/app/features/admin/models/asset-review.models.ts`
- Create: `cms-frontend/src/app/features/admin/services/asset-review.service.ts`

**Interfaces:**
- Produces:
  - `PORTAL_PERMISSIONS.PORTAL_REVIEW_CONTENT = 'portal_review_content'`
  - `ReviewChange`, `ReviewState`, `ReviewChangesResponse` types
  - `AssetReviewService` with `listLanguages`, `listChanges`, `setState`

- [ ] **Step 1: Add the permission constant**

In `portal-permission.constants.ts`, add to the `PORTAL_PERMISSIONS` object:
```ts
  PORTAL_REVIEW_CONTENT: 'portal_review_content',
```

- [ ] **Step 2: Add models**

Create `asset-review.models.ts`:
```ts
export type ReviewState = 'unreviewed' | 'approved' | 'commented';

export interface ReviewChange {
  id: number;
  sura: number;
  aya: number;
  surah_name: string;
  change_type: 'added' | 'modified' | 'removed';
  old_text: string;
  new_text: string;
  commit_ref: string;
  commit_id: number;
  review_state: ReviewState;
  comment: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface ReviewChangesResponse {
  results: ReviewChange[];
  count: number;
}
```

- [ ] **Step 3: Add the service**

Create `asset-review.service.ts` (mirror `AssetContentService`'s base-URL pattern; `kind` is `'translation' | 'tafsir'`, segment `translations`/`tafsirs`):
```ts
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';
import type { AssetVersionParentKind } from '../models/asset-versions.models';
import type { ReviewChange, ReviewChangesResponse, ReviewState } from '../models/asset-review.models';

@Injectable({ providedIn: 'root' })
export class AssetReviewService {
  private readonly http = inject(HttpClient);

  private base(kind: AssetVersionParentKind, slug: string): string {
    const segment = kind === 'tafsir' ? 'tafsirs' : 'translations';
    return `${environment.ADMIN_API_BASE_URL}/content/${segment}/${slug}/review/`;
  }

  listLanguages(kind: AssetVersionParentKind, slug: string): Observable<string[]> {
    return this.http.get<string[]>(`${this.base(kind, slug)}languages/`);
  }

  listChanges(
    kind: AssetVersionParentKind, slug: string, language: string,
    page: number, pageSize: number, state?: ReviewState | null,
  ): Observable<ReviewChangesResponse> {
    let params = new HttpParams()
      .set('language', language)
      .set('page', page.toString())
      .set('page_size', pageSize.toString());
    if (state) params = params.set('state', state);
    return this.http.get<ReviewChangesResponse>(`${this.base(kind, slug)}changes/`, { params });
  }

  setState(
    kind: AssetVersionParentKind, slug: string, changeId: number,
    state: ReviewState, comment?: string,
  ): Observable<ReviewChange> {
    return this.http.patch<ReviewChange>(
      `${this.base(kind, slug)}changes/${changeId}/`,
      { state, comment: comment ?? '' },
    );
  }
}
```
Confirm the exact base-URL constant by matching `AssetContentService` (it may use a shared helper rather than `environment.ADMIN_API_BASE_URL`); reuse whatever it uses.

- [ ] **Step 4: Verify**

Run: `cd cms-frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**
```bash
git add src/app/features/admin/constants/portal-permission.constants.ts src/app/features/admin/models/asset-review.models.ts src/app/features/admin/services/asset-review.service.ts
git commit -m "feat(admin): review models + service + permission constant"
```

---

## Task 7: Frontend review grid component

**Files:**
- Create: `cms-frontend/src/app/features/admin/components/asset-review-grid/asset-review-grid.component.ts`
- Create: `cms-frontend/src/app/features/admin/components/asset-review-grid/asset-review-grid.component.html`
- Create: `cms-frontend/src/app/features/admin/components/asset-review-grid/asset-review-grid.component.less`

**Interfaces:**
- Consumes: `AssetReviewService`, `AdminAuthService.hasPermission`, `PORTAL_PERMISSIONS`, localized-language-name util, ng-zorro modules.
- Inputs: `@Input({required:true}) kind: AssetVersionParentKind`, `@Input({required:true}) slug: string`.
- Produces: `<app-asset-review-grid>` — the reviewer surface.

- [ ] **Step 1: Build the component**

Create the component (standalone; mirror `asset-versions-manager` structure). Requirements:
- `canReview = this.adminAuth.hasPermission(PORTAL_PERMISSIONS.PORTAL_REVIEW_CONTENT)`. Render nothing/hidden when false.
- `ngOnInit`: `listLanguages(kind, slug)` → `languages` signal; default `selectedLanguage` to the first; then `loadChanges()`.
- Signals: `languages`, `selectedLanguage`, `changes`, `total`, `page`, `pageSize` (e.g. 20), `loading`, `stateFilter` (`'all'|'unreviewed'|'approved'|'commented'`, default `'unreviewed'`), `savingId` (number|null), comment-dialog state (`commentOpen`, `commentText`, `commentChangeId`).
- `loadChanges()`: `listChanges(kind, slug, selectedLanguage, page, pageSize, filter==='all'?null:filter)`.
- `onLanguageChange(lang)`, `onFilterChange(f)`, `onPageChange(p)` → reload.
- `approve(row)`: `setState(..., 'approved')` → replace row in `changes`, success toast.
- `markUnreviewed(row)`: `setState(..., 'unreviewed')` → replace row.
- `openComment(row)`: prefill `commentText` with `row.comment`, open dialog. `confirmComment()`: `setState(..., 'commented', commentText)`; guard non-empty; on success replace row + close.
- Error handling: map `error_name` → `ADMIN.REVIEW.ERRORS.<UPPER>` else generic (mirror versions-manager's inline handler).
- `langName(code)` via `localizedLanguageName`.
- If `languages()` is empty → show `ADMIN.REVIEW.NO_ASSIGNED_LANGUAGES`.

- [ ] **Step 2: Build the template**

Create the HTML: a section titled `ADMIN.REVIEW.TITLE`; language `nz-select` (assigned languages); a state-filter `nz-select` (All/Unreviewed/Approved/Commented); an `nz-table` with columns: ayah ref (`{{surah_name}} {{row.sura}}:{{row.aya}}`), change type badge, old→new text (stacked, `old_text` struck / `new_text`), commit ref, review state badge, reviewed-by/at, and an actions cell with **Approve** (check), **Comment** (message icon), **Unreviewed** (undo) buttons — the current state's button shown as active. Include pagination (`app-admin-table-pagination` like versions-manager) and a comment `nz-modal` (textarea bound to `commentText`, OK disabled when empty, calls `confirmComment()`). Read-only on content.

- [ ] **Step 3: Style (LESS)**

Add minimal styles: state badges (approved=green, commented=amber, unreviewed=grey), stacked old/new text (old = muted + line-through, new = normal), toolbar layout. Reuse the availability badge pattern from `asset-versions-manager.component.less`.

- [ ] **Step 4: Verify build**

Run: `cd cms-frontend && npx tsc --noEmit && npx eslint src/app/features/admin/components/asset-review-grid/asset-review-grid.component.ts`
Expected: clean.

- [ ] **Step 5: Commit**
```bash
git add src/app/features/admin/components/asset-review-grid/
git commit -m "feat(admin): translation review grid component"
```

---

## Task 8: Wire into detail pages + i18n + final verification

**Files:**
- Modify: `cms-frontend/src/app/features/admin/tafsirs/components/tafsir-detail/tafsir-detail.component.html` (+ `.ts` import)
- Modify: `cms-frontend/src/app/features/admin/translations/components/translation-detail/translation-detail.component.html` (+ `.ts` import)
- Modify: `cms-frontend/public/i18n/en.json`, `cms-frontend/public/i18n/ar.json`

- [ ] **Step 1: Add the grid to the detail pages**

In both `tafsir-detail` and `translation-detail` templates, after `<app-asset-versions-manager …/>`, add (only rendered for reviewers):
```html
<app-asset-review-grid kind="tafsir" [slug]="tafsir()!.slug" />
```
(`kind="translation"` and `translation()!.slug` in the translation page.) Import `AssetReviewGridComponent` into each component's `imports`. The component self-hides when the user lacks `PORTAL_REVIEW_CONTENT`, but also guard with `@if` for clarity if the detail component already exposes a permission signal.

- [ ] **Step 2: Add i18n keys (en + ar)**

Add an `ADMIN.REVIEW` block to both `en.json` and `ar.json` with parity: `TITLE`, `LANGUAGE_LABEL`, `NO_ASSIGNED_LANGUAGES`, `FILTER.{ALL,UNREVIEWED,APPROVED,COMMENTED}`, `STATE.{UNREVIEWED,APPROVED,COMMENTED}`, `ACTION.{APPROVE,COMMENT,UNREVIEW}`, `COLUMN.{AYAH,TYPE,CHANGE,COMMIT,STATE,REVIEWER,ACTIONS}`, `COMMENT_DIALOG.{TITLE,PLACEHOLDER,CONFIRM,CANCEL}`, `MESSAGES.{APPROVED,COMMENTED,UNREVIEWED}`, `ERRORS.{REVIEW_COMMENT_REQUIRED,LANGUAGE_NOT_ASSIGNED,GENERIC}`. Provide real Arabic translations (e.g. `TITLE` → `"مراجعة التغييرات"`, `STATE.COMMENTED` → `"يحتاج إلى تعديل"`).

- [ ] **Step 3: i18n parity + build**

Run: `cd cms-frontend && node scripts/check-arabic-translations.js`
Expected: parity passes.

Run: `npx tsc --noEmit && npx ng build --configuration staging`
Expected: build succeeds (template type-checking clean).

Run: `npx prettier --write` on all changed files; `npx eslint` on changed TS.
Expected: clean.

- [ ] **Step 4: Commit**
```bash
git add src/app/features/admin/tafsirs/ src/app/features/admin/translations/ public/i18n/en.json public/i18n/ar.json
git commit -m "feat(admin): surface review grid on asset detail + i18n"
```

---

## Task 9: Docs

**Files:**
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Document the review subsystem**

Update `docs/ARCHITECTURE.md`: add `ReviewerLanguage` and `AssetVersionChangeReview` to the models/ER section, the `PORTAL_REVIEW_CONTENT` permission to access control, and a short "content review (audit-only)" note in the content lifecycle. Keep the existing structure and update the mermaid ER diagram to include the two new models and their relations.

- [ ] **Step 2: Commit**
```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: document translation review subsystem"
```

---

## Self-review notes

- **Spec coverage:** models+permission (T1–2), assignment via admin (T2), enforcement/service (T3), API incl. permission+assignment 403s, list/patch, pagination, state filter (T4), localization gate (T5), frontend permission-gated grid limited to assigned languages with the three-state control + comment dialog (T6–8), audit via `reviewed_by`/`reviewed_at` (T2/T4), docs (T9). Audit-only — no gating touched anywhere. ✔
- **Type consistency:** `review_state`/`ReviewState` values `unreviewed|approved|commented` are consistent across backend `ReviewChangeOut.resolve_review_state`, `ReviewStateIn`, and frontend `ReviewState`. `kind` segments `translations`/`tafsirs` consistent with `_CATEGORY_CONFIG`.
- **No placeholders:** all steps carry concrete code or concrete instructions; the two larger frontend UI tasks (T7 template/styles) are described by explicit requirements mirroring the existing `asset-versions-manager` component rather than pasted verbatim, since they are new UI with no exact prior source.
