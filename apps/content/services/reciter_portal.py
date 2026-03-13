from django.db import IntegrityError
from django.utils.text import slugify

from apps.content.models import Reciter
from apps.content.repositories.reciter import ReciterRepository
from apps.core.ninja_utils.errors import ItqanError


class ReciterPortalService:
    def __init__(self, repo: ReciterRepository) -> None:
        self.repo = repo

    def create_reciter(
        self,
        *,
        name: str,
        name_ar: str = "",
        name_en: str = "",
        bio: str = "",
        bio_ar: str = "",
        bio_en: str = "",
        is_active: bool = True,
    ) -> Reciter:
        if not name or not name.strip():
            raise ItqanError(
                error_name="reciter_name_required",
                message="Reciter name is required",
                status_code=400,
            )

        slug = slugify(name[:50], allow_unicode=True)

        if self.repo.slug_exists(slug):
            raise ItqanError(
                error_name="reciter_already_exists",
                message=f"A reciter with slug '{slug}' already exists",
                status_code=400,
            )

        kwargs: dict[str, object] = {
            "name": name.strip(),
            "slug": slug,
            "bio": bio,
            "is_active": is_active,
        }
        if name_ar:
            kwargs["name_ar"] = name_ar
        if name_en:
            kwargs["name_en"] = name_en
        if bio_ar:
            kwargs["bio_ar"] = bio_ar
        if bio_en:
            kwargs["bio_en"] = bio_en

        try:
            return self.repo.create(**kwargs)
        except IntegrityError as exc:
            raise ItqanError(
                error_name="reciter_already_exists",
                message="A reciter with this name or slug already exists",
                status_code=400,
            ) from exc
