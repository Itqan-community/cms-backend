from django.db import IntegrityError
from django.utils.text import slugify

from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher
from apps.publishers.repositories.publisher import PublisherRepository


class PublisherService:
    def __init__(self, repo: PublisherRepository) -> None:
        self.repo = repo

    def create_publisher(
        self,
        *,
        name: str,
        name_ar: str = "",
        name_en: str = "",
        description: str = "",
        description_ar: str = "",
        address: str = "",
        website: str = "",
        contact_email: str = "",
        is_verified: bool = True,
        foundation_year: int | None = None,
        country: str = "",
    ) -> Publisher:
        if not name or not name.strip():
            raise ItqanError(
                error_name="publisher_name_required",
                message="Publisher name is required",
                status_code=400,
            )

        slug = slugify(name[:50], allow_unicode=True)

        if self.repo.slug_exists(slug):
            raise ItqanError(
                error_name="publisher_already_exists",
                message=f"A publisher with slug '{slug}' already exists",
                status_code=400,
            )

        kwargs: dict[str, object] = {
            "name": name.strip(),
            "slug": slug,
            "description": description,
            "address": address,
            "website": website,
            "contact_email": contact_email,
            "is_verified": is_verified,
            "foundation_year": foundation_year,
            "country": country,
        }
        if name_ar:
            kwargs["name_ar"] = name_ar
        if name_en:
            kwargs["name_en"] = name_en
        if description_ar:
            kwargs["description_ar"] = description_ar

        try:
            return self.repo.create(**kwargs)
        except IntegrityError as exc:
            raise ItqanError(
                error_name="publisher_already_exists",
                message=f"A publisher with slug '{slug}' already exists",
                status_code=400,
            ) from exc
