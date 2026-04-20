from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher
from apps.publishers.repositories.publisher import PublisherRepository


class PublisherService:
    def __init__(self, repo: PublisherRepository) -> None:
        self.repo = repo

    def create_publisher(
        self,
        *,
        name_ar: str | None,
        name_en: str | None,
        description_ar: str | None,
        description_en: str | None,
        address: str = "",
        website: str = "",
        contact_email: str = "",
        is_verified: bool = True,
        foundation_year: int | None = None,
        country: str = "",
        icon_url: object | None = None,
    ) -> Publisher:
        name = name_ar or name_en
        if not name or not name.strip():
            raise ItqanError(
                error_name="publisher_name_required",
                message="Publisher name (Arabic or English) is required",
                status_code=400,
            )

        slug = slugify(name[:50], allow_unicode=True)

        if self.repo.slug_exists(slug):
            raise ItqanError(
                error_name="publisher_already_exists",
                message=f"A publisher with slug '{slug}' already exists",
                status_code=400,
            )

        description = description_ar or description_en
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
            "icon_url": icon_url,
        }
        if name_ar:
            kwargs["name_ar"] = name_ar
        if name_en:
            kwargs["name_en"] = name_en
        if description_ar:
            kwargs["description_ar"] = description_ar
        if description_en:
            kwargs["description_en"] = description_en

        try:
            return self.repo.create(**kwargs)
        except IntegrityError as exc:
            raise ItqanError(
                error_name="publisher_already_exists",
                message=f"A publisher with slug '{slug}' already exists",
                status_code=400,
            ) from exc

    def get_publisher(self, publisher_id: int) -> Publisher:
        publisher = self.repo.get_by_id(publisher_id)
        if publisher is None:
            raise ItqanError(
                error_name="publisher_not_found",
                message=f"Publisher with id {publisher_id} not found",
                status_code=404,
            )
        return publisher

    def update_publisher(self, publisher_id: int, *, fields: dict[str, object]) -> Publisher:
        publisher = self.get_publisher(publisher_id)

        if "name_ar" in fields or "name_en" in fields:
            name_ar = fields.get("name_ar")
            name_en = fields.get("name_en")
            new_name = (
                name_ar
                or name_en
                or getattr(publisher, "name_ar", "")
                or getattr(publisher, "name_en", "")
                or publisher.name
            )
            if not str(new_name).strip():
                raise ItqanError(
                    error_name="publisher_name_required",
                    message="Publisher name (Arabic or English) is required",
                    status_code=400,
                )
            slug = slugify(str(new_name)[:50], allow_unicode=True)
            if self.repo.slug_exists(slug, exclude_id=publisher_id):
                raise ItqanError(
                    error_name="publisher_already_exists",
                    message=f"A publisher with slug '{slug}' already exists",
                    status_code=400,
                )
            fields["name"] = str(new_name).strip()
            fields["slug"] = slug

        if "description_ar" in fields or "description_en" in fields:
            desc_ar = fields.get("description_ar")
            desc_en = fields.get("description_en")
            new_desc = (
                desc_ar
                or desc_en
                or getattr(publisher, "description_ar", "")
                or getattr(publisher, "description_en", "")
                or publisher.description
            )
            fields["description"] = new_desc

        # Skip empty translation fields to avoid overriding modeltranslation values
        translation_fields = {"name_ar", "name_en", "description_ar", "description_en"}
        for key, value in fields.items():
            if key in translation_fields and value == "":
                continue
            setattr(publisher, key, value)
        publisher.save()
        return publisher

    def delete_publisher(self, publisher_id: int) -> None:
        publisher = self.get_publisher(publisher_id)
        try:
            self.repo.delete(publisher)
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Publisher because they are referenced through other objects")),
                status_code=400,
            ) from exc
