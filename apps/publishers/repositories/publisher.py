from apps.publishers.models import Publisher


class PublisherRepository:
    def create(self, **kwargs: object) -> Publisher:
        return Publisher.objects.create(**kwargs)

    def get_by_id(self, publisher_id: int) -> Publisher | None:
        return Publisher.objects.filter(id=publisher_id).first()

    def slug_exists(self, slug: str, *, exclude_id: int | None = None) -> bool:
        qs = Publisher.objects.filter(slug=slug)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def delete(self, publisher: Publisher) -> None:
        publisher.delete()
